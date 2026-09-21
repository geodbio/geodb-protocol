"""
The export round trip — the one write a read-only grant may make.

create -> poll status -> follow the download redirect. This is the only
asynchronous flow in the read half, and the only place a grant's request
CREATES something, so it carries its own concurrency refusal with its own
code: `export_concurrency` is NOT `throttled`, and a client that treats them
alike will hammer a server it should be polling.
"""

from __future__ import annotations

import time

from ..harness import REGISTRY, Failed, Skipped, require, require_equal, require_in

#: How long to wait for a job to leave a non-terminal state before giving up.
#: An export of a sandbox-sized project is seconds; the ceiling is generous
#: because a conformance run must not be the thing that fails on a slow server.
POLL_TIMEOUT_S = 180
POLL_INTERVAL_S = 2

TERMINAL_DONE = ('done', 'complete', 'completed', 'succeeded', 'success')
TERMINAL_BAD = ('failed', 'error', 'cancelled', 'canceled')


def _available_models(session):
    """What this server will export, asked of the server rather than assumed.

    There is no "list the export models" operation, so the enumeration comes
    out of the refusal: an unsupported model is refused with the allowed set
    beside it. A server may put that set under ``allowed_models`` (geoDB's
    pre-contract shape) or inside ``offending.allowed`` (the error envelope's
    shape); both are read, because a conformance runner must not fail a server
    over which of two documented spellings it chose.
    """
    if 'export_models' in session.shared:
        return session.shared['export_models']
    response = session.post('/api/v2/exports/',
                            json={'model': '__conformance_probe__',
                                  'format': 'csv'})
    models = []
    if response.status_code in (400, 422):
        try:
            body = response.json()
        except ValueError:
            body = {}
        if isinstance(body, dict):
            models = (body.get('allowed_models')
                      or (body.get('offending') or {}).get('allowed')
                      or [])
    session.shared['export_models'] = list(models)
    return session.shared['export_models']


@REGISTRY.add(
    'export.round_trip',
    'An export goes create (202, with a status URL) -> poll to a terminal '
    'state -> download via a redirect: the whole asynchronous lane works '
    'end to end for a read-only grant.')
def export_round_trip(session):
    models = _available_models(session)
    if not models:
        raise Skipped('this server advertises no exportable models')
    model = 'drill_collars' if 'drill_collars' in models else models[0]

    created = session.post('/api/v2/exports/',
                           json={'model': model, 'format': 'csv'})
    require(created.status_code in (200, 201, 202),
            f'creating an export must be accepted, got '
            f'{created.status_code}: {created.text[:200]!r}')
    body = session.json(created, 'export create')
    job_id = body.get('id') or body.get('job_id')
    require(job_id, f'the export create response names no job id: {body!r}')
    status_url = body.get('status_url') or f'/api/v2/exports/{job_id}/'

    deadline = time.time() + POLL_TIMEOUT_S
    state = body.get('state')
    status_body = {}
    while time.time() < deadline:
        status_body = session.get_json(status_url, what='export status')
        state = (status_body.get('state') or '').lower()
        if state in TERMINAL_DONE or state in TERMINAL_BAD:
            break
        time.sleep(POLL_INTERVAL_S)
    require(state not in TERMINAL_BAD,
            f'the export job reached {state!r}: {status_body!r}')
    require(state in TERMINAL_DONE,
            f'the export job was still {state!r} after {POLL_TIMEOUT_S}s')

    download_url = status_body.get('download_url') or f'{status_url}download/'
    response = session.get(download_url, allow_redirects=False)
    require(response.status_code in (200, 301, 302, 303, 307),
            f'the finished export must be downloadable, got '
            f'{response.status_code}')
    if response.status_code != 200:
        location = response.headers.get('Location')
        require(location,
                'the export download redirect carries no Location header')
        session.shared['export_download_location'] = location
    session.shared['export_job_id'] = job_id


