"""
The write profile's assertions — one per clause of the write contract
(protocol plan §1: what ``geodb_conformance write`` proves).

Each assertion builds its own rows (uniquely named, so the order never
matters), reads back what the server STORED rather than trusting what it
said, and leaves its writes for the run's clean-up to undo. Every one has a
breakage in ``mock_write.WRITE_BREAKAGES`` it has been watched to fail on.
"""

from __future__ import annotations

import uuid

from ..harness import Failed, Skipped, require, require_equal, require_in
from . import WRITE_REGISTRY as R
from .session import CHILD, COLLAR_PATH, PARENT, SAMPLE_PATH, WRITES


def _rows(body):
    return [(r.get('status'), r.get('reason_code')) for r in body.get('rows', [])]


def _refusal(session, response, code, status, what):
    """A request-level refusal: ``status`` + a registered ``code`` + remedy."""
    body = session.json(response, what)
    require_equal(response.status_code, status, f'{what}: HTTP status')
    require_equal(body.get('reason_code'), code, f'{what}: reason_code')
    require(body.get('remedy'), f'{what}: the refusal names no remedy')
    return body


# ---------------------------------------------------------------------------
# The contract an agent reads before writing
# ---------------------------------------------------------------------------

@R.add('write.describe_serves_the_contract',
       '`GET /api/v2/records/describe/<Model>/` serves the live write contract: the '
       'fields, the identifying fields, the intents, and for a set-aware model the '
       'set rule with the project\'s sets — so an agent never guesses a field.')
def describe_serves_the_contract(session):
    parent, child = session.describe(PARENT), session.describe(CHILD)
    for model, body in ((PARENT, parent), (CHILD, child)):
        require(body.get('identifying_fields'), f'describe {model}: no identifying_fields')
        names = {f.get('name') for f in body.get('fields') or []}
        require(names, f'describe {model}: no fields')
        missing = set(session.write_profile['intents']) - set(body.get('intents') or [])
        require(not missing, f'describe {model}: intents missing {sorted(missing)}')
    names = {f['name'] for f in parent['fields']}
    for field in ('latitude', 'longitude', 'epsg'):
        require_in(field, names, f'describe {PARENT} fields')
    rule = child.get('set') or {}
    require(rule.get('field') and isinstance(rule.get('sets'), list),
            f'describe {CHILD}: no set rule ({{field, sets}}), so an agent cannot ask '
            f'the user which set')


# ---------------------------------------------------------------------------
# Validate, coordinates, identity, conflicts
# ---------------------------------------------------------------------------

@R.add('write.dry_run_is_validate',
       '`"dry_run": true` answers exactly the per-row outcomes the write would — into '
       'a new set too — and writes nothing: validate is the dry run, never a second '
       'code path.')
def dry_run_is_validate(session):
    rows = [session.collar_row('DRY'),
            {k: v for k, v in session.collar_row('DRY').items() if k != 'epsg'}]
    body = {'model': PARENT, 'intent': 'create', 'records': rows}
    dry = session.records(dict(body, dry_run=True))
    require(dry.get('write_id') is None, f'a dry run returned a write_id ({dry.get("write_id")})')
    real = session.records(body)
    require_equal(_rows(dry), _rows(real), 'per-row outcomes of the dry run vs the write')
    require_equal(real['rows'][0]['status'], 'created',
                  'the good row after its dry run (a dry run that wrote makes it "unchanged")')
    require(session.row(COLLAR_PATH, real['rows'][0]['id']) is not None,
            'the written row cannot be read back')
    # ... and into a NEW set (validate-first is how an agent writes a set the
    # user just named): the dry run answers as the write lands.
    hole = rows[0]['name']
    samples = {'model': CHILD, 'intent': 'create',
               'set': {'name': session.new_set_name(), 'create': True},
               'records': [{'bhid': hole, 'name': session.name('S'), 'depth_from': 2.0 * i,
                            'depth_to': 2.0 * i + 2.0} for i in range(2)]}
    dry = session.records(dict(samples, dry_run=True))
    real = session.records(samples)
    require_equal(_rows(dry), _rows(real),
                  'per-row outcomes of a dry run into a new set vs the write')
    require_equal(_rows(real), [('created', None)] * 2, 'the samples written into the new set')


