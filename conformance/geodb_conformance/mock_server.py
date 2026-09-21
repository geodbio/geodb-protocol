"""
A deliberately breakable reference server, so every assertion can be shown to
fail before it is trusted to pass.

⭐ This is the acceptance instrument for the suite itself. A green
conformance run proves nothing unless each assertion has been watched to go
red for the one reason it exists. An assertion that cannot be made to fail is
not testing anything — it is a line in a report that will stay green through
the very regression it was written for.

So: this module serves a CORRECT implementation of the read half over
``http.server``, small but faithful (real envelope, real coordinate contract
with a projected CRS so the reprojection check has something to reproject,
real error bodies, a real export state machine, a real STAC tree with an
asset). Then ``--break <assertion-name>`` breaks it in exactly the one way
that assertion names, and nothing else.

The breakages are in ``BREAKAGES`` below: each is a one-line description of
the wrong behaviour, and the assertion it must turn red. ``selftest.py``
walks that table.

Run it standalone to poke at it:

    python -m geodb_conformance.mock_server --port 8765
    python -m geodb_conformance.mock_server --port 8765 --break envelope.paginated_list
"""

from __future__ import annotations

import copy
import datetime as dt
import json
import math
import re
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

PROTOCOL_VERSION = '0.1.0'
TOKEN = 'gdbg_mock_conformance_token'

#: EPSG:26915 (NAD83 / UTM 15N). The mock's collars are stored in it, exactly
#: as the real sandbox project is, because the coordinate assertions have to
#: have a projected CRS to be meaningful — on a 4326 project the whole native
#: coordinate trap is invisible and every check passes vacuously.
NATIVE_EPSG = 26915


# ---------------------------------------------------------------------------
# The breakage table — the acceptance matrix
# ---------------------------------------------------------------------------
#: ``name -> (assertion it must turn red, what the broken server does wrong)``
BREAKAGES = {
    'auth.header_accepted': (
        'auth.header_accepted',
        'grant-context omits `project`, so a client cannot learn what it is '
        'pinned to'),
    'auth.bearer_rejected': (
        'auth.bearer_rejected',
        'accepts `Authorization: Bearer <token>` as if it were a Grant'),
    'auth.401_shape': (
        'auth.401_shape',
        '401 answers bare prose with no reason_code'),
    'auth.www_authenticate': (
        'auth.www_authenticate',
        '401 omits the WWW-Authenticate: Grant header'),
    'auth.no_credential_refused': (
        'auth.no_credential_refused',
        'serves rows to a request carrying no credential at all'),
    'auth.malformed_header': (
        'auth.malformed_header',
        'a malformed Authorization header answers 500 instead of a coded 401'),
    'auth.write_refused': (
        'auth.write_refused',
        'accepts a POST to a record collection from a read-only grant'),
    'auth.v1_refused': (
        'auth.v1_refused',
        '/api/v1/ serves data to a grant instead of refusing with use_v2'),
    'auth.cross_project_is_404': (
        'auth.cross_project_is_404',
        'an out-of-scope row answers 403, revealing that the id is real'),
    'core.every_operation_reachable': (
        'core.every_operation_reachable',
        'a core list operation answers 404 — the published profile is not '
        'the profile served'),
    'core.retrieve_by_id': (
        'core.retrieve_by_id',
        'a row that was just listed cannot be retrieved by its own id'),
    'envelope.paginated_list': (
        'envelope.paginated_list',
        'a list drops the deletion-sync keys, so a mirror grows stale rows '
        'forever'),
    'envelope.limit_offset_paging': (
        'envelope.limit_offset_paging',
        'offset is ignored, so every page is page one'),
    'envelope.page_size_is_not_silently_honoured': (
        'envelope.page_size_is_not_silently_honoured',
        'honours an undeclared page_size AND reports a matching count, so the '
        'truncation is undetectable'),
    'envelope.only_cf_extra_keys': (
        'envelope.only_cf_extra_keys',
        'rows carry an undeclared internal key that is not a cf_ custom field'),
    'envelope.protocol_version_header': (
        'envelope.protocol_version_header',
        'the X-GeoDB-Protocol-Version header names a different version from '
        'the spec'),
    'envelope.grant_context_version_agrees': (
        'envelope.grant_context_version_agrees',
        'grant-context reports a protocol version the header contradicts'),
    'schema.every_row_validates': (
        'schema.every_row_validates',
        'a collar sends total_depth as a string, so the published schema '
        'rejects the row'),
    'schema.declared_types_hold': (
        'schema.declared_types_hold',
        'assay values are JSON numbers, silently rounding what the lab '
        'reported'),
    'coords.source_coordinate_present': (
        'coords.source_coordinate_present',
        'rows carry a location but no source_coordinate'),
    'coords.source_matches_scalars': (
        'coords.source_matches_scalars',
        'source_coordinate.x and .y are swapped relative to the scalars'),
    'coords.epsg_consistent_with_geometry': (
        'coords.epsg_consistent_with_geometry',
        'the derived WGS84 is a different point from the native coordinate '
        'reprojected — the customer\'s numbers have been lost'),
    'coords.geometry_is_ewkt_4326': (
        'coords.geometry_is_ewkt_4326',
        'geometry carries the native SRID instead of 4326'),
    'sync.modified_since_accepted': (
        'sync.modified_since_accepted',
        'no sync_timestamp comes back, so there is no cursor to persist'),
    'sync.modified_since_is_day_granular': (
        'sync.modified_since_is_day_granular',
        'the comparison narrows within the day, so a same-day cursor silently '
        'misses rows'),
    'sync.unparseable_is_refused': (
        'sync.unparseable_is_refused',
        'an unparseable modified_since is ignored and a full table scan is '
        'served to a client that asked for a delta'),
    'sync.deleted_since_semantics': (
        'sync.deleted_since_semantics',
        'deleted_since is accepted but deleted_since_applied never says it '
        'was applied'),
    'sync.deleted_ids_on_first_page': (
        'sync.deleted_ids_on_first_page',
        'the deletion feed is missing from the first page'),
    'stac.landing_is_1_1': (
        'stac.landing_is_1_1',
        'the STAC landing page declares no conformsTo'),
    'stac.conformance_link_differs_from_self': (
        'stac.conformance_link_differs_from_self',
        'the conformance link points back at the landing page'),
    'stac.asset_redirects_without_credential': (
        'stac.asset_redirects_without_credential',
        'the signed asset URL demands the grant token, forcing a client to '
        'hand its credential to storage'),
    'export.round_trip': (
        'export.round_trip',
        'an export job never leaves the queued state'),
    'export.download_needs_no_credential': (
        'export.download_needs_no_credential',
        'the finished export URL requires the grant header'),
    'export.refusals_carry_a_registered_code': (
        'export.refusals_carry_a_registered_code',
        'an export refusal answers bare {detail, allowed_models} prose with '
        'no reason_code'),
    'errors.every_4xx_is_registered': (
        'errors.every_4xx_is_registered',
        'a refusal invents an unregistered reason_code'),
    'errors.detail_is_not_the_contract': (
        'errors.detail_is_not_the_contract',
        'a parameter refusal names no offending parameter, forcing a client '
        'to parse prose'),
    'discovery.model_schemas_shape': (
        'discovery.model_schemas_shape',
        'model-schemas answers count without a matching models array'),
    'discovery.model_schemas_join_keys': (
        'discovery.model_schemas_join_keys',
        'record types omit api_endpoint, so discovery cannot join to data'),
    'discovery.natural_key_is_an_object': (
        'discovery.natural_key_is_an_object',
        'bhid is flattened to a bare string, so a spec-driven client reads '
        'the wrong type'),
    'discovery.grant_context_scope': (
        'discovery.grant_context_scope',
        'grant-context echoes the credential itself instead of its prefix'),
}

