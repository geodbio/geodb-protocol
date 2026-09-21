"""
The error contract, swept across every 4xx this suite can provoke.

Design rule 2 of the protocol is "a refusal names the remedy, in a code". The
individual checks in ``auth``/``sync``/``exports`` assert the code each
specific refusal uses; this module asserts the RULE — that nothing the server
refuses comes back with a code nobody published, and that the register the
suite carries is the register the server implements.

That distinction matters. A server can pass every named refusal check and
still answer some untested path with a bare `{"detail": "..."}` prose body,
which is exactly the state the audit found the API in.
"""

from __future__ import annotations

from ..harness import REGISTRY, Failed, Skipped, require, require_equal, require_in

#: Requests that must be refused, each shaped to reach a different refusal
#: path. `(label, method, path, kwargs)`.
REFUSAL_PROBES = (
    ('an unparseable date parameter', 'GET',
     '/api/v2/drill-collars/', {'params': {'modified_since': 'yesterday'}}),
    ('a row that does not exist', 'GET',
     '/api/v2/drill-collars/999999999/', {}),
    ('a write with a read-only grant', 'POST',
     '/api/v2/drill-collars/', {'json': {'name': 'conformance-probe'}}),
    ('the /api/v1/ tree', 'GET', '/api/v1/drill-collars/', {}),
    ('an endpoint outside the grant surface', 'GET',
     '/api/v2/projects/', {}),
    ('an unsupported export model', 'POST', '/api/v2/exports/',
     {'json': {'model': '__conformance_probe__', 'format': 'csv'}}),
    ('an unsupported export format', 'POST', '/api/v2/exports/',
     {'json': {'model': 'drill_collars', 'format': '__conformance_probe__'}}),
    ('an export job that does not exist', 'GET',
     '/api/v2/exports/00000000-0000-0000-0000-000000000000/', {}),
)


@REGISTRY.add(
    'errors.every_4xx_is_registered',
    'Every refusal this suite can provoke carries a `reason_code` that is in '
    'the published register, with the HTTP status the register gives it — an '
    'agent handles what it can enumerate.')
def errors_every_4xx_registered(session):
    registered = session.contract.reason_codes
    problems = []
    checked = 0
    for label, method, path, kwargs in REFUSAL_PROBES:
        response = session.request(method, path, note=label, **kwargs)
        if response.status_code < 400 or response.status_code >= 500:
            # Not a refusal on this server (an endpoint it does not serve at
            # all, or one it allows). Not this check's business.
            continue
        checked += 1
        try:
            body = response.json()
        except ValueError:
            problems.append(
                f'{label} ({method} {path}) -> {response.status_code} is not '
                f'JSON: {response.text[:120]!r}')
            continue
        if not isinstance(body, dict) or 'reason_code' not in body:
            problems.append(
                f'{label} ({method} {path}) -> {response.status_code} carries '
                f'no `reason_code`; keys were '
                f'{sorted(body) if isinstance(body, dict) else type(body).__name__} '
                f'({str(body)[:140]})')
            continue
        code = body['reason_code']
        if code not in registered:
            problems.append(
                f'{label} ({method} {path}) -> reason_code {code!r} is not in '
                f'errors.json')
            continue
        expected_status = registered[code]['http']
        if response.status_code != expected_status:
            problems.append(
                f'{label} ({method} {path}) -> answered '
                f'{response.status_code} with {code!r}, which errors.json '
                f'registers at {expected_status}')
        if not body.get('remedy'):
            problems.append(
                f'{label} ({method} {path}) -> {code!r} carries no `remedy`')
    require(checked, 'no probe in this suite was refused, so the error '
                     'contract was never exercised')
    require(not problems,
            f'refusals that are not the published error contract '
            f'({checked} probed):\n'
            + '\n'.join(f'  {row}' for row in problems))


@REGISTRY.add(
    'errors.register_is_self_consistent',
    'The published register itself is well formed: every code has an HTTP '
    'status, a meaning, a remedy and a retry semantics a client can act on.')
def errors_register_self_consistent(session):
    registry = session.contract.errors
    semantics = set(registry.get('retry_semantics') or {})
    require(semantics,
            'errors.json declares no `retry_semantics`, so `retry` values '
            'mean nothing to a reader')
    problems = []
    for code, entry in session.contract.reason_codes.items():
        for key in ('http', 'meaning', 'remedy', 'retry'):
            if not entry.get(key):
                problems.append(f'{code}: no {key!r}')
        if entry.get('retry') and entry['retry'] not in semantics:
            problems.append(
                f'{code}: retry {entry["retry"]!r} is not one of '
                f'{sorted(semantics)}')
        if not isinstance(entry.get('http'), int):
            problems.append(f'{code}: `http` is not an integer')
    require(not problems,
            'the published error register is not self-consistent:\n'
            + '\n'.join(f'  {row}' for row in problems))


@REGISTRY.add(
    'errors.detail_is_not_the_contract',
    'A refusal carries machine-readable keys beside its prose, so a client '
    'never has to pattern-match `detail` to know what happened.')
def errors_detail_not_the_contract(session):
    response = session.get('/api/v2/drill-collars/',
                           params={'modified_since': 'yesterday'})
    require_equal(response.status_code, 400, 'an unparseable date')
    body = session.json(response, 'the refusal')
    require_in('reason_code', body, 'the refusal')
    require_in('remedy', body, 'the refusal')
    require(body.get('offending'),
            'a parameter refusal names no `offending` parameter, so a client '
            'must parse the prose to learn which parameter was wrong')
