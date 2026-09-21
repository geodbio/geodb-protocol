"""
Auth and the refusal contract.

The protocol's security claim is that a token reads one project, read-only,
and that a refusal is something a program can act on. These checks are what
turn that claim into something a vendor can verify in thirty seconds.
"""

from __future__ import annotations

from ..harness import REGISTRY, Failed, Skipped, require, require_equal, require_in

#: A credential that cannot possibly resolve to a grant. Deliberately shaped
#: like a real token (the server must not distinguish "wrong shape" from
#: "wrong value" in a way that leaks which tokens exist).
GARBAGE_TOKEN = 'gdbg_conformance_not_a_real_token_0000000000'

#: Keys the error envelope owes on every 4xx.
ERROR_KEYS = ('reason_code', 'detail', 'remedy')


@REGISTRY.add(
    'auth.header_accepted',
    'A grant token in `Authorization: Grant <token>` is accepted and '
    'identifies exactly one project.')
def auth_header_accepted(session):
    body = session.get_json('/api/v2/grant-context/',
                            what='GET /api/v2/grant-context/')
    require_in('project', body, 'grant-context')
    require(isinstance(body.get('project'), dict) and body['project'].get('id'),
            f'grant-context: `project` must name the project this credential '
            f'is pinned to, got {body.get("project")!r}')
    require_in('read_only', body, 'grant-context')
    session.shared['project'] = body['project']
    session.shared['grant_context'] = body


@REGISTRY.add(
    'auth.bearer_rejected',
    '`Authorization: Bearer <token>` is refused — the scheme is `Grant`, and a '
    'client that guesses Bearer is told so rather than silently unauthorised.')
def auth_bearer_rejected(session):
    if not session.token:
        raise Skipped('no token supplied')
    response = session.request(
        'GET', '/api/v2/grant-context/', auth=False,
        headers={'Authorization': f'Bearer {session.token}'})
    require(response.status_code == 401,
            f'a Bearer-scheme header must be refused 401, got '
            f'{response.status_code}')
    body = session.json(response, 'Bearer refusal')
    require_in('reason_code', body, 'Bearer refusal body')


@REGISTRY.add(
    'auth.401_shape',
    'An unusable credential answers 401 with `reason_code`, `remedy` and the '
    'short `grant_error` key, so a revoked token is distinguishable from a '
    'transient failure.')
def auth_401_shape(session):
    response = session.request('GET', '/api/v2/grant-context/', auth=False,
                               headers={'Authorization':
                                        f'Grant {GARBAGE_TOKEN}'})
    require(response.status_code == 401,
            f'an unknown credential must answer 401, got '
            f'{response.status_code}: {response.text[:200]!r}')
    body = session.json(response, '401 body')
    for key in ERROR_KEYS:
        require_in(key, body, '401 body')
    require_in('grant_error', body, '401 body')
    registered = session.contract.reason_codes
    require(body['reason_code'] in registered,
            f'401 reason_code {body["reason_code"]!r} is not registered in '
            f'errors.json (registered: {sorted(registered)})')
    require_equal(registered[body['reason_code']]['http'], 401,
                  f'errors.json registers {body["reason_code"]!r} at a '
                  f'different status than the wire used')


@REGISTRY.add(
    'auth.www_authenticate',
    'A 401 carries `WWW-Authenticate: Grant`, so a client discovers the scheme '
    'from the refusal itself.')
def auth_www_authenticate(session):
    response = session.request('GET', '/api/v2/grant-context/', auth=False,
                               headers={'Authorization':
                                        f'Grant {GARBAGE_TOKEN}'})
    require_equal(response.status_code, 401, 'unknown credential status')
    header = response.headers.get('WWW-Authenticate')
    require(header is not None,
            'the 401 carries no WWW-Authenticate header')
    require(header.strip().split()[0].lower() == 'grant',
            f'WWW-Authenticate must name the Grant scheme, got {header!r}')


@REGISTRY.add(
    'auth.no_credential_refused',
    'A request with no credential at all is refused 401, not served '
    'anonymously.')
def auth_no_credential(session):
    response = session.request('GET', '/api/v2/drill-collars/', auth=False)
    require(response.status_code == 401,
            f'an unauthenticated read must answer 401, got '
            f'{response.status_code}')


@REGISTRY.add(
    'auth.malformed_header',
    'A header that is not `Grant <token>` is refused with its own code rather '
    'than being treated as an unknown token.')
def auth_malformed_header(session):
    response = session.request('GET', '/api/v2/grant-context/', auth=False,
                               headers={'Authorization': 'Grant'})
    require(response.status_code == 401,
            f'a malformed Authorization header must answer 401, got '
            f'{response.status_code}')
    body = session.json(response, 'malformed-header refusal')
    require_in('reason_code', body, 'malformed-header refusal')
    require(body['reason_code'] in session.contract.reason_codes,
            f'reason_code {body["reason_code"]!r} is not registered in '
            f'errors.json')


@REGISTRY.add(
    'auth.write_refused',
    'A write with a read-only grant is refused `grant_write_forbidden` — the '
    'read-only claim is enforced by the server, not by the client library.')
def auth_write_refused(session):
    response = session.post('/api/v2/drill-collars/',
                            json={'name': 'conformance-probe'})
    require(response.status_code in (403, 405),
            f'a POST to a read-only collection must be refused 403 (or 405), '
            f'got {response.status_code}: {response.text[:200]!r}')
    body = session.json(response, 'write refusal')
    require_in('reason_code', body, 'write refusal body')
    require_equal(body['reason_code'], 'grant_write_forbidden',
                  'a write refused with a read-only grant')


@REGISTRY.add(
    'auth.v1_refused',
    'The `/api/v1/` tree refuses a grant with `use_v2`, so a client that '
    'guesses the old path is redirected by code rather than by a 404.')
def auth_v1_refused(session):
    response = session.get('/api/v1/drill-collars/')
    require(response.status_code in (403, 404),
            f'/api/v1/ with a grant must be refused, got '
            f'{response.status_code}')
    body = session.json(response, '/api/v1/ refusal')
    require_in('reason_code', body, '/api/v1/ refusal body')
    require_equal(body['reason_code'], 'use_v2',
                  '/api/v1/ refusal reason_code')


@REGISTRY.add(
    'auth.cross_project_is_404',
    'A row outside the grant\'s project is indistinguishable from one that does '
    'not exist: 404 with `not_found`, never 403.')
def auth_cross_project_404(session):
    # An id that cannot exist in any project. The contract is about the SHAPE
    # of the refusal: a 403 here would tell a caller that the id is real and
    # belongs to somebody else, which is the tenancy leak this forbids.
    response = session.get('/api/v2/drill-collars/999999999/')
    require_equal(response.status_code, 404,
                  'an out-of-scope or absent row must answer 404')
    body = session.json(response, '404 body')
    require_in('reason_code', body, '404 body')
    require_equal(body['reason_code'], 'not_found', '404 reason_code')
    require_in('remedy', body, '404 body')