#: Assertions the mock cannot meaningfully break, with the reason. Kept
#: explicit so the matrix reports them rather than quietly covering 38 of 41.
UNBREAKABLE = {
    'errors.register_is_self_consistent':
        'asserts the PACKAGED errors.json, not the server — a server cannot '
        'break it, and the packaged file is checked by scripts/validate.py',
    'stac.extensions_resolve':
        'asserts that third-party schema URIs resolve on the public internet; '
        'a local mock cannot make spec.geodb.io fail or succeed',
    'export.concurrency_refusal_shape':
        'needs a real in-flight job cap to be reached; the mock finishes jobs '
        'immediately, and a mock that refused on demand would be asserting '
        'itself',
}


# ---------------------------------------------------------------------------
# Fixture data — small, but shaped exactly like the real wire
# ---------------------------------------------------------------------------

def _wgs84(easting, northing):
    """UTM 15N -> WGS84 without pyproj, good to well under a metre.

    A closed-form inverse transverse Mercator. The mock cannot depend on
    pyproj (the suite treats it as optional), but the coordinate assertion
    compares the mock's derived WGS84 against a pyproj reprojection — so the
    mock's own maths has to be right, or the check fails for the wrong reason.
    """
    a = 6378137.0
    f = 1 / 298.257222101            # GRS80 (NAD83)
    k0 = 0.9996
    e2 = f * (2 - f)
    ep2 = e2 / (1 - e2)
    lon0 = math.radians(-93.0)       # zone 15 central meridian

    x = easting - 500000.0
    y = northing
    m = y / k0
    e1 = (1 - math.sqrt(1 - e2)) / (1 + math.sqrt(1 - e2))
    mu = m / (a * (1 - e2 / 4 - 3 * e2 ** 2 / 64 - 5 * e2 ** 3 / 256))
    phi1 = (mu
            + (3 * e1 / 2 - 27 * e1 ** 3 / 32) * math.sin(2 * mu)
            + (21 * e1 ** 2 / 16 - 55 * e1 ** 4 / 32) * math.sin(4 * mu)
            + (151 * e1 ** 3 / 96) * math.sin(6 * mu)
            + (1097 * e1 ** 4 / 512) * math.sin(8 * mu))
    c1 = ep2 * math.cos(phi1) ** 2
    t1 = math.tan(phi1) ** 2
    n1 = a / math.sqrt(1 - e2 * math.sin(phi1) ** 2)
    r1 = a * (1 - e2) / (1 - e2 * math.sin(phi1) ** 2) ** 1.5
    d = x / (n1 * k0)

    lat = phi1 - (n1 * math.tan(phi1) / r1) * (
        d ** 2 / 2
        - (5 + 3 * t1 + 10 * c1 - 4 * c1 ** 2 - 9 * ep2) * d ** 4 / 24
        + (61 + 90 * t1 + 298 * c1 + 45 * t1 ** 2 - 252 * ep2
           - 3 * c1 ** 2) * d ** 6 / 720)
    lon = lon0 + (
        d
        - (1 + 2 * t1 + c1) * d ** 3 / 6
        + (5 - 2 * c1 + 28 * t1 - 3 * c1 ** 2 + 8 * ep2
           + 24 * t1 ** 2) * d ** 5 / 120) / math.cos(phi1)
    return math.degrees(lon), math.degrees(lat)


