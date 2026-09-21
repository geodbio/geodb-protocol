"""
The list envelope, paging, and the reachability of the core profile.

These are the checks that decide whether a client generated from the spec can
walk the data at all: one envelope on every list, a paging mechanism that
means what it says, and every operation the profile promises actually being
there.
"""

from __future__ import annotations

import re

from ..harness import (REGISTRY, Failed, Skipped, require, require_equal,
                       require_in)

#: Keys the envelope owes. `count`/`results` are the DRF half; the three
#: sync keys are what makes a mirror possible and are the half a naive
#: implementation drops.
ENVELOPE_KEYS = ('count', 'next', 'previous', 'results',
                 'deleted_ids', 'deleted_since_applied', 'sync_timestamp')

#: The custom-field pattern. Trap 3.2: anything outside the declared schema
#: must match this, or the server is emitting undeclared vocabulary.
CF_PATTERN = re.compile(r'^cf_[a-z0-9_]+$')


def core_list_paths(session):
    """Every core LIST operation path (no path parameters)."""
    return [path for method, path, _op in session.contract.core_operations()
            if method == 'GET' and '{' not in path
            and not path.startswith('/api/v2/stac')
            and path not in ('/api/v2/grant-context/',
                             '/api/v2/model-schemas/')]


@REGISTRY.add(
    'core.every_operation_reachable',
    'Every operation the spec flags `x-protocol-core` answers a grant — the '
    'published profile is the profile the server actually serves.')
def core_every_operation_reachable(session):
    unreachable = []
    for method, path, operation_id in session.contract.core_operations():
        if method != 'GET' or '{' in path:
            # Parameterised and write operations are covered by their own
            # named checks (export round trip, asset redirect, retrieve-by-id);
            # probing them here would need ids this check has no business
            # inventing.
            continue
        response = session.get(path)
        if response.status_code != 200:
            unreachable.append(
                f'{method} {path} ({operation_id}) -> '
                f'{response.status_code} {response.text[:120]!r}')
    require(not unreachable,
            'core operations the spec promises but the server does not serve:\n'
            + '\n'.join(f'  {row}' for row in unreachable))


@REGISTRY.add(
    'core.retrieve_by_id',
    'A row listed by a core list is retrievable by its own id at the '
    'operation the spec declares for it.')
def core_retrieve_by_id(session):
    for path in core_list_paths(session):
        body = session.get_json(path, params={'limit': 1})
        rows = body.get('results') or []
        if not rows:
            continue
        row_id = rows[0].get('id')
        if row_id is None:
            continue
        detail = session.get(f'{path}{row_id}/')
        require_equal(detail.status_code, 200,
                      f'GET {path}{row_id}/ (a row this server just listed)')
        row = session.json(detail, f'{path}{row_id}/')
        require_equal(row.get('id'), row_id,
                      f'{path}{row_id}/ returned a different row')
        session.shared['retrieved_from'] = path
        return
    raise Skipped('no core list on this server returned a row to retrieve')


@REGISTRY.add(
    'envelope.paginated_list',
    'Every core list answers the one envelope: `count`, `next`, `previous`, '
    '`results`, plus the `deleted_ids` / `deleted_since_applied` / '
    '`sync_timestamp` sync keys a mirror needs.')
def envelope_paginated_list(session):
    problems = []
    checked = 0
    for path in core_list_paths(session):
        body = session.get_json(path, params={'limit': 1})
        checked += 1
        missing = [key for key in ENVELOPE_KEYS if key not in body]
        if missing:
            problems.append(f'{path} is missing {missing}')
            continue
        if not isinstance(body['results'], list):
            problems.append(f'{path}: `results` is not an array')
        if not isinstance(body['count'], int):
            problems.append(f'{path}: `count` is not an integer')
        if not isinstance(body['deleted_ids'], list):
            problems.append(f'{path}: `deleted_ids` is not an array')
    require(checked, 'the spec declares no core list operations')
    require(not problems,
            'lists that do not answer the protocol envelope:\n'
            + '\n'.join(f'  {row}' for row in problems))


@REGISTRY.add(
    'envelope.limit_offset_paging',
    '`limit` and `offset` page the result set: a second page returns different '
    'rows, and `next` is a followable URL that carries its own parameters.')