@REGISTRY.add(
    'export.download_needs_no_credential',
    'The finished export\'s signed URL is fetchable without `Authorization`, '
    'like any other asset — the credential stops at the API.')
def export_download_unauthenticated(session):
    location = session.shared.get('export_download_location')
    if not location:
        # Run standalone (the break matrix runs one assertion at a time), so
        # drive the round trip ourselves rather than skipping. A check that
        # can only run after a sibling is a check that silently does not run.
        try:
            export_round_trip(session)
        except Skipped:
            raise
        location = session.shared.get('export_download_location')
    if not location:
        raise Skipped('the export download is served inline rather than as a '
                      'redirect to a signed URL, so there is no second hop '
                      'to check')
    import requests
    if location.startswith('/'):
        location = f'{session.base_url}{location}'
    response = requests.get(location, timeout=session.timeout, stream=True)
    response.close()
    require(response.status_code < 400,
            f'the signed export URL answered {response.status_code} with no '
            f'Authorization header')


@REGISTRY.add(
    'export.refusals_carry_a_registered_code',
    'An export refused for a bad model or format answers the ONE error '
    'envelope with a registered `reason_code`, like every other 4xx.')
def export_refusal_envelope(session):
    problems = []
    probes = (
        ('an unsupported model', {'model': '__conformance_probe__',
                                  'format': 'csv'}),
        ('an unsupported format', {'model': 'drill_collars',
                                   'format': '__conformance_probe__'}),
    )
    for what, payload in probes:
        response = session.post('/api/v2/exports/', json=payload)
        if response.status_code not in (400, 422):
            problems.append(
                f'{what}: expected a 400, got {response.status_code}')
            continue
        body = session.json(response, f'export refused for {what}')
        if 'reason_code' not in body:
            problems.append(
                f'{what}: the refusal body is {sorted(body)} — no '
                f'`reason_code`, so a client cannot branch on it '
                f'(body: {str(body)[:160]})')
            continue
        if body['reason_code'] not in session.contract.reason_codes:
            problems.append(
                f'{what}: reason_code {body["reason_code"]!r} is not '
                f'registered in errors.json')
        if 'remedy' not in body:
            problems.append(f'{what}: the refusal names no `remedy`')
    require(not problems,
            'export refusals that are not the protocol error envelope:\n'
            + '\n'.join(f'  {row}' for row in problems))


@REGISTRY.add(
    'export.concurrency_refusal_shape',
    'When the in-flight export cap is reached the refusal is 429 '
    '`export_concurrency` with `Retry-After` — distinct from `throttled`, '
    'because the right reaction is to POLL, not to back off and resend.',
    profile='full')
def export_concurrency_shape(session):
    models = _available_models(session)
    if not models:
        raise Skipped('this server advertises no exportable models')
    model = 'drill_collars' if 'drill_collars' in models else models[0]

    # Fire distinct jobs until the cap refuses one. Distinct `format`/model
    # combinations avoid the byte-identical-job reuse path, which would return
    # the same job rather than consuming a slot.
    refusal = None
    fired = 0
    for index in range(12):
        payload = {'model': models[index % len(models)],
                   'format': 'csv' if index % 2 else 'geoparquet'}
        response = session.post('/api/v2/exports/', json=payload)
        fired += 1
        if response.status_code == 429:
            refusal = response
            break
    if refusal is None:
        raise Skipped(
            f'the in-flight export cap was not reached in {fired} jobs — '
            f'either the cap is higher than this probe, or jobs finish faster '
            f'than they can be queued')

    body = session.json(refusal, 'export concurrency refusal')
    require_in('reason_code', body, 'export concurrency refusal')
    require_equal(body['reason_code'], 'export_concurrency',
                  'the in-flight export cap refusal')
    require(refusal.headers.get('Retry-After'),
            'the 429 carries no Retry-After header')
    require_in('offending', body, 'export concurrency refusal')
