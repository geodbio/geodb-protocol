"""
Discovery, and the two shapes that bit a cold agent.

Both checks here exist because A7's cold-agent runs hit them
(``protocol_a7_cold_agent_transcripts_2026-09-21.md``). Neither is a server
bug — both are correct, deliberate wire shapes that a reader assumes wrongly
because the rest of the API taught them a different assumption. That is
exactly the kind of thing a conformance suite should PIN: not because the
server might change, but because a second implementer reading only the spec
will otherwise guess the more obvious shape and produce something a client
cannot consume.

`model-schemas` answers `{count, models}` rather than the list envelope.
`bhid` (and its siblings) is a natural-key OBJECT, not a scalar, so a
DataFrame merge on it raises `unhashable type: 'dict'` until you reach inside
for the hole id.
"""

from __future__ import annotations

from ..harness import REGISTRY, Failed, Skipped, require, require_equal, require_in


@REGISTRY.add(
    'discovery.model_schemas_shape',
    '`model-schemas` answers `{count, models: [...]}` — its own shape, NOT the '
    'list envelope. A client that loops it like every other list finds nothing '
    'and concludes the project has no custom fields.')
def discovery_model_schemas_shape(session):
    body = session.get_json('/api/v2/model-schemas/',
                            what='GET /api/v2/model-schemas/')
    require(isinstance(body, dict),
            f'model-schemas must answer an object, got '
            f'{type(body).__name__}')
    require_in('models', body, 'model-schemas')
    require(isinstance(body['models'], list),
            '`models` must be an array of record types')
    require_in('count', body, 'model-schemas')
    require_equal(body['count'], len(body['models']),
                  '`count` vs the number of entries in `models`')
    # It is NOT the paginated envelope, and saying so is the point: a client
    # written against `results` must fail loudly here rather than silently
    # iterate nothing.
    require('results' not in body,
            'model-schemas carries BOTH `models` and `results` — pick one '
            'shape; two spellings of the same list is how a client ends up '
            'reading the wrong one')
    require(body['models'], 'this project exposes no record types at all')
    session.shared['model_schemas'] = body['models']


@REGISTRY.add(
    'discovery.model_schemas_join_keys',
    'Every record type names both `model_type` (the key you look it up by) and '
    '`api_endpoint` (where its rows live), so discovery joins to data without '
    'transforming one name into the other.')
def discovery_model_schemas_join_keys(session):
    models = session.shared.get('model_schemas')
    if models is None:
        models = session.get_json('/api/v2/model-schemas/')['models']
    problems = []
    for entry in models:
        for key in ('model_type', 'api_endpoint'):
            if not entry.get(key):
                problems.append(f'{entry!r}: no {key!r}')
    require(not problems,
            'record types that cannot be joined to their rows:\n'
            + '\n'.join(f'  {row}' for row in problems[:10]))

    # The lookup key is `model_type`, not the endpoint segment. A server that
    # accepted the endpoint segment here would be teaching two spellings.
    sample = next((entry for entry in models if entry.get('model_type')), None)
    if sample is None:
        raise Skipped('no record type to look up')
    response = session.get(f'/api/v2/model-schemas/{sample["model_type"]}/')
    require_equal(response.status_code, 200,
                  f'GET /api/v2/model-schemas/{sample["model_type"]}/ — the '
                  f'`model_type` this server just advertised')
    detail = session.json(response, 'one model schema')
    require(detail.get('fields') is not None or detail.get('model_type'),
            f'the per-type schema carries neither `fields` nor `model_type`: '
            f'{sorted(detail)}')


@REGISTRY.add(
    'discovery.natural_key_is_an_object',
    'A cross-record reference like `bhid` is a natural-key OBJECT, not a '
    'scalar: reach inside it for the identifier. Merging a DataFrame on the '
    'raw field raises `unhashable type: dict`.')
def discovery_natural_key_shape(session):
    body = session.get_json('/api/v2/drill-samples/', params={'limit': 5})
    rows = body.get('results') or []
    if not rows:
        raise Skipped('this project holds no drill samples')
    problems = []
    checked = 0
    for row in rows:
        reference = row.get('bhid')
        if reference is None:
            continue
        checked += 1
        if not isinstance(reference, dict):
            problems.append(
                f'drill sample {row.get("id")}: `bhid` is '
                f'{type(reference).__name__} {reference!r}. The protocol '
                f'declares a natural-key object; a scalar here means a '
                f'client written against the spec reads the wrong type')
            continue
        if not reference.get('hole_id'):
            problems.append(
                f'drill sample {row.get("id")}: `bhid` names no `hole_id`, so '
                f'there is no key to join a collar on: {sorted(reference)}')
    if not checked:
        raise Skipped('no drill sample carries a collar reference')
    require(not problems,
            'collar references that cannot be joined:\n'
            + '\n'.join(f'  {row}' for row in problems[:10]))

    # And the join it exists for actually closes.
    collars = session.get_json('/api/v2/drill-collars/', params={'limit': 500})
    names = {row.get('name') for row in collars.get('results') or []}
    if not names:
        raise Skipped('no collars to join against')
    unmatched = [row.get('id') for row in rows
                 if isinstance(row.get('bhid'), dict)
                 and row['bhid'].get('hole_id') not in names]
    require(not unmatched,
            f'drill samples whose `bhid.hole_id` matches no collar this '
            f'server serves: {unmatched[:10]}')


@REGISTRY.add(
    'discovery.grant_context_scope',
    '`grant-context` states the project, the read-only flag and the throttle '
    'rate — the cheapest first call, and the one that tells a client what it '
    'is holding before it pulls anything.')
def discovery_grant_context_scope(session):
    body = session.shared.get('grant_context')
    if body is None:
        body = session.get_json('/api/v2/grant-context/')
    for key in ('protocol_version', 'project', 'read_only', 'throttle_rate'):
        require_in(key, body, 'grant-context')
    require_equal(body['read_only'], True,
                  'a grant is read-only; `read_only` must say so')
    require(body.get('token_prefix'),
            'grant-context names no `token_prefix`, so an owner reading their '
            'access log cannot tell which credential made a call')
    require('token' not in body and 'token_hash' not in body,
            'grant-context echoes the credential itself — it must name only '
            'the prefix')
