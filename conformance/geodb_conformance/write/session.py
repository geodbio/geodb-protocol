"""
The write session: the read session's transport and packaged contract, plus
the WRITE PROFILE and the bookkeeping a writing suite owes its target.

⭐ Like the read half, the contract travels with the runner:
``contract/write-profile.json`` (generated from the reference
implementation, versioned on its own) is what a server is checked against —
never anything the server says about itself.

Every row an assertion writes carries the run's id in its name
(``CONF-<run>-…``), so two runs never collide and a person can see what the
suite wrote; every write is remembered so the run can undo them all at the
end.
"""

from __future__ import annotations

import json
import uuid

from ..harness import Failed, Skipped
from ..session import Session, _package_file

#: The two record types the suite writes: a collar (a point, with the
#: coordinate rule) and a drill sample (an interval in a SET, with no
#: server-specific vocabulary to know in advance — a lithology would need the
#: project's rock list).
PARENT, CHILD = 'DrillCollar', 'DrillSample'
COLLAR_PATH, SAMPLE_PATH = '/api/v2/drill-collars/', '/api/v2/drill-samples/'
RECORDS = '/api/v2/records/'
DESCRIBE = '/api/v2/records/describe/{}/'
WRITES = '/api/v2/records/writes/'


class WriteSession(Session):
    """A :class:`Session` for a key that may write records."""

    def __init__(self, base_url, token, **kwargs):
        super().__init__(base_url, token, **kwargs)
        self.run_id = uuid.uuid4().hex[:8]
        self._serial = 0
        self._profile = None
        self._context = None
        #: Every write_id a write (not an undo) returned, oldest first.
        self.written: list[str] = []

    # -- the packaged write profile --------------------------------------
    @property
    def write_profile(self) -> dict:
        if self._profile is None:
            self._profile = json.loads(_package_file('write-profile.json'))
        return self._profile

    def registered(self) -> dict:
        """Every reason code a write may answer: the read registry the suite
        carries (``errors.json``) plus the write profile's own codes."""
        codes = dict(self.contract.reason_codes)
        codes.update(self.write_profile.get('reason_codes') or {})
        return codes

    # -- the target --------------------------------------------------------
    def context(self) -> dict:
        """``grant-context``, once. A key that cannot write is a setup error,
        not a server failure: every assertion skips, saying so."""
        if self._context is None:
            body = self.get_json('/api/v2/grant-context/', what='grant-context')
            if body.get('read_only', True):
                raise Skipped('this key is read-only (grant-context read_only: true); '
                              'the write suite needs a records-level key')
            self._context = body
        return self._context

    @property
    def project_id(self):
        project = self.context().get('project') or {}
        if project.get('id') is None:
            raise Skipped('grant-context names no project for this key to write into')
        return project['id']

    def name(self, label: str) -> str:
        """A name no other run (or assertion) uses."""
        self._serial += 1
        return f'CONF-{self.run_id}-{label}-{self._serial}'

    # -- the write endpoint ------------------------------------------------
    def records(self, body: dict, *, idempotency_key=None, note='', raw=False):
        """POST one records body. Returns the response (``raw``) or its JSON
        after requiring HTTP 200. Remembers every write_id for the clean-up."""
        headers = {}
        if idempotency_key:
            headers['Idempotency-Key'] = idempotency_key
        body = dict(body)
        if body.get('intent') not in ('undo', 'restore'):
            body.setdefault('project', self.project_id)
        response = self.post(RECORDS, json=body, headers=headers,
                             note=note or f'{body.get("intent")} {body.get("model", "")}')
        if raw:
            self._remember(response)
            return response
        if response.status_code != 200:
            raise Failed(f'POST {RECORDS} ({body.get("intent")} '
                         f'{body.get("model", "")}): expected HTTP 200, got '
                         f'{response.status_code}: {response.text[:400]!r}')
        self._remember(response)
        return self.json(response, 'the write response')

    def _remember(self, response):
        try:
            body = response.json()
        except ValueError:
            return
        if (isinstance(body, dict) and body.get('write_id')
                and body.get('intent') != 'undo' and not body.get('dry_run')):
            if body['write_id'] not in self.written:
                self.written.append(body['write_id'])

    def undo(self, write_id, *, raw=False, dry_run=False):
        response = self.post(RECORDS, json={'intent': 'undo', 'write_id': write_id,
                                            'dry_run': dry_run}, note='undo')
        if raw:
            return response
        if response.status_code != 200:
            raise Failed(f'undo of {write_id}: expected HTTP 200, got '
                         f'{response.status_code}: {response.text[:400]!r}')
        return self.json(response, 'the undo response')

    def describe(self, model):
        return self.get_json(DESCRIBE.format(model), what=f'describe {model}')

    # -- reading back ------------------------------------------------------
    def row(self, path, row_id):
        """The live record ``path`` + ``row_id``, or None when it is gone
        (a soft-deleted record answers 404 like any absent one)."""
        response = self.get(f'{path}{row_id}/', note='read back')
        if response.status_code == 404:
            return None
        if response.status_code != 200:
            raise Failed(f'GET {path}{row_id}/: expected 200 or 404, got '
                         f'{response.status_code}: {response.text[:300]!r}')
        return self.json(response, f'GET {path}{row_id}/')

    # -- fixtures every assertion builds for itself ------------------------
    def collar_row(self, label='H', **extra):
        row = {'name': self.name(label), 'latitude': 37.9, 'longitude': -91.0,
               'epsg': 4326, 'total_depth': 120.0}
        row.update(extra)
        return row

    def new_hole(self, label='H', **extra):
        """Create one collar; returns ``(id, name)``."""
        row = self.collar_row(label, **extra)
        body = self.records({'model': PARENT, 'intent': 'create', 'records': [row]})
        out = body['rows'][0]
        if out.get('status') != 'created':
            raise Failed(f'could not create a collar to work on: {out}')
        return out['id'], row['name']

    def new_set_name(self):
        return f'conformance {self.run_id} {self._next()}'

    def _next(self):
        self._serial += 1
        return self._serial

    def new_samples(self, hole_name, n=3, set_ref=None):
        """Create ``n`` samples down ``hole_name`` in a NEW set this key makes.
        Returns ``(ids, set_name, body)``."""
        set_name = set_ref or self.new_set_name()
        records = [{'bhid': hole_name, 'name': self.name('S'), 'depth_from': 2.0 * i,
                    'depth_to': 2.0 * i + 2.0} for i in range(n)]
        body = self.records({'model': CHILD, 'intent': 'create',
                             'set': {'name': set_name, 'create': True}
                             if set_ref is None else set_ref,
                             'records': records})
        statuses = [r.get('status') for r in body['rows']]
        if statuses != ['created'] * n:
            raise Failed(f'could not create {n} samples in a new set to work on: '
                         f'{[(r.get("status"), r.get("reason_code")) for r in body["rows"]]}')
        return [r['id'] for r in body['rows']], set_name, body

    # -- leaving the target as it was --------------------------------------
    def cleanup(self):
        """Undo every write this run made, newest first. Best effort: a write
        an assertion already undid answers already_undone, which is fine."""
        report = {'undone': 0, 'already': 0, 'failed': []}
        for write_id in reversed(self.written):
            try:
                response = self.undo(write_id, raw=True)
            except Exception as exc:                    # noqa: BLE001
                report['failed'].append(f'{write_id}: {exc}')
                continue
            code = None
            try:
                code = response.json().get('reason_code')
            except ValueError:
                pass
            if response.status_code == 200:
                report['undone'] += 1
            elif code in ('already_undone', 'not_undoable'):
                report['already'] += 1
            else:
                report['failed'].append(f'{write_id}: HTTP {response.status_code} {code}')
        return report
