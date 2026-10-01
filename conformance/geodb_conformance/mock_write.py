"""
The WRITE half of the breakable reference server.

A small, faithful, in-memory implementation of the write profile — the one
records endpoint, describe, the key's write log, and R9 on a resource path —
so every write assertion can be watched to go red under exactly the one
breakage it exists to catch (``WRITE_BREAKAGES``) and green against a correct
server. ``mock_server.MockHandler`` routes here for the write key
(``WRITE_TOKEN``); the read half, its token and its data are untouched.

Two record types, as the suite writes them: collars (points, with the
coordinate rule) and drill samples (intervals in a SET). Undo is real: a
write records what it created, the old values of what it changed, and what it
retracted or restored, and an undo reverses exactly that — refusing a row a
later write changed (``undo_stale``).
"""

from __future__ import annotations

import copy
import itertools
import uuid

WRITE_TOKEN = 'gdbg_mock_conformance_WRITE_token'
PROJECT = {'id': 2, 'name': 'Mock Write Twin', 'code': 'MOCKW2'}
BATCH_LIMIT = 1000
INTENTS = ('create', 'upsert', 'update', 'retract', 'restore', 'make_default_set', 'undo')
BODY_KEYS = {'model', 'intent', 'records', 'project', 'set', 'logging_set', 'sample_set',
             'acknowledge', 'dry_run', 'confirm', 'audit_batch_id', 'write_id'}
HOLE_TYPES = {'DD': 'Diamond Core', 'RC': 'Reverse Circulation'}
COLLAR_FIELDS = ('name', 'latitude', 'longitude', 'epsg', 'total_depth', 'hole_type', 'notes')
SAMPLE_FIELDS = ('name', 'bhid', 'depth_from', 'depth_to', 'notes')
READ_ONLY = {'id', 'project', 'source_coordinate', 'geometry', 'geometry_geojson',
             'date_created', 'last_edited', 'display_units'}
MODELS = {'DrillCollar': 'collar', 'DrillSample': 'sample'}

#: ``breakage -> (the write assertion it must turn red, what goes wrong)``
WRITE_BREAKAGES = {
    'write.describe_serves_the_contract': (
        'write.describe_serves_the_contract',
        'describe omits the identifying fields, so an agent cannot tell a create '
        'from an update'),
    'write.dry_run_is_validate': (
        'write.dry_run_is_validate', 'a dry run writes the rows it validates'),
    'write.dry_run_is_validate:new_set': (
        'write.dry_run_is_validate',
        'a dry run into a set the request creates refuses every row the write would land'),
    'write.missing_crs_refused_per_row': (
        'write.missing_crs_refused_per_row',
        'a coordinate with no epsg is silently assumed to be WGS84'),
    'write.external_id_is_a_no_op': (
        'write.external_id_is_a_no_op',
        'a re-sent external_id creates a second record'),
    'write.idempotency_key_replays': (
        'write.idempotency_key_replays',
        'a repeated Idempotency-Key runs the write again instead of replaying it'),
    'write.create_never_overwrites': (
        'write.create_never_overwrites',
        'a create that meets an existing record overwrites it'),
    'write.set_required': (
        'write.set_required', 'a sample that names no set lands in the default set'),
    'write.set_not_owned': (
        'write.set_not_owned', 'a vendor key writes into the customer\'s own set'),
    'write.update_changes_only_named_fields': (
        'write.update_changes_only_named_fields',
        'an update blanks the depth it was not sent'),
    'write.undo_restores_an_update': (
        'write.undo_restores_an_update',
        'undo of an update says "undone" and leaves the new values'),
    'write.undo_stale_refused_per_row': (
        'write.undo_stale_refused_per_row',
        'undo overwrites a change a later write made'),
    'write.already_undone': (
        'write.already_undone', 'a second undo answers 200 again'),
    'write.undo_create_removes_the_rows': (
        'write.undo_create_removes_the_rows',
        'undo of a create leaves the records readable'),
    'write.retract_needs_confirm': (
        'write.retract_needs_confirm', 'a retract runs without its confirm'),
    'write.retract_cascades_and_undo_restores': (
        'write.retract_cascades_and_undo_restores',
        'undo of a retract brings the collar back but not its samples'),
    'write.restore_brings_a_batch_back': (
        'write.restore_brings_a_batch_back',
        'a restore answers "restored" and leaves the rows in the Trash'),
    'write.restore_brings_a_batch_back:undo_chain': (
        'write.restore_brings_a_batch_back',
        'undo of a retract is refused undo_stale once its restore was undone'),
    'write.resource_path_names_records_endpoint': (
        'write.resource_path_names_records_endpoint',
        'a resource-path write is refused without naming the records call'),
    'write.round_trip_is_a_no_op': (
        'write.round_trip_is_a_no_op',
        'a choice read as its label and written back counts as a change'),
    'write.refusals_are_registered': (
        'write.refusals_are_registered',
        'an oversized batch is refused with an unregistered code'),
    'write.writes_log_lists_writes_and_undos': (
        'write.writes_log_lists_writes_and_undos', 'the write log leaves out undos'),
}