@R.add('write.missing_crs_refused_per_row',
       'A row with coordinates and no `epsg` is refused `missing_crs` and an '
       'unparseable coordinate `invalid_geometry`, on THAT row — the batch goes on, '
       'and the stored native coordinate is exactly what was sent.')
def missing_crs_refused_per_row(session):
    good = session.collar_row('CRS', latitude=37.91, longitude=-91.02)
    no_epsg = {k: v for k, v in session.collar_row('CRS').items() if k != 'epsg'}
    bad = session.collar_row('CRS', latitude='north of the creek')
    body = session.records({'model': PARENT, 'intent': 'create',
                            'records': [good, no_epsg, bad]})
    require_equal(_rows(body), [('created', None), ('refused', 'missing_crs'),
                                ('refused', 'invalid_geometry')], 'the three rows')
    stored = session.row(COLLAR_PATH, body['rows'][0]['id'])
    require(stored is not None, 'the good row was not stored')
    for field in ('latitude', 'longitude', 'epsg'):
        require_equal(stored.get(field), good[field], f'the stored native {field}')


@R.add('write.external_id_is_a_no_op',
       'A record re-sent with the same `external_id` is `unchanged` — the same id, '
       'no second row, no write — so a vendor can re-send a whole batch safely.')
def external_id_is_a_no_op(session):
    row = dict(session.collar_row('EXT'), external_id=f'conf-{uuid.uuid4().hex}')
    first = session.records({'model': PARENT, 'intent': 'create', 'records': [row]})
    require_equal(_rows(first), [('created', None)], 'the first send')
    again = session.records({'model': PARENT, 'intent': 'create', 'records': [row]})
    require_equal(_rows(again), [('unchanged', None)], 'the same external_id re-sent')
    require_equal(again['rows'][0].get('id'), first['rows'][0]['id'], 'the id it names')
    require(again.get('write_id') is None,
            f'a re-send that changed nothing recorded a write ({again.get("write_id")})')


@R.add('write.idempotency_key_replays',
       'The same `Idempotency-Key` with the same body answers the stored response '
       'verbatim (`Idempotent-Replayed: true`) without writing twice; with a different '
       'body it is refused `idempotency_key_reused`.')
def idempotency_key_replays(session):
    key = str(uuid.uuid4())
    body = {'model': PARENT, 'intent': 'create', 'records': [session.collar_row('IDEM')]}
    first = session.records(body, idempotency_key=key, raw=True)
    require_equal(first.status_code, 200, 'the first request')
    second = session.records(body, idempotency_key=key, raw=True)
    require_equal(second.status_code, 200, 'the replay')
    require_equal(second.headers.get('Idempotent-Replayed'), 'true',
                  'the replay\'s Idempotent-Replayed header')
    require_equal(second.json(), first.json(), 'the replayed body vs the first answer')
    other = dict(body, records=[session.collar_row('IDEM')])
    reused = session.records(other, idempotency_key=key, raw=True)
    _refusal(session, reused, 'idempotency_key_reused', 409,
             'the same key with a different body')


@R.add('write.create_never_overwrites',
       'A `create` that meets an existing record with different values is `skipped` '
       '(`record_exists`), naming each conflicting field with both values — and the '
       'stored value does not move.')
def create_never_overwrites(session):
    row = session.collar_row('CONFLICT', total_depth=120.0)
    first = session.records({'model': PARENT, 'intent': 'create', 'records': [row]})
    row_id = first['rows'][0]['id']
    clash = session.records({'model': PARENT, 'intent': 'create',
                             'records': [dict(row, total_depth=150.0)]})
    out = clash['rows'][0]
    require_equal((out.get('status'), out.get('reason_code')), ('skipped', 'record_exists'),
                  'the conflicting create')
    conflicts = {c.get('field'): c for c in out.get('conflicts') or []}
    require('total_depth' in conflicts,
            f'the skip does not name the conflicting field: {out.get("conflicts")}')
    require(float(conflicts['total_depth'].get('existing')) == 120.0
            and float(conflicts['total_depth'].get('sent')) == 150.0,
            f'the conflict does not carry both values: {conflicts["total_depth"]}')
    stored = session.row(COLLAR_PATH, row_id)
    require(stored is not None and float(stored.get('total_depth')) == 120.0,
            f'the stored total_depth moved: {stored and stored.get("total_depth")}')