def _make_collars(count=4):
    rows = []
    for index in range(count):
        easting = 712671.5336718 + index * 180.0
        northing = 4189978.5209981 + index * 210.0
        elevation = 332.1369 + index
        lon, lat = _wgs84(easting, northing)
        rows.append({
            'id': 50728 + index,
            'name': f'SB-26-{index + 1:03d}',
            'project': {'name': 'Mock Sandbox (projected UTM 15N)',
                        'company': 'Mock Co'},
            'pad': None,
            'hole_type': 'Diamond Core',
            'hole_status': None,
            'hole_size': None,
            'date_completed': '2026-02-02',
            'total_depth': 253.3 + index,
            'total_depth_label': 'Final TD',
            'azimuth': 145.6,
            'dip': -62.4,
            'display_units': 'M',
            'latitude': northing,
            'longitude': easting,
            'epsg': NATIVE_EPSG,
            'elevation': elevation,
            'elevation_source': 'unknown',
            'length_units': 'Meters',
            'xy_units': 'meters',
            'crs_easting': round(lon, 7),
            'crs_northing': round(lat, 7),
            'crs_elevation': elevation,
            'crs_epsg': 4326,
            'crs_xy_units': 'degrees',
            'crs_elevation_units': 'M',
            'proj4_easting': None, 'proj4_northing': None,
            'proj4_elevation': None, 'proj4_string': None,
            'proj4_xy_units': None, 'proj4_elevation_units': None,
            'notes': None,
            'geometry': f'SRID=4326;POINT Z ({lon} {lat} {elevation})',
            'documents': [], 'images': [],
            'date_created': '2026-09-21',
            'last_edited': '2026-09-21',
            'source_coordinate': {'x': easting, 'y': northing,
                                  'epsg': NATIVE_EPSG},
            'geometry_geojson': {'type': 'Point',
                                 'coordinates': [lon, lat, elevation]},
            'coordinate_system_metadata': None,
        })
    return rows


#: The certificate object an assay row nests. Copied in SHAPE from the real
#: wire, not invented: a certificate reference is an object with a natural key,
#: not a bare string, and a mock that simplified it would let the schema
#: assertion pass here and fail against a real server.
CERTIFICATE = {
    'id': 2243,
    'name': 'MOCK-2026-0117',
    'laboratory': 'Mock Analytical',
    'analysis_date': '2026-03-14',
    'status': 'final',
    'date_preliminary': None,
    'natural_key': {'name': 'MOCK-2026-0117',
                    'project': 'Mock Sandbox (projected UTM 15N)',
                    'company': 'Mock Co'},
}

METHOD = {
    'id': 1219,
    'name': 'Mock FA-AAS',
    'laboratory': 'Mock Analytical',
    'is_floating_dl': False,
    'required_sample_mass_g': None,
    'natural_key': {'name': 'Mock FA-AAS', 'laboratory': 'Mock Analytical',
                    'company': 'Mock Co'},
}


def _make_drill_samples(collars):
    rows = []
    for index, collar in enumerate(collars):
        rows.append({
            'id': 262072 + index,
            'name': f'SB{index + 101:05d}',
            'project': {'name': 'Mock Sandbox (projected UTM 15N)',
                        'company': 'Mock Co'},
            'bhid': {'hole_id': collar['name'],
                     'project': 'Mock Sandbox (projected UTM 15N)',
                     'company': 'Mock Co'},
            'depth_from': 0.0 + index * 30,
            'depth_to': 30.0 + index * 30,
            'display_units': 'M',
            'xyz_from': None, 'xyz_to': None,
            'xyz_from_wgs84': None, 'xyz_to_wgs84': None,
            'images': [],
            'notes': None,
            'date_collected': None,
            'collected_by': None,
            'length_units': 'M',
            'lab_status': 'CO',
            'assay': None,
            'submittal': None,
            'submittal_name': None,
            'package_number': None,
            'drill_sample_set': {'id': 18, 'name': 'default',
                                 'kind': 'primary',
                                 'description': 'System default sampling pass'},
            'date_created': '2026-09-21',
            'last_edited': '2026-09-21',
        })
    return rows


