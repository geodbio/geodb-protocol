"""
`modified_since` / `deleted_since` — the semantics a mirror is built on.

The contract here is unusual and has to be checked rather than assumed,
because the failure mode is silent: the comparison is DAY-granular, so a
client that treats it as an instant gets same-day repeats and, if it appends
rather than upserts, duplicates every poll. And an unparseable value must be
REFUSED rather than ignored — a server that ignores it answers a full table
scan to a client that believes it asked for a delta.
"""

from __future__ import annotations

import datetime as dt

from ..harness import REGISTRY, Failed, Skipped, require, require_equal, require_in


def _a_list_path(session):
    from .envelope import core_list_paths
    for path in core_list_paths(session):
        if session.get_json(path, params={'limit': 1})['count'] > 0:
            return path
    return None


@REGISTRY.add(
    'sync.modified_since_accepted',
    '`modified_since` with an ISO date is accepted and echoed back through '
    '`sync_timestamp`, which is the cursor for the next pull.')
def sync_modified_since_accepted(session):
    path = _a_list_path(session)
    if path is None:
        raise Skipped('no core list on this server holds a row')
    body = session.get_json(path, params={'modified_since': '2000-01-01',
                                          'limit': 1})
    require_in('sync_timestamp', body, f'{path}?modified_since=')
    require(body['sync_timestamp'],
            f'{path}: `sync_timestamp` is empty, so a client has no cursor '
            f'to persist for its next incremental pull')
    # It must parse as a timestamp, or it cannot be fed back.
    stamp = body['sync_timestamp']
    try:
        dt.datetime.fromisoformat(stamp.replace('Z', '+00:00'))
    except (ValueError, AttributeError):
        raise Failed(f'{path}: `sync_timestamp` {stamp!r} is not an ISO 8601 '
                     f'timestamp, so it cannot be fed back as a cursor')
    session.shared['sync_path'] = path
    session.shared['sync_timestamp'] = stamp


@REGISTRY.add(
    'sync.modified_since_is_day_granular',
    'The comparison is by DAY: a cursor from today still returns rows touched '
    'today. Over-inclusion, never under-inclusion — so a client upserts by id '
    'and never misses a change.')
def sync_day_granular(session):
    path = session.shared.get('sync_path') or _a_list_path(session)
    if path is None:
        raise Skipped('no core list on this server holds a row')

    everything = session.get_json(path, params={'limit': 1})
    if not everything['count']:
        raise Skipped('no rows to reason about')

    # A cursor set to the far future must not return rows; a cursor set to the
    # epoch must return all of them. Between those two, the day-granular claim
    # is that TODAY's cursor still includes rows modified today.
    future = (dt.date.today() + dt.timedelta(days=365)).isoformat()
    future_body = session.get_json(path, params={'modified_since': future,
                                                 'limit': 1})
    require_equal(future_body['count'], 0,
                  f'{path}?modified_since={future} (a year ahead) must match '
                  f'no rows; `modified_since` appears not to filter at all')

    past_body = session.get_json(path, params={'modified_since': '2000-01-01',
                                               'limit': 1})
    require_equal(past_body['count'], everything['count'],
                  f'{path}?modified_since=2000-01-01 must match every row')

    # The day-granular claim itself: a full ISO timestamp for LATER TODAY must
    # not narrow within the day.
    today = dt.date.today().isoformat()
    today_body = session.get_json(path, params={'modified_since': today,
                                                'limit': 1})
    late_today = f'{today}T23:59:59'
    late_body = session.get_json(path, params={'modified_since': late_today,
                                               'limit': 1})
    require_equal(
        late_body['count'], today_body['count'],
        f'{path}: `modified_since={late_today}` matched '
        f'{late_body["count"]} rows but `modified_since={today}` matched '
        f'{today_body["count"]} — the comparison narrowed WITHIN the day. '
        f'The protocol documents day granularity; a client that trusts a '
        f'within-day cursor here will silently miss rows')


@REGISTRY.add(
    'sync.unparseable_is_refused',
    'An unparseable `modified_since` is refused 400 `invalid_parameter` with '
    'the offending value named — never silently ignored into a full scan.')
def sync_unparseable_refused(session):
    path = session.shared.get('sync_path') or _a_list_path(session)
    if path is None:
        raise Skipped('no core list on this server holds a row')
    response = session.get(path, params={'modified_since': 'yesterday'})
    require_equal(response.status_code, 400,
                  f'{path}?modified_since=yesterday must be REFUSED, not '
                  f'ignored (a client believes it asked for a delta)')
    body = session.json(response, 'invalid modified_since')
    require_in('reason_code', body, 'invalid modified_since body')
    require_equal(body['reason_code'], 'invalid_parameter',
                  'an unparseable date parameter')
    require_in('offending', body, 'invalid modified_since body')
    require_equal(body['offending'].get('parameter'), 'modified_since',
                  '`offending` names the parameter at fault')


@REGISTRY.add(
    'sync.deleted_since_semantics',
    '`deleted_since` returns the deletion feed with `deleted_since_applied` '
    'echoing what was applied, so a mirror can prove its removals ran.')
def sync_deleted_since(session):
    path = session.shared.get('sync_path') or _a_list_path(session)
    if path is None:
        raise Skipped('no core list on this server holds a row')
    body = session.get_json(path, params={'deleted_since': '2000-01-01',
                                          'limit': 1})
    require_in('deleted_ids', body, f'{path}?deleted_since=')
    require(isinstance(body['deleted_ids'], list),
            f'{path}: `deleted_ids` must be an array')
    require_in('deleted_since_applied', body, f'{path}?deleted_since=')
    require(body['deleted_since_applied'] not in (None, False),
            f'{path}: `deleted_since` was sent but `deleted_since_applied` is '
            f'{body["deleted_since_applied"]!r} — a client cannot tell whether '
            f'its deletion feed was honoured or dropped')

    response = session.get(path, params={'deleted_since': 'whenever'})
    require_equal(response.status_code, 400,
                  f'{path}?deleted_since=whenever must be refused like any '
                  f'other unparseable date')
    refusal = session.json(response, 'invalid deleted_since')
    require_equal(refusal.get('reason_code'), 'invalid_parameter',
                  'an unparseable deleted_since')


@REGISTRY.add(
    'sync.deleted_ids_on_first_page',
    'The deletion feed rides the FIRST page, so a client that reads page one '
    'has it even when it never paginates.')
def sync_deleted_ids_first_page(session):
    path = session.shared.get('sync_path') or _a_list_path(session)
    if path is None:
        raise Skipped('no core list on this server holds a row')
    body = session.get_json(path, params={'limit': 1})
    require_in('deleted_ids', body,
               f'{path} first page (no offset)')
    require(isinstance(body['deleted_ids'], list),
            f'{path}: `deleted_ids` on the first page must be an array, got '
            f'{type(body["deleted_ids"]).__name__}')