# ---------------------------------------------------------------------------
# Sets
# ---------------------------------------------------------------------------

@R.add('write.set_required',
       'An interval or sample write that names no set is refused `set_required` on '
       'every row, and the answer lists the project\'s sets so the agent can ask the '
       'user which one — the server never picks a set for an outside caller.')
def set_required(session):
    _hole_id, hole = session.new_hole('SETREQ')
    records = [{'bhid': hole, 'name': session.name('S'), 'depth_from': 0.0,
                'depth_to': 2.0}]
    body = session.records({'model': CHILD, 'intent': 'create', 'records': records})
    require_equal(_rows(body), [('refused', 'set_required')], 'a sample naming no set')
    require(isinstance(body.get('sets'), dict) and body['sets'],
            'the set_required answer lists no sets to choose from')


@R.add('write.set_not_owned',
       'A vendor key writing into a set it neither created nor was given is refused '
       '`set_not_owned` on every row; a set it creates in the same request is its own.')
def set_not_owned(session):
    sets = (session.describe(CHILD).get('set') or {}).get('sets') or []
    foreign = next((s for s in sets if s.get('writable_by_this_key') is False), None)
    if foreign is None:
        raise Skipped('every set in this project is writable by this key (a person\'s '
                      'own key, or a vendor key the customer ticked every set for)')
    _hole_id, hole = session.new_hole('NOTOWNED')
    records = [{'bhid': hole, 'name': session.name('S'), 'depth_from': 0.0,
                'depth_to': 2.0}]
    body = session.records({'model': CHILD, 'intent': 'create', 'set': foreign['name'],
                            'records': records})
    require_equal(_rows(body), [('refused', 'set_not_owned')],
                  f'a sample written into the set "{foreign["name"]}"')
    session.new_samples(hole, n=1)                   # a new set: the key's own


# ---------------------------------------------------------------------------
# Update + Undo
# ---------------------------------------------------------------------------

def _sample_fixture(session, label):
    _hole_id, hole = session.new_hole(label)
    ids, set_name, _body = session.new_samples(hole, n=2)
    return hole, ids, set_name


@R.add('write.update_changes_only_named_fields',
       '`update` overwrites exactly the fields it sends, on the record its `id` names; '
       'every other stored field is untouched.')
def update_changes_only_named_fields(session):
    _hole, ids, _set = _sample_fixture(session, 'UPD')
    before = session.row(SAMPLE_PATH, ids[0])
    body = session.records({'model': CHILD, 'intent': 'update',
                            'records': [{'id': ids[0], 'notes': 'conformance edit'}]})
    require_equal(_rows(body), [('updated', None)], 'the update')
    after = session.row(SAMPLE_PATH, ids[0])
    require_equal(after.get('notes'), 'conformance edit', 'the field the update named')
    for field in ('name', 'depth_from', 'depth_to'):
        require_equal(after.get(field), before.get(field), f'{field} (not named)')


@R.add('write.undo_restores_an_update',
       'Undo of an update restores every changed field to its old value, field for '
       'field, and says the undo is complete.')
def undo_restores_an_update(session):
    _hole, ids, _set = _sample_fixture(session, 'UNDOUPD')
    before = session.row(SAMPLE_PATH, ids[0])
    write = session.records({'model': CHILD, 'intent': 'update', 'records': [
        {'id': ids[0], 'notes': 'to be undone', 'depth_to': before['depth_to'] + 0.5}]})
    undo = session.undo(write['write_id'])
    require(undo.get('complete') is True, f'the undo is not complete: {undo.get("summary")}')
    after = session.row(SAMPLE_PATH, ids[0])
    for field in ('notes', 'depth_to', 'depth_from', 'name'):
        require_equal(after.get(field), before.get(field), f'{field} after the undo')