def _element(symbol, value, units, detection_limit):
    return {
        'element': symbol,
        'value': value,                      # a decimal STRING, on purpose
        'units': units,
        'detection_limit': detection_limit,
        'upper_limit': None,
        'above_det_limit': True,
        'method': copy.deepcopy(METHOD),
        'certificate': {'id': CERTIFICATE['id'], 'name': CERTIFICATE['name'],
                        'laboratory': CERTIFICATE['laboratory']},
    }


def _make_assays(samples):
    rows = []
    for index, sample in enumerate(samples):
        rows.append({
            'id': 465008 + index,
            'name': sample['name'],
            'project': {'id': 1, 'name': 'Mock Sandbox (projected UTM 15N)',
                        'company': 'Mock Co'},
            'certificate': copy.deepcopy(CERTIFICATE),
            'weight': None,
            'detection_limit_per_sample': None,
            'precision_per_sample': None,
            'analyte_mass_g': None,
            'lab_status_code': '',
            'elements': [
                _element('Au', '5.5575', 'ppm', 0.005),
                _element('Cu', '145.3700', 'ppm', 1.0),
            ],
            'date_created': '2026-09-21',
            'qaqc_status': None,
        })
    return rows


COLLARS = _make_collars()
DRILL_SAMPLES = _make_drill_samples(COLLARS)
ASSAYS = _make_assays(DRILL_SAMPLES)

#: Core list path -> rows. Families with no fixture rows answer an empty list,
#: which the protocol explicitly permits ("you may serve an empty list for a
#: family you hold no data for").
COLLECTIONS = {
    '/api/v2/drill-collars/': COLLARS,
    '/api/v2/drill-samples/': DRILL_SAMPLES,
    '/api/v2/assays/': ASSAYS,
    '/api/v2/drill-surveys/': [],
    '/api/v2/drill-lithologies/': [],
    '/api/v2/drill-alterations/': [],
    '/api/v2/drill-structures/': [],
    '/api/v2/drill-mineralizations/': [],
    '/api/v2/drill-veins/': [],
    '/api/v2/drill-rqds/': [],
    '/api/v2/drill-spectral-intervals/': [],
    '/api/v2/drill-custom-intervals/': [],
    '/api/v2/point-samples/': [],
    '/api/v2/qc-samples/': [],
    '/api/v2/laboratories/': [],
    '/api/v2/certificates/': [],
}

MODEL_TYPES = [
    {'model_type': 'DrillCollar', 'display_name': 'Drill Collars',
     'api_endpoint': 'drill-collars', 'geometry_type': 'Point',
     'supports_push': False, 'supports_pull': True},
    {'model_type': 'DrillSample', 'display_name': 'Drill Samples',
     'api_endpoint': 'drill-samples', 'geometry_type': None,
     'supports_push': False, 'supports_pull': True},
    {'model_type': 'Assay', 'display_name': 'Assays',
     'api_endpoint': 'assays', 'geometry_type': None,
     'supports_push': False, 'supports_pull': True},
]

EXPORT_MODELS = ['drill_collars', 'drill_samples', 'point_samples']
EXPORT_FORMATS = ['geoparquet', 'parquet', 'csv']

ERROR_BODIES = {
    'grant_unknown': (401, {
        'reason_code': 'grant_unknown',
        'detail': 'Invalid or expired access grant.',
        'remedy': 'Check the credential. If it was never issued, ask the '
                  'project owner for an access grant. Do not retry as-is.',
        'grant_error': 'unknown'}),
    'grant_malformed': (401, {
        'reason_code': 'grant_malformed',
        'detail': 'The Authorization header is not a well-formed Grant header.',
        'remedy': "Send exactly 'Authorization: Grant <token>'.",
        'grant_error': 'malformed'}),
    'authentication_failed': (401, {
        'reason_code': 'authentication_failed',
        'detail': 'No usable credential was presented.',
        'remedy': 'Send `Authorization: Grant <token>` with a current grant.',
        'grant_error': 'unknown'}),
    'grant_write_forbidden': (403, {
        'reason_code': 'grant_write_forbidden',
        'detail': 'Access grants are read-only.',
        'remedy': 'Use a read operation. The one write a grant may make is '
                  'creating an export job (POST /api/v2/exports/).',
        'grant_error': 'grant_write_forbidden'}),
    'use_v2': (403, {
        'reason_code': 'use_v2',
        'detail': 'Access grants use the /api/v2/ surface only.',
        'remedy': 'Request the same path under /api/v2/.',
        'grant_error': 'use_v2'}),
    'grant_surface_forbidden': (403, {
        'reason_code': 'grant_surface_forbidden',
        'detail': 'The endpoint is not part of the grant-readable surface.',
        'remedy': 'Use an operation listed in the published OpenAPI spec '
                  '(/api/schema/).',
        'grant_error': 'grant_surface_forbidden'}),
    'not_found': (404, {
        'reason_code': 'not_found',
        'detail': 'No such resource inside this credential\'s scope.',
        'remedy': 'Check the id, and that it belongs to the project this '
                  'grant is pinned to (GET /api/v2/grant-context/).'}),
}