def _err(code, detail, remedy, status, **extra):
    body = {'reason_code': code, 'detail': detail, 'remedy': remedy}
    body.update(extra)
    return status, body


class WriteStore:
    """One mock server's write state."""

    def __init__(self, breakage=None):
        self.breakage = breakage
        self.ids = itertools.count(70001)
        self.seq = itertools.count(1)
        self.rows = {'collar': {}, 'sample': {}}
        self.sets = {'default': {'id': 1, 'owned': False, 'default': True}}
        self.writes = []                     # newest last
        self.identities = {}                 # (model, external_id) -> id
        self.idempotency = {}                # key -> (fingerprint, status, body)

    # ---------------------------------------------------------------- reads
    def collar_view(self, row):
        lon, lat = row['longitude'], row['latitude']
        return {
            'id': row['id'], 'name': row['name'],
            'project': {'name': PROJECT['name'], 'company': 'Mock Co'},
            'latitude': lat, 'longitude': lon, 'epsg': row['epsg'],
            'total_depth': row.get('total_depth'),
            'hole_type': HOLE_TYPES.get(row.get('hole_type')) if row.get('hole_type') else None,
            'notes': row.get('notes'),
            'source_coordinate': {'x': lon, 'y': lat, 'epsg': row['epsg']},
            'geometry': f'SRID=4326;POINT Z ({lon} {lat} 0)',
            'geometry_geojson': {'type': 'Point', 'coordinates': [lon, lat, 0.0]},
            'date_created': '2026-10-01', 'last_edited': '2026-10-01',
        }

    def sample_view(self, row):
        return {
            'id': row['id'], 'name': row['name'],
            'project': {'name': PROJECT['name'], 'company': 'Mock Co'},
            'bhid': {'hole_id': row['bhid'], 'project': PROJECT['name'], 'company': 'Mock Co'},
            'depth_from': row['depth_from'], 'depth_to': row['depth_to'],
            'notes': row.get('notes'),
            'drill_sample_set': {'id': self.sets[row['set']]['id'], 'name': row['set'],
                                 'kind': 'primary', 'description': None},
            'display_units': 'M', 'date_created': '2026-10-01', 'last_edited': '2026-10-01',
        }

    def view(self, kind, row):
        return self.collar_view(row) if kind == 'collar' else self.sample_view(row)

    def live(self, kind):
        return [r for r in self.rows[kind].values() if not r['deleted']]

    def describe(self, model):
        if model not in MODELS:
            return _err('unsupported_model', f'No model {model!r}.',
                        'GET /api/v2/grant-context/ lists the models.', 400)
        kind = MODELS[model]
        fields = COLLAR_FIELDS if kind == 'collar' else SAMPLE_FIELDS
        body = {
            'model': model, 'intents': list(INTENTS),
            'identifying_fields': ['name'] if kind == 'collar' else ['name', 'bhid'],
            'fields': [dict({'name': f, 'type': 'text', 'required': f == 'name'},
                            **({'choices': list(HOLE_TYPES), 'choice_labels': HOLE_TYPES}
                               if f == 'hole_type' else {}))
                       for f in fields],
            'batch_limit': BATCH_LIMIT,
            'project': {'id': PROJECT['id'], 'name': PROJECT['name']},
        }
        if kind == 'sample':
            body['set'] = {'field': 'drill_sample_set', 'required': True, 'sets': [
                {'name': name, 'writable_by_this_key': s['owned'],
                 'is_project_default': s['default']} for name, s in self.sets.items()]}
        if self.breakage == 'write.describe_serves_the_contract':
            body.pop('identifying_fields')
        return 200, body

    def writes_log(self, write_id=None):
        writes = [w for w in reversed(self.writes)
                  if not (self.breakage == 'write.writes_log_lists_writes_and_undos'
                          and w['intent'] == 'undo')]

        def summary(w):
            return {'write_id': w['id'], 'model': w['model'], 'intent': w['intent'],
                    'summary': w['summary'], 'audit_batch_id': w['batch'],
                    'undone_at': w['undone_at'], 'undo_of': w['undo_of'],
                    'undone_by': list(w['undone_by']),
                    'undo': ({'intent': 'undo', 'write_id': w['id']}
                             if w['intent'] != 'undo' and not w['undone_at'] else None)}
        if write_id is not None:
            hit = next((w for w in writes if w['id'] == write_id), None)
            if hit is None:
                return _err('not_found', 'No such write by this key.',
                            'Use a write_id this key\'s writes returned.', 404)
            return 200, dict(summary(hit), rows=hit['rows'])
        return 200, {'count': len(writes), 'next': None, 'previous': None,
                     'results': [summary(w) for w in writes]}

    # --------------------------------------------------------------- writes
    def post(self, payload, idempotency_key=None):
        """Returns ``(status, body, headers)``."""
        if idempotency_key:
            fingerprint = repr(sorted(payload.items())) if isinstance(payload, dict) else ''
            seen = self.idempotency.get(idempotency_key)
            if seen is not None:
                if seen[0] != fingerprint:
                    status, body = _err('idempotency_key_reused',
                                        'This Idempotency-Key was used for a different request.',
                                        'Use a new Idempotency-Key for a different request.', 409)
                    return status, body, {}
                if self.breakage != 'write.idempotency_key_replays':
                    return seen[1], copy.deepcopy(seen[2]), {'Idempotent-Replayed': 'true'}
            status, body = self._post(payload)
            if status == 200:
                self.idempotency[idempotency_key] = (fingerprint, status, copy.deepcopy(body))
            return status, body, {}
        status, body = self._post(payload)
        return status, body, {}

    def _post(self, body):
        if not isinstance(body, dict):
            return _err('validation_error', 'The body must be a JSON object.',
                        'Send {"model", "intent", "records"}.', 400)
        unknown = sorted(set(body) - BODY_KEYS)
        if unknown:
            return _err('unknown_field', f'No body key(s) {unknown}.',
                        'Send only the keys the write profile names.', 400,
                        offending={'fields': unknown})
        intent = body.get('intent')
        if intent not in INTENTS:
            return _err('unsupported_intent', f'Intent {intent!r} is not served.',
                        'Use one of the intents describe lists.', 400)
        if intent == 'undo':
            return self.undo(body)
        if intent == 'restore':
            return self.restore(body)
        model = body.get('model')
        if model not in MODELS:
            return _err('unsupported_model', f'No model {model!r}.',
                        'GET /api/v2/grant-context/ lists the models.', 400)
        records = body.get('records')
        if not isinstance(records, list) or not records:
            return _err('validation_error', '"records" must be a non-empty list.',
                        'Send at least one record.', 400)
        if len(records) > BATCH_LIMIT:
            code = ('too_many_rows' if self.breakage == 'write.refusals_are_registered'
                    else 'batch_too_large')
            return _err(code, f'{len(records)} records; the limit is {BATCH_LIMIT}.',
                        'Split the batch.', 400)
        dry = bool(body.get('dry_run'))
        if intent == 'retract' and not dry and body.get('confirm') != 'retract' \
                and self.breakage != 'write.retract_needs_confirm':
            return _err('confirm_required', 'A retract needs "confirm": "retract".',
                        'Confirm with the user, then resend with "confirm": "retract".', 400)
        commit = not dry or self.breakage == 'write.dry_run_is_validate'
        snapshot = None if commit else copy.deepcopy(
            (self.rows, self.sets, self.identities, next(self.ids)))
        write = self._new_write(model, intent)
        cascade = {}
        rows = [self._row(MODELS[model], intent, i, rec, body, write, cascade)
                for i, rec in enumerate(records)]
        if not commit:
            self.rows, self.sets, self.identities, start = snapshot
            self.ids = itertools.count(start)
        landed = [r for r in rows if r['status'] in ('created', 'updated', 'retracted')]
        out = {'model': model, 'intent': intent, 'dry_run': dry, 'write_id': None,
               'audit_batch_id': None, 'summary': self._summary(rows), 'rows': rows}
        if intent == 'retract':
            out['cascade'] = cascade
        if any(r.get('reason_code') in ('set_required', 'set_not_owned') for r in rows):
            out['sets'] = {str(PROJECT['id']): [{'name': n, 'writable_by_this_key': s['owned']}
                                                for n, s in self.sets.items()]}
        if landed and not dry:
            write['summary'] = out['summary']
            write['rows'] = [{'index': r['index'], 'status': r['status'], 'id': r.get('id')}
                             for r in rows]
            self.writes.append(write)
            out.update(write_id=write['id'], audit_batch_id=write['batch'],
                       undo={'write_id': write['id'], 'available': True,
                             'request': {'intent': 'undo', 'write_id': write['id']}})
        return 200, out

    def _new_write(self, model, intent):
        return {'id': str(uuid.uuid4()), 'batch': str(uuid.uuid4()), 'model': model,
                'intent': intent, 'seq': next(self.seq), 'created': [], 'updated': [],
                'retracted': [], 'restored': [], 'undone_at': None, 'undo_of': None,
                'undone_by': [], 'summary': {}, 'rows': []}

    @staticmethod
    def _summary(rows):
        out = {}
        for row in rows:
            out[row['status']] = out.get(row['status'], 0) + 1
        return out

    def _touch(self, row, write):
        row['seq'], row['by'] = write['seq'], write['id']

    def _row(self, kind, intent, index, rec, body, write, cascade):
        out = {'index': index, 'external_id': None, 'project': PROJECT['id']}

        def refuse(code, detail, remedy, **extra):
            out.update(status='refused', reason_code=code, detail=detail, remedy=remedy)
            out.update(extra)
            return out
        if not isinstance(rec, dict):
            return refuse('validation_error', 'A record is an object.', 'Send an object.')
        rec = dict(rec)
        external = rec.pop('external_id', None)
        out['external_id'] = external
        fields = COLLAR_FIELDS if kind == 'collar' else SAMPLE_FIELDS
        set_ref = rec.pop('drill_sample_set', None) if kind == 'sample' else None
        unknown = [k for k in rec if k not in fields and k not in READ_ONLY]
        if unknown:
            return refuse('unknown_field', f'No field(s) {unknown}.',
                          'GET /api/v2/records/describe/<Model>/ lists the fields.')
        data = {k: v for k, v in rec.items() if k in fields}
        if isinstance(data.get('bhid'), dict):
            data['bhid'] = data['bhid'].get('hole_id')
        if isinstance(set_ref, dict) and 'create' not in set_ref:
            set_ref = set_ref.get('name')
        if kind == 'collar' and data.get('hole_type') in HOLE_TYPES.values() \
                and self.breakage != 'write.round_trip_is_a_no_op':
            data['hole_type'] = next(c for c, l in HOLE_TYPES.items() if l == data['hole_type'])

        if intent == 'retract':
            return self._retract(kind, rec, out, write, cascade, refuse)

        if kind == 'collar' and ('latitude' in data or 'longitude' in data):
            try:
                data['latitude'], data['longitude'] = (float(data['latitude']),
                                                       float(data['longitude']))
            except (TypeError, ValueError, KeyError):
                return refuse('invalid_geometry', 'The coordinates do not parse.',
                              'Send numbers.')
            if data.get('epsg') in (None, ''):
                if self.breakage != 'write.missing_crs_refused_per_row':
                    return refuse('missing_crs', 'Coordinates with no "epsg".',
                                  'Add "epsg": <code> to the row.', offending={'field': 'epsg'})
                data['epsg'] = 4326

        target = None
        if intent == 'update' and rec.get('id') is not None:
            target = self.rows[kind].get(rec['id'])
            if target is None or target['deleted']:
                return refuse('not_found', f'No live record {rec["id"]}.', 'Read the id again.')
        elif external is not None and self.breakage == 'write.external_id_is_a_no_op':
            target = None                    # broken: the identity is never looked up
        elif external is not None and (kind, external) in self.identities:
            target = self.rows[kind].get(self.identities[(kind, external)])
        else:
            target = self._match(kind, data)
        if target is not None and target['deleted']:
            target = None

        if kind == 'sample' and not (intent == 'update' and rec.get('id') is not None):
            ref = set_ref if set_ref is not None else body.get('set')
            if ref is None:
                if self.breakage != 'write.set_required':
                    return refuse('set_required', 'Name the set.',
                                  'ASK THE USER which set; the sets are listed in "sets".')
                ref = 'default'
            if isinstance(ref, dict):
                name = ref.get('name')
                if self.breakage == 'write.dry_run_is_validate:new_set' \
                        and body.get('dry_run'):
                    return refuse('interval_overlap', f'"{name}" is not an existing set.',
                                  'Name the kind of pass.')
                if name not in self.sets:
                    self.sets[name] = {'id': len(self.sets) + 1, 'owned': True, 'default': False}
                ref = name
            if ref not in self.sets:
                return refuse('set_required', f'No set "{ref}".',
                              'ASK THE USER which set; the sets are listed in "sets".')
            if not self.sets[ref]['owned'] and self.breakage != 'write.set_not_owned':
                return refuse('set_not_owned', f'This key may not write into "{ref}".',
                              'Create a new set with "set": {"name": …, "create": true}.')
            data['set'] = ref
            parent = self._match('collar', {'name': data.get('bhid')})
            if parent is None:
                return refuse('parent_not_found', f'No collar {data.get("bhid")!r}.',
                              'Create the collar first.')
            data['collar_id'] = parent['id']

        if target is None:
            if intent == 'update':
                return refuse('not_found', 'No record matches.', 'Send the geoDB id.')
            row = dict({k: None for k in fields if k != 'bhid'}, **data,
                       id=next(self.ids), deleted=False)
            self.rows[kind][row['id']] = row
            self._touch(row, write)
            write['created'].append((kind, row['id']))
            if external is not None:
                self.identities[(kind, external)] = row['id']
            out.update(status='created', id=row['id'])
            return out

        diffs = {k: v for k, v in data.items()
                 if k not in ('collar_id', 'set') and target.get(k) != v
                 and not (isinstance(v, (int, float)) and isinstance(target.get(k), (int, float))
                          and float(v) == float(target[k]))}
        out['id'] = target['id']
        if not diffs:
            out['status'] = 'unchanged'
            return out
        if intent == 'create' and self.breakage != 'write.create_never_overwrites':
            out.update(status='skipped', reason_code='record_exists',
                       detail='A create never overwrites.',
                       remedy='ASK THE USER, then resend with "intent": "upsert".',
                       conflicts=[{'field': k, 'existing': target.get(k), 'sent': v}
                                  for k, v in diffs.items()])
            return out
        old = {k: target.get(k) for k in diffs}
        old['seq'], old['by'] = target.get('seq'), target.get('by')   # undo puts the stamp back
        target.update(diffs)
        if intent == 'update' and self.breakage == 'write.update_changes_only_named_fields' \
                and kind == 'sample':
            old.setdefault('depth_to', target.get('depth_to'))
            target['depth_to'] = None
        self._touch(target, write)
        write['updated'].append((kind, target['id'], old))
        out['status'] = 'updated'
        return out

    def _match(self, kind, data):
        for row in self.rows[kind].values():
            if row['deleted'] or row['name'] != data.get('name'):
                continue
            if kind == 'sample' and data.get('bhid') not in (None, row['bhid']):
                continue
            return row
        return None

    def _retract(self, kind, rec, out, write, cascade, refuse):
        target = (self.rows[kind].get(rec['id']) if rec.get('id') is not None
                  else self._match(kind, rec))
        if target is None or target['deleted']:
            return refuse('not_found', 'No live record matches.', 'Read the id again.')
        target['deleted'] = True
        write['retracted'].append((kind, target['id'], (target.get('seq'), target.get('by'))))
        self._touch(target, write)
        model = 'DrillCollar' if kind == 'collar' else 'DrillSample'
        cascade[model] = cascade.get(model, 0) + 1
        children = 0
        if kind == 'collar':
            for child in self.live('sample'):
                if child['collar_id'] == target['id']:
                    child['deleted'] = True
                    write['retracted'].append(('sample', child['id'],
                                               (child.get('seq'), child.get('by'))))
                    self._touch(child, write)
                    children += 1
            if children:
                cascade['DrillSample'] = cascade.get('DrillSample', 0) + children
                out['children'] = {'DrillSample': children}
        out.update(status='retracted', id=target['id'])
        return out

    def restore(self, body):
        batch, wid = body.get('audit_batch_id'), body.get('write_id')
        write = next((w for w in self.writes if w['intent'] == 'retract'
                      and ((wid and w['id'] == wid) or (batch and w['batch'] == batch))),
                     None)
        if write is None:
            return _err('not_found', 'No retract with that audit_batch_id.',
                        'Use the audit_batch_id a retract returned.', 404)
        new = self._new_write(write['model'], 'restore')
        rows = []
        for i, (kind, pk, _stamp) in enumerate(write['retracted']):
            row = self.rows[kind][pk]
            if self.breakage != 'write.restore_brings_a_batch_back':
                row['deleted'] = False
            self._touch(row, new)
            new['restored'].append((kind, pk))
            rows.append({'index': i, 'status': 'restored', 'id': pk,
                         'model': 'DrillCollar' if kind == 'collar' else 'DrillSample'})
        new['summary'] = self._summary(rows)
        new['rows'] = rows
        self.writes.append(new)
        return 200, {'model': write['model'], 'intent': 'restore', 'dry_run': False,
                     'write_id': new['id'], 'audit_batch_id': new['batch'],
                     'summary': new['summary'], 'rows': rows}

    def undo(self, body):
        write = next((w for w in self.writes if w['id'] == body.get('write_id')), None)
        if write is None:
            return _err('not_found', 'No such write inside this key\'s reach.',
                        'Send the write_id a write returned.', 404)
        if write['undone_at'] and self.breakage != 'write.already_undone':
            return _err('already_undone', f'Write {write["id"]} was undone already.',
                        'Nothing to do; read the records.', 409)
        if write['undone_at']:
            return 200, {'intent': 'undo', 'undo_of': write['id'], 'write_id': None,
                         'summary': {'undone': 0}, 'complete': True, 'rows': []}
        undo = self._new_write(write['model'], 'undo')
        rows = []

        def done(kind, pk, status='undone', **extra):
            rows.append(dict({'model': 'DrillCollar' if kind == 'collar' else 'DrillSample',
                              'id': pk, 'status': status}, **extra))
        for kind, pk in write['created']:
            row = self.rows[kind][pk]
            if row['seq'] > write['seq'] and row.get('by') != write['id']:
                done(kind, pk, 'refused', reason_code='undo_stale',
                     remedy='Undo the later write first, or leave this row.')
                continue
            if self.breakage != 'write.undo_create_removes_the_rows':
                row['deleted'] = True
            done(kind, pk)
        for kind, pk, old in write['updated']:
            row = self.rows[kind][pk]
            if row['by'] != write['id'] and self.breakage != 'write.undo_stale_refused_per_row':
                done(kind, pk, 'refused', reason_code='undo_stale',
                     remedy='Undo the later write first, or leave this row.',
                     offending={'later_write_id': row['by']})
                continue
            if self.breakage != 'write.undo_restores_an_update':
                row.update(old)            # the values AND the stamp: an undo is neutral
            done(kind, pk)
        for kind, pk, stamp in write['retracted']:
            if self.breakage == 'write.restore_brings_a_batch_back:undo_chain' and any(
                    w['intent'] == 'restore' and (kind, pk) in w['restored']
                    for w in self.writes):
                done(kind, pk, 'refused', reason_code='undo_stale',
                     remedy='Undo the later write first.')
                continue
            if kind == 'sample' and self.breakage == 'write.retract_cascades_and_undo_restores':
                done(kind, pk)
                continue
            row = self.rows[kind][pk]
            row['deleted'] = False
            row['seq'], row['by'] = stamp
            done(kind, pk)
        for kind, pk in write['restored']:
            self.rows[kind][pk]['deleted'] = True
            done(kind, pk)
        refused = sum(1 for r in rows if r['status'] == 'refused')
        undo['summary'] = {'undone': len(rows) - refused, 'refused': refused, 'unchanged': 0}
        undo['rows'] = rows
        undo['undo_of'] = write['id']
        self.writes.append(undo)
        write['undone_by'].append(undo['id'])
        if not refused:
            write['undone_at'] = '2026-10-01T00:00:00Z'
        return 200, {'intent': 'undo', 'dry_run': False, 'undo_of': write['id'],
                     'write_id': undo['id'], 'audit_batch_id': undo['batch'],
                     'summary': undo['summary'], 'complete': not refused, 'rows': rows}

    # -------------------------------------------------------------------- R9
    def resource_write(self):
        if self.breakage == 'write.resource_path_names_records_endpoint':
            return _err('grant_write_forbidden', 'Access grants are read-only.',
                        'Use a read operation.', 403)
        return _err('use_records_endpoint',
                    'Records are written through ONE endpoint, not the resource paths.',
                    'POST /api/v2/records/ with {"model": "DrillCollar", "intent": "create", '
                    '"records": [ … ], "dry_run": true}.', 403,
                    use={'method': 'POST', 'path': '/api/v2/records/',
                         'body': {'model': 'DrillCollar', 'intent': 'create',
                                  'records': [], 'dry_run': True}})