@R.add('write.undo_stale_refused_per_row',
       'Undo never overwrites a later change: a row another write changed since is '
       'refused `undo_stale` (naming that write) and keeps the later value.')
def undo_stale_refused_per_row(session):
    _hole, ids, _set = _sample_fixture(session, 'STALE')
    first = session.records({'model': CHILD, 'intent': 'update',
                             'records': [{'id': ids[0], 'notes': 'first edit'}]})
    session.records({'model': CHILD, 'intent': 'update',
                     'records': [{'id': ids[0], 'notes': 'later edit'}]})
    undo = session.undo(first['write_id'])
    hit = [r for r in undo.get('rows', []) if r.get('id') == ids[0]]
    require(hit, f'the undo does not report the row it could not undo: {undo.get("rows")}')
    require_equal((hit[0].get('status'), hit[0].get('reason_code')),
                  ('refused', 'undo_stale'), 'the row changed since')
    require(undo.get('complete') is False, 'an undo with a refused row says complete')
    require_equal(session.row(SAMPLE_PATH, ids[0]).get('notes'), 'later edit',
                  'the later value')


@R.add('write.already_undone',
       'A second undo of the same write is refused `already_undone` (409) — undo is '
       'never applied twice.')
def already_undone(session):
    body = session.records({'model': PARENT, 'intent': 'create',
                            'records': [session.collar_row('TWICE')]})
    session.undo(body['write_id'])
    _refusal(session, session.undo(body['write_id'], raw=True), 'already_undone', 409,
             'a second undo')


@R.add('write.undo_create_removes_the_rows',
       'Undo of a create removes every record it created: none of them can be read '
       'afterwards.')
def undo_create_removes_the_rows(session):
    hole_id, hole = session.new_hole('UNDOCREATE')
    ids, _set, samples = session.new_samples(hole, n=2)
    session.undo(samples['write_id'])
    for row_id in ids:
        require(session.row(SAMPLE_PATH, row_id) is None,
                f'sample {row_id} is still readable after its create was undone')
    require(session.row(COLLAR_PATH, hole_id) is not None,
            'the collar (a different write) went with the samples\' undo')
    collar_write = next(w for w in reversed(session.written)
                        if w != samples['write_id'])
    session.undo(collar_write)
    require(session.row(COLLAR_PATH, hole_id) is None,
            'the collar is still readable after its create was undone')


# ---------------------------------------------------------------------------
# Retract + restore
# ---------------------------------------------------------------------------

@R.add('write.retract_needs_confirm',
       'A retract without `"confirm": "retract"` is refused `confirm_required` and '
       'nothing moves to the Trash.')
def retract_needs_confirm(session):
    hole_id, hole = session.new_hole('NOCONFIRM')
    response = session.records({'model': PARENT, 'intent': 'retract',
                                'records': [{'name': hole}]}, raw=True)
    _refusal(session, response, 'confirm_required', 400, 'a retract without the confirm')
    require(session.row(COLLAR_PATH, hole_id) is not None,
            'the collar was retracted without the confirm')


@R.add('write.retract_cascades_and_undo_restores',
       'A retract moves the record AND everything that belongs to it to the Trash, '
       'counting them by model; undo of the retract brings every one of them back.')
def retract_cascades_and_undo_restores(session):
    hole_id, hole = session.new_hole('CASCADE')
    ids, _set, _b = session.new_samples(hole, n=2)
    body = session.records({'model': PARENT, 'intent': 'retract', 'confirm': 'retract',
                            'records': [{'name': hole}]})
    require_equal(_rows(body), [('retracted', None)], 'the retract')
    cascade = body.get('cascade') or {}
    require(int(cascade.get(CHILD) or 0) >= 2,
            f'the retract does not count the {CHILD} rows that went with it: {cascade}')
    gone = [session.row(COLLAR_PATH, hole_id)] + [session.row(SAMPLE_PATH, i) for i in ids]
    require(all(r is None for r in gone), 'a retracted record (or a child) is still readable')
    undo = session.undo(body['write_id'])
    require(undo.get('complete') is True, f'the undo of the retract: {undo.get("summary")}')
    back = [session.row(COLLAR_PATH, hole_id)] + [session.row(SAMPLE_PATH, i) for i in ids]
    require(all(r is not None for r in back),
            'undo of the retract did not bring every record back')