def _iso_date(value):
    """Parse a date or datetime; return a DATE (the contract is day-granular)."""
    text = (value or '').strip()
    if not text:
        raise ValueError('empty')
    try:
        return dt.date.fromisoformat(text[:10])
    except ValueError:
        return dt.datetime.fromisoformat(text.replace('Z', '+00:00')).date()


class MockHandler(BaseHTTPRequestHandler):
    broken = None                       # set on the server instance
    protocol_version = 'HTTP/1.1'

    # -- plumbing ---------------------------------------------------------
    def log_message(self, *args):
        pass                            # a conformance run must stay readable

    @property
    def breakage(self):
        return getattr(self.server, 'breakage', None)

    def _send(self, status, body=None, headers=None, raw=None):
        payload = raw if raw is not None else (
            json.dumps(body).encode() if body is not None else b'')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(payload)))
        version = PROTOCOL_VERSION
        if self.breakage == 'envelope.protocol_version_header':
            version = '9.9.9'
        self.send_header('X-GeoDB-Protocol-Version', version)
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        if payload:
            self.wfile.write(payload)

    def _error(self, code, **overrides):
        status, body = ERROR_BODIES[code]
        body = dict(body)
        body.update(overrides)
        headers = {}
        if status == 401:
            headers['WWW-Authenticate'] = 'Grant'
            if self.breakage == 'auth.www_authenticate':
                headers.pop('WWW-Authenticate')
            if self.breakage == 'auth.401_shape':
                body = {'detail': 'Authentication credentials were not '
                                  'provided.'}
        if self.breakage == 'errors.every_4xx_is_registered':
            body = dict(body, reason_code='mock_made_this_up')
        self._send(status, body, headers)

    def _authenticate(self):
        """Returns True when the request may proceed; answers the 401 if not."""
        header = self.headers.get('Authorization')
        if self.breakage == 'auth.no_credential_refused':
            return True
        if not header:
            self._error('authentication_failed')
            return False
        parts = header.split()
        if len(parts) != 2:
            if self.breakage == 'auth.malformed_header':
                self._send(500, {'detail': 'boom'})
                return False
            self._error('grant_malformed')
            return False
        scheme, token = parts
        if scheme.lower() != 'grant':
            if self.breakage == 'auth.bearer_rejected':
                return True             # wrongly accepts Bearer
            self._error('grant_malformed')
            return False
        if token != TOKEN:
            self._error('grant_unknown')
            return False
        return True

    def _guard(self, handler):
        """Turn an exception in the mock into a 500, not a dropped connection.

        BaseHTTPRequestHandler lets an exception propagate, which closes the
        socket mid-response; the suite then reports `RemoteDisconnected` on
        whichever assertion happened to be running. That is a mock bug wearing
        a server failure's clothes, and it cost a debugging cycle. A 500 with
        the traceback in the body says plainly whose fault it is.
        """
        try:
            handler()
        except Exception as exc:                            # noqa: BLE001
            import traceback
            try:
                self._send(500, {'mock_server_error': f'{type(exc).__name__}: '
                                                      f'{exc}',
                                 'traceback': traceback.format_exc()})
            except Exception:                                # noqa: BLE001
                pass

    # -- request routing --------------------------------------------------
    def do_GET(self):                                        # noqa: N802
        self._guard(self._do_get)

    def do_POST(self):                                       # noqa: N802
        self._guard(self._do_post)

    def _do_get(self):
        parsed = urlparse(self.path)
        path, query = parsed.path, parse_qs(parsed.query)
        if not path.endswith('/'):
            path += '/'

        if path.startswith('/api/v1/'):
            if not self._authenticate():
                return
            if self.breakage == 'auth.v1_refused':
                return self._send(200, {'count': 0, 'results': []})
            return self._error('use_v2')

        if path.startswith('/mock-storage/'):
            # The "signed URL" lane: self-authenticating by construction.
            if self.breakage in ('stac.asset_redirects_without_credential',
                                 'export.download_needs_no_credential'):
                if not self.headers.get('Authorization'):
                    return self._send(401, {'detail': 'credential required'})
            return self._send(200, raw=b'mock,asset,bytes\n',
                              headers={'Content-Type': 'text/csv'})

        if not self._authenticate():
            return

        if path == '/api/v2/grant-context/':
            return self._grant_context()
        if path == '/api/v2/model-schemas/':
            return self._model_schemas()
        if path.startswith('/api/v2/model-schemas/'):
            return self._model_schema_detail(path)
        if path.startswith('/api/v2/stac'):
            return self._stac(path)
        if path.startswith('/api/v2/exports/'):
            return self._export_get(path)
        if path == '/api/v2/projects/':
            return self._error('grant_surface_forbidden')

        if path in COLLECTIONS:
            if self.breakage == 'core.every_operation_reachable' \
                    and path == '/api/v2/certificates/':
                return self._error('not_found')
            return self._list(path, query)

        match = re.match(r'^(/api/v2/[a-z\-]+/)(\d+)/$', path)
        if match and match.group(1) in COLLECTIONS:
            return self._detail(match.group(1), int(match.group(2)))

        return self._error('not_found')

    def _do_post(self):
        parsed = urlparse(self.path)
        path = parsed.path if parsed.path.endswith('/') else parsed.path + '/'
        if not self._authenticate():
            return
        length = int(self.headers.get('Content-Length') or 0)
        try:
            payload = json.loads(self.rfile.read(length) or b'{}')
        except ValueError:
            payload = {}

        if path == '/api/v2/exports/':
            return self._export_create(payload)
        if path in COLLECTIONS:
            if self.breakage == 'auth.write_refused':
                return self._send(201, {'id': 999, 'name': payload.get('name')})
            return self._error('grant_write_forbidden')
        return self._error('not_found')

    # -- handlers ---------------------------------------------------------
    def _grant_context(self):
        body = {
            'protocol_version': PROTOCOL_VERSION,
            'label': 'Mock conformance grant',
            'token_prefix': TOKEN[:12],
            'project': {'id': 1, 'name': 'Mock Sandbox (projected UTM 15N)',
                        'code': 'MOCK123'},
            'company': {'id': 1, 'name': 'Mock Co'},
            'dataroom': None,
            'read_only': True,
            'expires_at': None,
            'throttle_rate': '2000/hour',
            'created': '2026-09-21',
            'last_used_at': '2026-09-21T00:00:00Z',
        }
        if self.breakage == 'auth.header_accepted':
            body.pop('project')
        if self.breakage == 'envelope.grant_context_version_agrees':
            body['protocol_version'] = '0.0.1'
        if self.breakage == 'discovery.grant_context_scope':
            body['token'] = TOKEN
        return self._send(200, body)

    def _model_schemas(self):
        models = copy.deepcopy(MODEL_TYPES)
        if self.breakage == 'discovery.model_schemas_join_keys':
            for entry in models:
                entry.pop('api_endpoint')
        body = {'count': len(models), 'models': models}
        if self.breakage == 'discovery.model_schemas_shape':
            body = {'count': len(models)}
        return self._send(200, body)

    def _model_schema_detail(self, path):
        model_type = path.rstrip('/').rsplit('/', 1)[-1]
        entry = next((m for m in MODEL_TYPES
                      if m['model_type'] == model_type), None)
        if entry is None:
            return self._error('not_found')
        return self._send(200, dict(entry, fields=[]))

    def _rows_for(self, path, query):
        """Apply the sync parameters, or refuse them, exactly as documented."""
        rows = copy.deepcopy(COLLECTIONS[path])

        for parameter in ('modified_since', 'deleted_since'):
            if parameter not in query:
                continue
            raw = query[parameter][0]
            try:
                cutoff = _iso_date(raw)
            except ValueError:
                if parameter == 'modified_since' \
                        and self.breakage == 'sync.unparseable_is_refused':
                    continue                      # wrongly ignores it
                body = {
                    'reason_code': 'invalid_parameter',
                    'detail': f'{parameter} is not an ISO 8601 date or '
                              f'datetime.',
                    'remedy': 'Send a date as YYYY-MM-DD, or a full ISO 8601 '
                              'timestamp.',
                    'offending': {'parameter': parameter, 'value': raw},
                }
                if self.breakage == 'errors.detail_is_not_the_contract':
                    body.pop('offending')
                if self.breakage == 'errors.every_4xx_is_registered':
                    body['reason_code'] = 'mock_made_this_up'
                self._send(400, body)
                return None
            if parameter == 'modified_since':
                if self.breakage == 'sync.modified_since_is_day_granular':
                    # Narrow WITHIN the day: a timestamp later than the row's
                    # own stamp drops it, which is the silent-miss failure.
                    moment = dt.datetime.fromisoformat(
                        raw.replace('Z', '+00:00')) \
                        if len(raw) > 10 else None
                    if moment is not None:
                        rows = [] if moment.hour >= 12 else rows
                        continue
                rows = [row for row in rows
                        if _iso_date(row.get('last_edited')
                                     or row.get('date_created')
                                     or '2026-09-21') >= cutoff]
        return rows

    def _list(self, path, query):
        rows = self._rows_for(path, query)
        if rows is None:
            return                                  # a refusal was sent
        total = len(rows)

        limit = int((query.get('limit') or [100])[0])
        offset = int((query.get('offset') or [0])[0])
        if 'page_size' in query \
                and self.breakage == 'envelope.page_size_is_not_silently_honoured':
            limit = int(query['page_size'][0])
        if self.breakage == 'envelope.limit_offset_paging':
            offset = 0

        page = rows[offset:offset + limit]

        if self.breakage == 'envelope.only_cf_extra_keys':
            for row in page:
                row['_internal_row_version'] = 7
        if self.breakage == 'schema.every_row_validates' \
                and path == '/api/v2/drill-collars/':
            for row in page:
                row['total_depth'] = str(row['total_depth'])
        if self.breakage == 'schema.declared_types_hold' \
                and path == '/api/v2/assays/':
            for row in page:
                for element in row['elements']:
                    element['value'] = float(element['value'])
        if path == '/api/v2/drill-collars/':
            for row in page:
                if self.breakage == 'coords.source_coordinate_present':
                    row.pop('source_coordinate', None)
                if self.breakage == 'coords.source_matches_scalars':
                    source = row['source_coordinate']
                    source['x'], source['y'] = source['y'], source['x']
                if self.breakage == 'coords.epsg_consistent_with_geometry':
                    lon, lat, elev = row['geometry_geojson']['coordinates']
                    lon += 0.01                     # ~900 m east
                    row['geometry_geojson']['coordinates'] = [lon, lat, elev]
                    row['geometry'] = f'SRID=4326;POINT Z ({lon} {lat} {elev})'
                if self.breakage == 'coords.geometry_is_ewkt_4326':
                    row['geometry'] = row['geometry'].replace(
                        'SRID=4326;', f'SRID={NATIVE_EPSG};')
        if path == '/api/v2/drill-samples/' \
                and self.breakage == 'discovery.natural_key_is_an_object':
            for row in page:
                row['bhid'] = row['bhid']['hole_id']

        next_url = None
        if offset + limit < total:
            next_url = (f'http://{self.headers.get("Host")}{path}'
                        f'?limit={limit}&offset={offset + limit}')
        previous_url = None
        if offset:
            previous_url = (f'http://{self.headers.get("Host")}{path}'
                            f'?limit={limit}&offset={max(offset - limit, 0)}')

        body = {
            'count': total,
            'next': next_url,
            'previous': previous_url,
            'results': page,
            'deleted_ids': [] if offset == 0 else [],
            'deleted_since_applied': (query['deleted_since'][0]
                                      if 'deleted_since' in query else None),
            'sync_timestamp': dt.datetime.now(dt.timezone.utc).isoformat(),
        }
        if self.breakage == 'envelope.paginated_list':
            for key in ('deleted_ids', 'deleted_since_applied',
                        'sync_timestamp'):
                body.pop(key)
        if self.breakage == 'envelope.page_size_is_not_silently_honoured' \
                and 'page_size' in query:
            body['count'] = len(page)
        if self.breakage == 'sync.modified_since_accepted':
            body.pop('sync_timestamp', None)
        if self.breakage == 'sync.deleted_since_semantics' \
                and 'deleted_since' in query:
            body['deleted_since_applied'] = None
        if self.breakage == 'sync.deleted_ids_on_first_page' and offset == 0:
            body.pop('deleted_ids')
        return self._send(200, body)

    def _detail(self, path, row_id):
        if self.breakage == 'core.retrieve_by_id':
            return self._error('not_found')
        for row in COLLECTIONS[path]:
            if row['id'] == row_id:
                return self._send(200, copy.deepcopy(row))
        if self.breakage == 'auth.cross_project_is_404':
            return self._send(403, {
                'reason_code': 'permission_denied',
                'detail': 'That row belongs to another project.',
                'remedy': 'Use a row in your own project.'})
        return self._error('not_found')

    # -- STAC -------------------------------------------------------------
    def _stac(self, path):
        host = f'http://{self.headers.get("Host")}'
        if path == '/api/v2/stac/':
            conformance_href = f'{host}/api/v2/stac/conformance/'
            if self.breakage == 'stac.conformance_link_differs_from_self':
                conformance_href = f'{host}/api/v2/stac/'
            body = {
                'type': 'Catalog',
                'stac_version': '1.1.0',
                'id': 'mock-project-1',
                'title': 'Mock catalog',
                'description': 'Mock STAC catalog for conformance self-test.',
                'conformsTo': [
                    'https://api.stacspec.org/v1.0.0/core',
                    'https://api.stacspec.org/v1.0.0/collections',
                    'https://api.stacspec.org/v1.0.0/ogcapi-features'],
                'links': [
                    {'rel': 'self', 'type': 'application/json',
                     'href': f'{host}/api/v2/stac/'},
                    {'rel': 'root', 'type': 'application/json',
                     'href': f'{host}/api/v2/stac/'},
                    {'rel': 'data', 'type': 'application/json',
                     'href': f'{host}/api/v2/stac/collections/'},
                    {'rel': 'conformance', 'type': 'application/json',
                     'href': conformance_href},
                ],
            }
            if self.breakage == 'stac.landing_is_1_1':
                body.pop('conformsTo')
            return self._send(200, body)

        if path == '/api/v2/stac/conformance/':
            return self._send(200, {'conformsTo': [
                'https://api.stacspec.org/v1.0.0/core',
                'https://api.stacspec.org/v1.0.0/collections',
                'https://api.stacspec.org/v1.0.0/ogcapi-features']})

        if path == '/api/v2/stac/collections/':
            return self._send(200, {'collections': [{
                'type': 'Collection',
                'stac_version': '1.1.0',
                'id': 'mock-grids',
                'title': 'Mock grids',
                'description': 'One collection with one item and one asset.',
                'license': 'other',
                'extent': {'spatial': {'bbox': [[-180.0, -90.0, 180.0, 90.0]]},
                           'temporal': {'interval': [[None, None]]}},
                'links': [
                    {'rel': 'self', 'type': 'application/json',
                     'href': f'{host}/api/v2/stac/collections/mock-grids/'},
                    {'rel': 'items', 'type': 'application/geo+json',
                     'href': f'{host}/api/v2/stac/collections/mock-grids/items/'},
                ],
            }]})

        if path == '/api/v2/stac/collections/mock-grids/items/':
            return self._send(200, {
                'type': 'FeatureCollection',
                'features': [{
                    'type': 'Feature',
                    'stac_version': '1.1.0',
                    'id': 'mock-item-1',
                    'collection': 'mock-grids',
                    # A real, resolvable extension URI. `stac.extensions_resolve`
                    # is a `full`-profile check that reaches the public
                    # internet; against the mock it either resolves (and the
                    # check passes) or the runner has no network (and the check
                    # SKIPS with that reason) — never a false red.
                    'stac_extensions': [
                        'https://stac-extensions.github.io/projection/v1.1.0/schema.json'],
                    'geometry': {'type': 'Point',
                                 'coordinates': [-90.58, 37.83]},
                    'bbox': [-90.59, 37.82, -90.57, 37.84],
                    'properties': {'datetime': '2026-09-21T00:00:00Z'},
                    'links': [],
                    'assets': {'data': {
                        'href': f'{host}/api/v2/stac/assets/grid/1/',
                        'type': 'application/octet-stream',
                        'roles': ['data']}},
                }],
            })

        if path.startswith('/api/v2/stac/assets/'):
            location = f'{host}/mock-storage/asset-1.csv'
            self.send_response(302)
            self.send_header('Location', location)
            self.send_header('Content-Length', '0')
            self.send_header('X-GeoDB-Protocol-Version', PROTOCOL_VERSION)
            self.end_headers()
            return
        return self._error('not_found')

    # -- exports ----------------------------------------------------------
    def _export_create(self, payload):
        model = (payload.get('model') or '').strip()
        fmt = (payload.get('format') or 'geoparquet').strip()
        host = f'http://{self.headers.get("Host")}'
        if model not in EXPORT_MODELS or fmt not in EXPORT_FORMATS:
            which = 'model' if model not in EXPORT_MODELS else 'format'
            if self.breakage == 'export.refusals_carry_a_registered_code':
                return self._send(400, {
                    'detail': f"Unsupported {which} '{model or fmt}'.",
                    'allowed_models': EXPORT_MODELS})
            return self._send(400, {
                'reason_code': 'validation_error',
                'detail': f"Unsupported {which} '{model or fmt}'.",
                'remedy': f'Choose a {which} this server exports; '
                          f'`offending` lists what is allowed.',
                'offending': {'parameter': which,
                              'value': model if which == 'model' else fmt,
                              'allowed': (EXPORT_MODELS if which == 'model'
                                          else EXPORT_FORMATS)}})
        job_id = str(uuid.uuid4())
        state = 'queued' if self.breakage == 'export.round_trip' else 'done'
        self.server.jobs[job_id] = {'state': state, 'model': model,
                                    'format': fmt}
        return self._send(202, {
            'id': job_id, 'state': 'queued', 'model': model, 'format': fmt,
            'status_url': f'{host}/api/v2/exports/{job_id}/',
            'reused': False})

    def _export_get(self, path):
        host = f'http://{self.headers.get("Host")}'
        # '/api/v2/exports/<id>/' and '/api/v2/exports/<id>/download/' ->
        # ['api', 'v2', 'exports', '<id>', ...], so the id is index 3.
        parts = path.strip('/').split('/')
        job_id = parts[3] if len(parts) > 3 else ''
        job = self.server.jobs.get(job_id)
        if job is None:
            return self._error('not_found', detail='Export not found.')
        if path.endswith('/download/'):
            location = f'{host}/mock-storage/{job_id}.csv'
            self.send_response(302)
            self.send_header('Location', location)
            self.send_header('Content-Length', '0')
            self.send_header('X-GeoDB-Protocol-Version', PROTOCOL_VERSION)
            self.end_headers()
            return
        body = {'state': job['state']}
        if job['state'] == 'done':
            body['download_url'] = f'{host}/api/v2/exports/{job_id}/download/'
            body['rows_total'] = len(COLLARS)
            body['elapsed_seconds'] = 1
        return self._send(200, body)


class MockServer(ThreadingHTTPServer):
    # Threading is load-bearing, not tidiness: the handler speaks HTTP/1.1, so
    # `requests` keeps the connection alive, and a single-threaded server
    # blocks on that idle connection instead of serving the next request. The
    # suite then hangs on its SECOND call, which looks like a slow server
    # rather than the mock's own plumbing.
    daemon_threads = True

    def __init__(self, address, breakage=None):
        super().__init__(address, MockHandler)
        self.breakage = breakage
        self.jobs = {}


def serve(port=0, breakage=None):
    """Start a mock in a background thread. Returns ``(server, base_url)``."""
    server = MockServer(('127.0.0.1', port), breakage=breakage)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f'http://127.0.0.1:{server.server_address[1]}'


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--break', dest='breakage', choices=sorted(BREAKAGES),
                        help='serve the protocol broken in exactly this one '
                             'way')
    args = parser.parse_args(argv)
    server, base = serve(args.port, args.breakage)
    print(f'mock server on {base}  token={TOKEN}'
          + (f'  BROKEN: {args.breakage}' if args.breakage else ''))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