def envelope_limit_offset(session):
    for path in core_list_paths(session):
        first = session.get_json(path, params={'limit': 1})
        if first['count'] < 2:
            continue
        require_equal(len(first['results']), 1,
                      f'{path}?limit=1 must return exactly one row')
        second = session.get_json(path, params={'limit': 1, 'offset': 1})
        require_equal(len(second['results']), 1,
                      f'{path}?limit=1&offset=1 must return exactly one row')
        first_id = first['results'][0].get('id')
        second_id = second['results'][0].get('id')
        require(first_id != second_id,
                f'{path}: offset=1 returned the same row as offset=0 '
                f'(id {first_id}) — offset does not page')
        require(first.get('next'),
                f'{path}: {first["count"]} rows and limit=1, but `next` is '
                f'{first.get("next")!r}')
        followed = session.get_json(first['next'],
                                    what=f'the `next` URL from {path}')
        require(followed['results'],
                f'{path}: following `next` returned no rows')
        session.shared['paged_path'] = path
        return
    raise Skipped('no core list on this server holds the two rows this check '
                  'needs to prove paging')


@REGISTRY.add(
    'envelope.page_size_is_not_silently_honoured',
    '`page_size` is not a paging parameter here. A server that neither honours '
    'it nor says so lets a client conclude a project is small; this check '
    'reports which of the two happens.')
def envelope_page_size(session):
    path = session.shared.get('paged_path')
    if not path:
        for candidate in core_list_paths(session):
            if session.get_json(candidate, params={'limit': 1})['count'] >= 2:
                path = candidate
                break
    if not path:
        raise Skipped('no list with enough rows to tell honoured from ignored')

    baseline = session.get_json(path, params={'limit': 500})
    total = baseline['count']
    if total < 2:
        raise Skipped('not enough rows to distinguish honoured from ignored')

    response = session.get(path, params={'page_size': 1})
    if response.status_code == 400:
        # The other acceptable behaviour: refuse the parameter by name. That
        # is strictly better than ignoring it, and it is a pass.
        body = session.json(response, 'page_size refusal')
        require_in('reason_code', body, 'page_size refusal')
        return
    require_equal(response.status_code, 200,
                  f'{path}?page_size=1 answered unexpectedly')
    body = session.json(response, f'{path}?page_size=1')
    returned = len(body['results'])
    if returned == 1 and total > 1:
        # Honoured. Then the spec must declare it, or a client cannot know.
        declared = {p.get('name') for p
                    in session.contract.operation('get', path).get('parameters', [])}
        require('page_size' in declared,
                f'{path}: the server HONOURS `page_size` (returned 1 of '
                f'{total} rows) but the spec does not declare it — a '
                f'spec-driven client cannot discover a parameter that '
                f'changes its results')
        return
    # Ignored. That is the documented behaviour, and AGENTS.md's "bonus trap"
    # says so — but the trap is only safe because `count` still tells the
    # truth about how many rows exist.
    require_equal(body['count'], total,
                  f'{path}: `page_size` was ignored AND `count` changed — a '
                  f'client cannot detect the ignored parameter')


@REGISTRY.add(
    'envelope.only_cf_extra_keys',
    'Beyond the declared schema a row carries only `cf_*` custom fields — '
    'positive declaration: what the spec does not declare is not on the wire.')
def envelope_only_cf_keys(session):
    from .schemas import schema_for_list_path

    undeclared = []
    for path in core_list_paths(session):
        schema_name = schema_for_list_path(session, path)
        if schema_name is None:
            continue
        schema = session.contract.schema(schema_name)
        declared = set(schema.get('properties') or {})
        body = session.get_json(path, params={'limit': 5})
        for row in body.get('results') or []:
            for key in row:
                if key in declared or CF_PATTERN.match(key):
                    continue
                undeclared.append(f'{path}: {key!r} (schema {schema_name})')
    require(not undeclared,
            'keys on the wire that neither the schema declares nor the `cf_*` '
            'pattern allows:\n'
            + '\n'.join(f'  {row}' for row in sorted(set(undeclared))))


@REGISTRY.add(
    'envelope.protocol_version_header',
    'Every response carries `X-GeoDB-Protocol-Version`, and it equals the '
    'version of the spec this suite was built from.')
def envelope_protocol_version(session):
    response = session.get('/api/v2/grant-context/')
    header = response.headers.get('X-GeoDB-Protocol-Version')
    require(header is not None,
            'no X-GeoDB-Protocol-Version header — a client cannot tell which '
            'version of the protocol it is talking to')
    expected = session.contract.version
    require_equal(header, expected,
                  f'X-GeoDB-Protocol-Version vs the packaged spec '
                  f'(spec/openapi.yaml info.version)')


@REGISTRY.add(
    'envelope.grant_context_version_agrees',
    '`grant-context` reports the same protocol version as the response header, '
    'so the body and the header cannot disagree about the contract in force.')
def envelope_grant_context_version(session):
    body = session.shared.get('grant_context')
    if body is None:
        body = session.get_json('/api/v2/grant-context/')
    require_in('protocol_version', body, 'grant-context')
    require_equal(body['protocol_version'], session.contract.version,
                  'grant-context protocol_version vs the packaged spec')