@R.add('write.restore_brings_a_batch_back',
       '`"intent": "restore"` with a retract\'s `audit_batch_id` brings that batch '
       'back from the Trash, as a write of its own — and undoing newest first '
       '(the restore, then the retract) brings everything back.')
def restore_brings_a_batch_back(session):
    hole_id, hole = session.new_hole('RESTORE')
    gone = session.records({'model': PARENT, 'intent': 'retract', 'confirm': 'retract',
                            'records': [{'name': hole}]})
    require(gone.get('audit_batch_id'), 'the retract answered no audit_batch_id')
    back = session.records({'intent': 'restore', 'audit_batch_id': gone['audit_batch_id']})
    statuses = [s for s, _c in _rows(back)]
    require(statuses and set(statuses) == {'restored'}, f'the restore rows: {_rows(back)}')
    require(back.get('write_id'), 'the restore is not a write of its own (no write_id)')
    require(session.row(COLLAR_PATH, hole_id) is not None,
            'the restored collar cannot be read')
    # Undo newest first, through the restore: the restore and its undo cancel
    # out, so the retract's undo brings the collar back, completely.
    session.undo(back['write_id'])
    require(session.row(COLLAR_PATH, hole_id) is None, 'undo of the restore left the collar')
    again = session.undo(gone['write_id'])
    require(again.get('complete') is True,
            f'undo of the retract, after the restore was undone: {_rows(again)}')
    require(session.row(COLLAR_PATH, hole_id) is not None,
            'undoing newest first did not bring the collar back')


# ---------------------------------------------------------------------------
# The one endpoint, the round trip, the refusals, the log
# ---------------------------------------------------------------------------

@R.add('write.resource_path_names_records_endpoint',
       'A write to a resource path (`POST /api/v2/drill-collars/`) is refused '
       '`use_records_endpoint`, and the answer carries the exact call to make instead.')
def resource_path_names_records_endpoint(session):
    response = session.post(COLLAR_PATH, json={'name': session.name('R9')},
                            note='a resource-path write')
    body = _refusal(session, response, 'use_records_endpoint', 403, 'a resource-path write')
    use = body.get('use') or {}
    require_equal((use.get('method'), use.get('path')), ('POST', '/api/v2/records/'),
                  'the call the refusal names')
    require_equal((use.get('body') or {}).get('model'), PARENT, 'the model it names')


@R.add('write.round_trip_is_a_no_op',
       'A record read from the API and written back unchanged is `unchanged` — same '
       'field names both ways, every read-only decoration ignored, never refused.')
def round_trip_is_a_no_op(session):
    extra = {}
    for field in session.describe(PARENT).get('fields') or []:
        if field.get('name') == 'hole_type' and field.get('choices'):
            extra['hole_type'] = field['choices'][0]       # a stored code, read as a label
    hole_id, hole = session.new_hole('ROUND', **extra)
    ids, _set, _b = session.new_samples(hole, n=1)
    for path, model, row_id in ((COLLAR_PATH, PARENT, hole_id), (SAMPLE_PATH, CHILD, ids[0])):
        record = session.row(path, row_id)
        for intent in ('update', 'upsert'):
            body = session.records({'model': model, 'intent': intent, 'records': [record]})
            require_equal(_rows(body), [('unchanged', None)],
                          f'a {model} read back and sent as {intent}')


#: Requests every write server refuses, each reaching a different refusal.
_REFUSAL_PROBES = (
    ('a body key the protocol does not have', {'model': PARENT, 'intent': 'create',
                                               'records': [{}], 'purge': True}),
    ('a model the endpoint does not take', {'model': '__conformance__', 'intent': 'create',
                                            'records': [{}]}),
    ('an intent it does not serve', {'model': PARENT, 'intent': 'hard_delete',
                                     'records': [{}]}),
    ('an undo naming no write', {'intent': 'undo',
                                 'write_id': '00000000-0000-0000-0000-000000000000'}),
)


@R.add('write.refusals_are_registered',
       'Every refusal a write can draw — for the request or for one row — carries a '
       '`reason_code` from the published registers (errors.json + the write profile), '
       'at the status the register gives it, with a remedy.')
def refusals_are_registered(session):
    registered = session.registered()
    problems, checked = [], 0

    def judge(label, code, status, remedy):
        nonlocal checked
        checked += 1
        if code not in registered:
            problems.append(f'{label}: reason_code {code!r} is in no published register')
        elif status is not None and registered[code].get('http') != status:
            problems.append(f'{label}: HTTP {status} with {code!r}, registered at '
                            f'{registered[code].get("http")}')
        if not remedy:
            problems.append(f'{label}: {code!r} carries no remedy')

    probes = list(_REFUSAL_PROBES)
    probes.append(('a batch over the cap', {
        'model': PARENT, 'intent': 'create', 'dry_run': True,
        'records': [{'name': f'x{i}'} for i in range(session.write_profile['batch_limit'] + 1)]}))
    for label, body in probes:
        response = session.records(body, raw=True)
        if response.status_code < 400:
            problems.append(f'{label}: answered {response.status_code}, not a refusal')
            continue
        try:
            payload = response.json()
        except ValueError:
            problems.append(f'{label}: {response.status_code} is not JSON')
            continue
        judge(label, payload.get('reason_code'), response.status_code, payload.get('remedy'))
    rows = session.records({'model': PARENT, 'intent': 'create', 'dry_run': True, 'records': [
        {k: v for k, v in session.collar_row('REG').items() if k != 'epsg'},
        dict(session.collar_row('REG'), not_a_field=1)]})
    for row in rows.get('rows', []):
        if row.get('status') == 'refused':
            judge(f'row {row.get("index")}', row.get('reason_code'), None, row.get('remedy'))
    require(checked >= len(probes) + 2, f'only {checked} refusals were drawn')
    require(not problems, 'refusals outside the published registers:\n'
            + '\n'.join(f'  {p}' for p in problems))


@R.add('write.writes_log_lists_writes_and_undos',
       '`GET /api/v2/records/writes/` lists what this key wrote, newest first — each '
       'with its undo handle — and an undo appears as a write naming what it undid.')
def writes_log_lists_writes_and_undos(session):
    body = session.records({'model': PARENT, 'intent': 'create',
                            'records': [session.collar_row('LOG')]})
    write_id = body['write_id']
    undo = session.undo(write_id)
    log = session.get_json(f'{WRITES}?limit=50', what='the writes log')
    for key in ('count', 'results'):
        require_in(key, log, 'the writes log envelope')
    by_id = {w.get('write_id'): w for w in log['results']}
    require(write_id in by_id, f'the write {write_id} is not in the log')
    require(undo.get('write_id') in by_id, 'the undo is not in the log as a write')
    require_equal(by_id[undo['write_id']].get('undo_of'), write_id, 'the undo\'s undo_of')
    require(by_id[write_id].get('undone_at'), 'the undone write shows no undone_at')
    detail = session.get_json(f'{WRITES}{write_id}/', what='one write')
    require_equal(detail.get('write_id'), write_id, 'the write detail')
    fresh = session.records({'model': PARENT, 'intent': 'create',
                             'records': [session.collar_row('LOG')]})
    listed = {w['write_id']: w for w in
              session.get_json(f'{WRITES}?limit=5', what='the writes log')['results']}
    handle = (listed.get(fresh['write_id']) or {}).get('undo') or {}
    require_equal(handle.get('write_id'), fresh['write_id'],
                  'the undo handle of a write not yet undone')
    if log['results'] and listed:
        newest = next(iter(listed))
        require_equal(newest, fresh['write_id'], 'the newest write is listed first')
    if not log['results']:
        raise Failed('the writes log is empty after two writes')
