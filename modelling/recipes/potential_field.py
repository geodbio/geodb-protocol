#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "numpy==2.2.5",
#     "scipy==1.16.2",
#     "scikit-image==0.25.2",
#     "pyarrow==24.0.0",
#     "gstlearn==1.11.1",
# ]
# ///
"""Reference recipe: a geological unit as a closed solid from its contacts and
logged orientations (potential-field kriging), filed with its run.

For a unit whose top (hanging wall) and base (footwall) are logged down the
holes and whose orientation is measured (bedding, foliation or vein walls
logged in the core): the contacts are two iso-potential families, the
measured planes give the field's gradient, and potential-field kriging
(gstlearn) interpolates one scalar field honouring both. The unit is the
volume between its two iso-values, drawn as one closed solid.

    pull the unit's logged intervals (top and base per intercept) and the
         oriented structures (dip, dip direction, position down the hole)
    -> contacts as two iso-potential families, gradients as upward normals
       turned into the project's local grid
    -> potential kriging on a coarse grid (unique neighbourhood), then exact
       evaluation again only in the cells that straddle a contact
    -> the closed solid between the two iso-values (marching cubes), clipped
       to the drilled volume when asked, its extrapolation distance stated
    -> checks read from the field's sign, never by ray casting
    -> one .glb in the project's local grid, Z up -> upload -> a MeshLayer

It is re-runnable as written: every setting comes from the parameters, every
input from the API pulls it makes, the key from the environment.

    export GEODB_SESSION_KEY=...        # or GEODB_TOKEN for a key of your own
    uv run potential_field.py parameters.json

``uv run`` builds the pinned environment from the header above. Offline, with
no key (an audit package):

    uv run potential_field.py parameters.json --inputs ./snapshot/ [--check-against manifest.json]

parameters.json, at least: {"project": 123, "unit": "Andesite"} (the unit's
lithology name or id as the lithology read gives it). Use it when the unit has
contacts AND orientations, or the user wants its uncertainty (simulations); a
single grade body with no orientations is the grade-shell recipe's job. The
result is an interpolated solid for visualisation, not a resource estimate.

gstlearn 1.11.1, measured in a chat sandbox (2 CPUs, 8 GB; rough): about 0.1 s
per equation and about four equations per contact, so the solve stays within
roughly 1,500 to 2,000 contacts (``max_points``; past that use a structural
modeller's finite-difference interpolator). It uses a CUBIC covariance (a
Gaussian one without a drift swings away from the data and is ill-conditioned
at long ranges), sets no drift (``setDriftIRF(1)`` makes the solve fail) and
never calls ``simulatePotential`` (it crashes the process in that version):
for uncertainty, condition simulations yourself and report P10 / P50 / P90
volumes. The potential field carries the unit on to the model box's edge, so
the run states how far the solid reaches from the nearest datum and can clip
it there (``clip_to_drilling``).
"""
import hashlib
import json
import math
import os
import platform
import re
import struct
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone

import numpy as np

RECIPE_VERSION = '1.0'

DEFAULTS = {
    'project': None,            # the project id (required)
    'unit': None,               # the unit's lithology, by name or id as the lithology read gives it (required)
    'set': None,                # the logging set of the lithology intervals, when the project has several
    'structure_types': None,    # only structures of these feature types (names), e.g. ["bedding"]; None = all
    'layer': None,              # an existing mesh layer id: file this run as its next version
    'name': None,               # the layer name (default: "<unit> solid")
    'made_by': None,
    'dry_run': False,
    'covariance': 'CUBIC',      # the only covariance taken: stable for potential kriging (see the docstring)
    'range': None,              # its range in grid units (default: the data's longest extent)
    'nugget_gradient': 0.0,     # the gradients' nugget (how loosely the field follows the measured planes)
    'max_points': 2000,         # contacts + orientations solved at once (unique neighbourhood); thinned above
    'clip_to_drilling': None,   # grid units: keep only the solid within this distance of a contact or orientation
    'grid_res': 48,             # coarse cells along the longest side of the model box
    'refine': 2,                # each straddling coarse cell is evaluated again this many times finer
    'margin': 10.0,             # padding around the data, in grid units
    'color': [86, 180, 233],
    'cutoff_confirmed_by': None,
}
MAX_MESH_BYTES = 104_857_600
MAX_TRIANGLES = 2_000_000
CAVEAT = ('An interpolated solid for visualisation, made by potential-field kriging of logged contacts and '
          'measured orientations. It is not a mineral resource estimate and carries no tonnage or grade claim.')
BASE = os.environ.get('GEODB_BASE_URL', 'https://api.geodb.io').rstrip('/')
SNAPSHOT_INDEX = 'inputs.json'
GRID_FIELDS = ['crs_epsg', 'origin_x', 'origin_y', 'rotation_degrees']
LITH_FIELDS = ['id', 'bhid', 'depth_from', 'depth_to', 'xyz_from', 'xyz_to', 'lithology']
STRUCTURE_FIELDS = ['id', 'bhid', 'depth_at', 'xyz_at', 'dip', 'dip_direction', 'feature_type']
LOG = []



# --------------------------------------------------------------------------- #
# The API, the snapshot, the environment, the file (as the grade-shell recipe) #
# --------------------------------------------------------------------------- #
def _auth():
    key = os.environ.get('GEODB_SESSION_KEY') or os.environ.get('GEODB_TOKEN')
    if not key:
        raise SystemExit('Set GEODB_SESSION_KEY (or GEODB_TOKEN) in the environment; never write a key into a '
                         'recipe.')
    return {'Authorization': 'Grant ' + key}          # the scheme is Grant for every geoDB key


def call(method, url, body=None, headers=None, raw=None):
    data = raw if raw is not None else (json.dumps(body).encode('utf-8') if body is not None else None)
    request = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            text = response.read()
    except urllib.error.HTTPError as error:
        text = error.read()
        try:
            answer = json.loads(text)
        except ValueError:
            answer = {'detail': text[:300].decode('utf-8', 'replace')}
        raise SystemExit(f'{method} {url.split("?")[0]} answered {error.code} {answer.get("reason_code", "")}: '
                         f'{answer.get("detail", "")}\n  remedy: {answer.get("remedy", "")}') from None
    try:
        return json.loads(text) if text else {}
    except ValueError:                      # a storage host answers a block PUT with no JSON
        return {}


def api(path, **params):
    query = ('?' + urllib.parse.urlencode(params)) if params else ''
    return call('GET', f'{BASE}/api/v2/{path}{query}', headers=_auth())


def pull(path, **params):
    """Every row of a list, following ``next`` to the end."""
    rows, url = [], f'{BASE}/api/v2/{path}?' + urllib.parse.urlencode({'limit': 500, **params})
    while url:
        page = call('GET', url, headers=_auth())
        rows.extend(page['results'])
        url = page.get('next')
    return rows


def write(body, key=None):
    headers = {**_auth(), 'Content-Type': 'application/json'}
    if key:
        headers['Idempotency-Key'] = key
    answer = call('POST', f'{BASE}/api/v2/records/', body=body, headers=headers)
    row = answer['rows'][0]
    if row['status'] == 'refused':
        raise SystemExit(f'{body["model"]} {body["intent"]} was refused: {row.get("reason_code")}: '
                         f'{row.get("detail")}\n  remedy: {row.get("remedy")}\n  {json.dumps(row.get("offending"))}')
    return answer, row


def fingerprint(rows, fields):
    """The fingerprint of a pull, by the model-run contract's one rule: keep
    only ``fields`` of each row; write each row as JSON with sorted keys, no
    whitespace and non-ASCII escaped; sort those texts; join them with ","
    inside "[" "]"; SHA-256 of that text. The same pull on unchanged data
    gives the same value, in any language."""
    return fingerprint_of_texts(row_texts(rows, fields))


def row_texts(rows, fields):
    """Each row reduced to ``fields`` as the rule writes it, sorted: the
    fingerprint's own texts, and what a snapshot stores."""
    return sorted(json.dumps({k: row.get(k) for k in fields}, sort_keys=True, separators=(',', ':'),
                             ensure_ascii=True) for row in rows)


def fingerprint_of_texts(texts):
    return hashlib.sha256(('[' + ','.join(texts) + ']').encode('utf-8')).hexdigest()


def write_snapshot(folder, index, item, texts):
    """Keep one pull as ``<folder>/<n>-<read>.parquet``: one text column
    ``row``, each row as the fingerprint rule writes it, so the file gives
    back the recorded fingerprint and the very rows the recipe computed on."""
    import pyarrow as pa
    import pyarrow.parquet as pq
    os.makedirs(folder, exist_ok=True)
    slug = re.sub(r'[^a-z0-9]+', '-', (item.get('read') or item['what']).lower()).strip('-')[:40] or 'pull'
    name = f'{index}-{slug}.parquet'
    pq.write_table(pa.table({'row': pa.array(texts, type=pa.string())}), os.path.join(folder, name),
                   compression='zstd')
    return name


def read_snapshot(folder):
    """The pulls of an earlier run, from its snapshot. Each file must give
    the fingerprint the run recorded, or nothing is built."""
    import pyarrow.parquet as pq
    with open(os.path.join(folder, SNAPSHOT_INDEX), encoding='utf-8') as handle:
        inputs = json.load(handle)
    pulls = []
    for item in inputs:
        texts = sorted(pq.read_table(os.path.join(folder, item['snapshot'])).column('row').to_pylist())
        found = fingerprint_of_texts(texts)
        if found != item.get('fingerprint'):
            raise SystemExit(f'The snapshot file {item["snapshot"]} gives fingerprint {found}, but the run recorded '
                             f'{item.get("fingerprint")}: it is not the data the run used. Nothing was built.')
        pulls.append([json.loads(text) for text in texts])
    return inputs, pulls


def now():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def drop_speckle(vertices, faces, smallest):
    """Keep the connected pieces of at least ``smallest`` triangles."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    edges = np.vstack([faces[:, [0, 1]], faces[:, [1, 2]]])
    graph = coo_matrix((np.ones(len(edges)), (edges[:, 0], edges[:, 1])), shape=(len(vertices),) * 2)
    count, label = connected_components(graph, directed=False)
    face_label = label[faces[:, 0]]
    sizes = np.bincount(face_label, minlength=count)
    pieces = int(np.count_nonzero(sizes))
    keep = np.flatnonzero(sizes >= smallest)
    if len(keep) == 0:                      # every piece is small: keep the largest rather than nothing
        keep = np.array([int(sizes.argmax())])
    faces = faces[np.isin(face_label, keep)]
    used = np.unique(faces)
    remap = np.full(len(vertices), -1, dtype=np.int64)
    remap[used] = np.arange(len(used))
    return vertices[used], remap[faces], pieces, int(len(keep))


def outward(vertices, faces):
    """Triangles wound so the enclosed volume is positive."""
    a, b, c = (vertices[faces[:, i]] for i in range(3))
    volume = float(np.einsum('ij,ij->i', a, np.cross(b, c)).sum() / 6.0)
    return (faces[:, ::-1], -volume) if volume < 0 else (faces, volume)


def write_glb(vertices, faces, color):
    """One self-contained binary glTF 2: plain geometry, a material colour, no
    node transform, positions written as computed (local grid, Z up)."""
    positions = np.ascontiguousarray(vertices, dtype='<f4')
    indices = np.ascontiguousarray(faces, dtype='<u4').ravel()
    blob = positions.tobytes() + indices.tobytes()
    blob += b'\0' * (-len(blob) % 4)
    document = {
        'asset': {'version': '2.0', 'generator': f'geoDB reference grade-shell recipe {RECIPE_VERSION}'},
        'scene': 0, 'scenes': [{'nodes': [0]}], 'nodes': [{'mesh': 0}],
        'meshes': [{'primitives': [{'attributes': {'POSITION': 0}, 'indices': 1, 'material': 0, 'mode': 4}]}],
        'materials': [{'pbrMetallicRoughness': {'baseColorFactor': [c / 255.0 for c in color] + [1.0],
                                                'metallicFactor': 0.0, 'roughnessFactor': 0.9},
                       'doubleSided': True}],
        'accessors': [
            {'bufferView': 0, 'componentType': 5126, 'count': int(len(positions)), 'type': 'VEC3',
             'min': [float(v) for v in positions.min(axis=0)], 'max': [float(v) for v in positions.max(axis=0)]},
            {'bufferView': 1, 'componentType': 5125, 'count': int(len(indices)), 'type': 'SCALAR'}],
        'bufferViews': [{'buffer': 0, 'byteOffset': 0, 'byteLength': positions.nbytes, 'target': 34962},
                        {'buffer': 0, 'byteOffset': positions.nbytes, 'byteLength': indices.nbytes, 'target': 34963}],
        'buffers': [{'byteLength': len(blob)}],
    }
    text = json.dumps(document, separators=(',', ':')).encode('utf-8')
    text += b' ' * (-len(text) % 4)
    body = struct.pack('<II', len(text), 0x4E4F534A) + text + struct.pack('<II', len(blob), 0x004E4942) + blob
    return b'glTF' + struct.pack('<II', 2, 12 + len(body)) + body


def upload(p, glb, file_name, category='3D'):
    """A file as a project file: upload_start, PUT the blocks, upload_commit."""
    _answer, started = write({'model': 'ProjectFile', 'intent': 'upload_start', 'dry_run': False, 'records': [
        {'project': p['project'], 'file_name': file_name, 'size': len(glb), 'category': category,
         'name': file_name.rsplit('.', 1)[0]}]})
    plan = started['result']
    for block in plan['blocks']:
        url = block.get('url') or plan['put']['url_template'].replace('{block_id}', urllib.parse.quote(block['id']))
        # Only the storage host is contacted here; no key goes with a block.
        call('PUT', url, raw=glb[block['offset']:block['offset'] + block['length']],
             headers={'Content-Type': 'application/octet-stream'})
    _answer, committed = write(plan['commit'] | {'dry_run': False}, key=str(uuid.uuid4()))
    return committed['result']['id']


def pinned():
    """``{package: version}`` from this file's own pinned header (PEP 723)."""
    import tomllib
    with open(os.path.abspath(__file__), encoding='utf-8') as handle:
        text = handle.read()
    block = re.search(r'(?m)^# /// script\s*$\n((?:^#(?: .*)?$\n)+?)^# ///\s*$', text)
    if not block:
        return {}
    meta = tomllib.loads(''.join(line[2:] + '\n' for line in block.group(1).splitlines()))
    out = {}
    for dep in meta.get('dependencies', []):
        name, _, version = dep.partition('==')
        out[name.strip()] = version.strip()
    return out


def environment():
    """The interpreter and the INSTALLED version of every package the header
    pins (the only third-party packages this recipe imports)."""
    from importlib import metadata
    packages = {}
    for name in pinned():
        try:
            packages[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            packages[name] = 'not installed'
    return {'python': platform.python_version(), 'platform': platform.system(), 'packages': packages}


def environment_check(env):
    wanted = pinned()
    off = {name: (wanted[name], env['packages'].get(name)) for name in wanted
           if env['packages'].get(name) != wanted[name]}
    return {'name': 'environment_matches_header', 'pass': not off,
            'detail': ('every package is the version the header pins' if not off else
                       'installed versions differ from the header: '
                       + ', '.join(f'{n} {have} (pinned {want})' for n, (want, have) in sorted(off.items()))
                       + '; run it with `uv run` to get the pinned environment')}


def say(line):
    LOG.append(line)
    sys.stderr.write(line + '\n')


def arguments(argv):
    """``parameters.json [--inputs FOLDER] [--check-against manifest.json]``."""
    args, options = [], {'inputs': None, 'check_against': None}
    rest = list(argv[1:])
    while rest:
        word = rest.pop(0)
        if word in ('--inputs', '--check-against'):
            if not rest:
                raise SystemExit(f'{word} needs a path.')
            options[word[2:].replace('-', '_')] = rest.pop(0)
        else:
            args.append(word)
    return args, options



# --------------------------------------------------------------------------- #
# The data                                                                      #
# --------------------------------------------------------------------------- #
def pull_inputs(p, snapshot=None):
    """The project grid, the logged lithology intervals and the oriented
    structures, each pull reduced to its fingerprinted fields in the rule's
    order (online and offline the recipe sees the same rows)."""
    project = p['project']
    lith_filters = {'project_id': project, **({'set': p['set']} if p['set'] is not None else {})}
    inputs = [
        {'what': 'the project local grid', 'read': f'projects/{project}/coordinate-system/', 'filters': {},
         'fields': GRID_FIELDS},
        {'what': 'logged lithology intervals with desurveyed positions on the local grid',
         'read': 'drill-lithologies/', 'filters': lith_filters, 'fields': LITH_FIELDS},
        {'what': 'oriented structures logged down the holes (dip, dip direction, position)',
         'read': 'drill-structures/', 'filters': {'project_id': project}, 'fields': STRUCTURE_FIELDS},
    ]
    if snapshot:
        recorded, pulls = read_snapshot(snapshot)
        if [i.get('read') for i in recorded] != [i['read'] for i in inputs]:
            raise SystemExit('The snapshot holds other pulls than this recipe makes; nothing was built.')
        for item, done in zip(inputs, recorded, strict=True):
            item.update({k: done[k] for k in ('filters', 'rows', 'fingerprint', 'pulled_at', 'snapshot') if k in done})
        texts = [row_texts(rows, item['fields']) for rows, item in zip(pulls, inputs, strict=True)]
    else:
        grid = api(f'projects/{project}/coordinate-system/').get('coordinate_system')
        if not grid:
            raise SystemExit('This project has no local grid a solid can be placed in. Tell the user; nothing '
                             'was built.')
        pulled = [[grid], pull('drill-lithologies/', **lith_filters), pull('drill-structures/', project_id=project)]
        texts = []
        for item, rows in zip(inputs, pulled, strict=True):
            texts.append(row_texts(rows, item['fields']))
            item.update({'rows': len(rows), 'fingerprint': fingerprint_of_texts(texts[-1]), 'pulled_at': now()})
    grid_rows, liths, structures = ([json.loads(t) for t in group] for group in texts)
    return grid_rows[0], liths, structures, inputs, texts


def _named(value, wanted):
    """Does a lithology as a read gives it (an id, a name, or {id, name})
    match ``wanted`` (a name, case-insensitive, or an id)?"""
    wanted = str(wanted).strip().lower()
    if isinstance(value, dict):
        return wanted in {str(value.get('id')), str(value.get('name') or '').strip().lower()}
    return value is not None and str(value).strip().lower() == wanted


def _hole(row):
    bhid = row.get('bhid')
    return json.dumps(bhid.get('id') if isinstance(bhid, dict) else bhid)


def contacts(p, liths):
    """``(points[n, 3], family[n], inside[m, 3], outside[k, 3])``: the top
    (family 1, hanging wall) and base (family 2, footwall) of each intercept
    of the unit, and the mid-points of the unit's intervals and of every
    other interval (for the checks)."""
    by_hole, inside, outside = {}, [], []
    for row in liths:
        a, b = row.get('xyz_from'), row.get('xyz_to')
        if not (isinstance(a, list) and isinstance(b, list) and len(a) == 3 and len(b) == 3):
            continue
        middle = [(x + y) / 2.0 for x, y in zip(a, b, strict=True)]
        if _named(row.get('lithology'), p['unit']):
            by_hole.setdefault(_hole(row), []).append(row)
            inside.append(middle)
        else:
            outside.append(middle)
    points, family = [], []
    for rows in by_hole.values():
        rows.sort(key=lambda r: r['depth_from'])
        run = [rows[0]]
        for row in rows[1:] + [None]:
            if row is not None and row['depth_from'] <= run[-1]['depth_to'] + 1e-6:
                run.append(row)
                continue
            points += [run[0]['xyz_from'], run[-1]['xyz_to']]
            family += [1, 2]
            run = [row] if row is not None else []
    return (np.array(points, float).reshape(-1, 3), np.array(family, float), np.array(inside, float).reshape(-1, 3),
            np.array(outside, float).reshape(-1, 3))


def gradients(p, structures, rotation):
    """``(points[n, 3], normals[n, 3])``: each measured plane's upward unit
    normal in the project's local grid. Dip directions are azimuths from
    true north; the grid is turned ``rotation`` degrees clockwise, so the
    direction in the grid is the dip direction minus the rotation."""
    kinds = {str(k).strip().lower() for k in (p['structure_types'] or [])}
    points, normals = [], []
    for row in structures:
        at, dip, direction = row.get('xyz_at'), row.get('dip'), row.get('dip_direction')
        if not (isinstance(at, list) and len(at) == 3) or dip is None or direction is None:
            continue
        kind = row.get('feature_type')
        kind = (kind.get('name') if isinstance(kind, dict) else kind) or ''
        if kinds and str(kind).strip().lower() not in kinds:
            continue
        d, a = math.radians(float(dip)), math.radians(float(direction) - rotation)
        points.append(at)
        normals.append([math.sin(d) * math.sin(a), math.sin(d) * math.cos(a), math.cos(d)])
    return np.array(points, float).reshape(-1, 3), np.array(normals, float).reshape(-1, 3)


def thin(points, values, limit):
    """Keep at most ``limit`` rows: one per cell of a grid made coarser until
    it fits (a unique neighbourhood solves every point at once)."""
    if len(points) <= limit:
        return points, values, None
    span = float(np.ptp(points, axis=0).max()) or 1.0
    size = span / 200.0
    while True:
        _, keep = np.unique(np.floor(points / size).astype(np.int64), axis=0, return_index=True)
        if len(keep) <= limit:
            keep = np.sort(keep)
            return points[keep], values[keep], size
        size *= 1.5


# --------------------------------------------------------------------------- #
# The solve                                                                     #
# --------------------------------------------------------------------------- #
def solve(p, iso, family, grad_at, normals):
    """Potential-field kriging: the field on a coarse grid, then again,
    exactly, on a finer grid in the cells that straddle a contact. Returns
    ``(signed[nx, ny, nz], origin, cell, iso_values, how)``: ``signed`` is
    negative inside the unit (between its two iso-values), positive out."""
    import gstlearn as gl
    gl.defineDefaultSpace(gl.ESpaceType.RN, 3)
    how = {}
    dbiso = gl.Db.createFromSamples(len(iso), gl.ELoadBy.SAMPLE, np.column_stack([iso, family]).ravel().tolist(),
                                    ['x', 'y', 'z', 'layer'], ['x1', 'x2', 'x3', 'layer'])
    dbgrd = gl.Db.createFromSamples(len(grad_at), gl.ELoadBy.SAMPLE,
                                    np.column_stack([grad_at, normals]).ravel().tolist(),
                                    ['x', 'y', 'z', 'gx', 'gy', 'gz'], ['x1', 'x2', 'x3', 'g1', 'g2', 'g3'])
    if str(p['covariance']).upper() != 'CUBIC':
        raise SystemExit('Only a cubic covariance is taken: a Gaussian one without a drift swings away from the data '
                         'and is ill-conditioned at long ranges. Nothing was built.')
    every = np.vstack([iso, grad_at]) if len(grad_at) else iso
    low, high = every.min(axis=0) - p['margin'], every.max(axis=0) + p['margin']
    extent = np.maximum(high - low, 1e-6)
    reach = float(p['range'] if p['range'] is not None else extent.max())
    base = gl.Model.createFromParam(getattr(gl.ECov, str(p['covariance']).upper()), range=reach)
    model = gl.Model.createFromParam(getattr(gl.ECov, str(p['covariance']).upper()), range=reach)
    model.setCov(gl.CovGradientAnalytic(base.getCovAniso(0)))
    cell = float(extent.max()) / float(max(int(p['grid_res']), 2))
    dims = [int(d) for d in np.maximum(np.ceil(extent / cell).astype(int) + 1, 2)]
    coarse = gl.DbGrid.create(nx=dims, dx=[cell] * 3, x0=[float(v) for v in low])
    if gl.krigingPotential(dbiso, dbgrd, None, coarse, model, nugget_grd=float(p['nugget_gradient']),
                           flag_save_data=True) != 0:
        raise SystemExit('The potential-field solve failed (gstlearn reported an error). Nothing was built.')
    at_data = np.array(dbiso.getColumn('Potential'))
    values = sorted(float(at_data[family == f].mean()) for f in (1, 2))
    lo, hi = values
    field = np.array(coarse.getColumn('Potential')).reshape(dims, order='F')

    def signed(pot):
        return np.maximum(lo - pot, pot - hi)

    # Finer, only where it matters: every fine node inside a coarse cell whose
    # corners change sign is evaluated exactly; the rest is interpolated.
    from scipy.ndimage import map_coordinates
    k = max(int(p['refine']), 1)
    fine_dims = [(d - 1) * k + 1 for d in dims]
    fine_cell = cell / k
    idx = np.meshgrid(*(np.arange(n) / k for n in fine_dims), indexing='ij')
    fine = map_coordinates(field, idx, order=1, mode='nearest')
    s = signed(field)
    corners = np.stack([s[i:i + dims[0] - 1, j:j + dims[1] - 1, l:l + dims[2] - 1]
                        for i in (0, 1) for j in (0, 1) for l in (0, 1)])
    straddle = (corners.min(axis=0) < 0) & (corners.max(axis=0) > 0)
    chosen = np.zeros(fine_dims, bool)
    for ci, cj, cl in np.argwhere(straddle):
        chosen[ci * k:(ci + 1) * k + 1, cj * k:(cj + 1) * k + 1, cl * k:(cl + 1) * k + 1] = True
    how['coarse_nodes'] = int(np.prod(dims))
    how['refined_nodes'] = int(chosen.sum())
    if k > 1 and chosen.any():
        grid = gl.DbGrid.create(nx=fine_dims, dx=[fine_cell] * 3, x0=[float(v) for v in low])
        grid.addColumns(chosen.ravel(order='F').astype(float).tolist(), 'sel', gl.ELoc.SEL)
        gl.krigingPotential(dbiso, dbgrd, None, grid, model, nugget_grd=float(p['nugget_gradient']))
        exact = np.array(grid.getColumn('Potential', useSel=False)).reshape(fine_dims, order='F')
        fine[chosen] = exact[chosen]
    how['solver'] = f'gstlearn potential kriging ({p["covariance"].lower()} covariance, range {reach:g}, unique neighbourhood)'
    out = signed(fine)
    if p['clip_to_drilling'] is not None:
        # Clipped on the FIELD (max with the distance beyond the reach), so the
        # solid stays closed where it is cut.
        from scipy.spatial import cKDTree
        nodes = np.stack(np.meshgrid(*(low[i] + fine_cell * np.arange(n) for i, n in enumerate(fine_dims)),
                                     indexing='ij'), axis=-1).reshape(-1, 3)
        distance = cKDTree(every).query(nodes, workers=-1)[0].reshape(fine_dims)
        scale = float(np.abs(out).max()) or 1.0
        out = np.maximum(out, (distance - float(p['clip_to_drilling'])) * scale / max(float(extent.max()), 1e-6))
        how['clipped_to'] = float(p['clip_to_drilling'])
    return out, low, fine_cell, values, how


def solid(signed, origin, cell):
    """The closed surface ``signed == 0`` (padded outside, so it closes at the
    box) in grid coordinates."""
    from skimage import measure
    padded = np.pad(signed, 1, mode='constant', constant_values=float(np.abs(signed).max() or 1.0))
    vertices, faces, _normals, _values = measure.marching_cubes(padded, level=0.0, spacing=(cell,) * 3)
    return vertices + (origin - cell), faces.astype(np.int64)


# --------------------------------------------------------------------------- #
# The checks                                                                    #
# --------------------------------------------------------------------------- #
def run_checks(vertices, faces, volume, signed, origin, cell, iso, family, inside, outside, grad_at, normals, glb,
               unit, values, margin):
    from scipy.ndimage import map_coordinates
    checks = []

    def at(points):
        if not len(points):
            return np.zeros(0)
        return map_coordinates(signed, ((points - origin) / cell).T, order=1, mode='nearest')
    edges = np.sort(np.vstack([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]]), axis=1)
    _, shared = np.unique(edges, axis=0, return_counts=True)
    closed = bool(np.all(shared == 2))
    checks.append({'name': 'closed_surface', 'pass': closed,
                   'detail': 'every edge is shared by exactly two triangles' if closed else
                             f'{int(np.count_nonzero(shared != 2))} edges are not shared by exactly two triangles'})
    thickness = abs(values[1] - values[0]) or 1.0
    off = np.abs(at(iso)) / thickness
    checks.append({'name': 'contacts_on_the_surface', 'pass': bool(len(off) and np.max(off) <= 0.05),
                   'detail': f'{len(iso)} contacts; the field at each is within {float(np.max(off)) if len(off) else 0:.3f} '
                             f'of the unit\'s potential span of its iso-value (read on the field, never by ray '
                             f'casting)'})
    if len(inside) and len(outside):
        captured = float(np.mean(at(inside) <= 0))
        excluded = float(np.mean(at(outside) > 0))
        checks.append({'name': 'honours_data', 'pass': captured >= 0.9 and excluded >= 0.9,
                       'detail': f'{captured:.0%} of the {len(inside)} logged intervals of the unit fall inside the '
                                 f'solid and {excluded:.0%} of the {len(outside)} other intervals outside (the sign '
                                 f'of the field at each interval\'s mid-point)'})
    else:
        checks.append({'name': 'honours_data', 'pass': False,
                       'detail': 'no intervals of the unit, or none of anything else: nothing to test against'})
    if len(grad_at):
        gx, gy, gz = np.gradient(signed, cell)
        coords = ((grad_at - origin) / cell).T
        g = np.column_stack([map_coordinates(c, coords, order=1, mode='nearest') for c in (gx, gy, gz)])
        norm = np.linalg.norm(g, axis=1)
        ok = norm > 0
        cosines = np.abs(np.einsum('ij,ij->i', g[ok] / norm[ok, None], normals[ok]))
        angles = np.degrees(np.arccos(np.clip(cosines, -1, 1)))
        median = float(np.median(angles)) if len(angles) else 180.0
        checks.append({'name': 'follows_the_orientations', 'pass': median <= 20.0,
                       'detail': f'median angle {median:.1f} degrees between the field\'s gradient and the '
                                 f'{len(grad_at)} measured planes\' normals (90th percentile '
                                 f'{float(np.percentile(angles, 90)) if len(angles) else 180.0:.1f})'})
    low = np.vstack([iso, grad_at]).min(axis=0) if len(grad_at) else iso.min(axis=0)
    high = np.vstack([iso, grad_at]).max(axis=0) if len(grad_at) else iso.max(axis=0)
    slack = margin + 2 * cell + 1e-6           # the model box is the data's plus the margin
    inside_box = bool(np.all(vertices.min(axis=0) >= low - slack) and np.all(vertices.max(axis=0) <= high + slack))
    checks.append({'name': 'inside_drilled_volume', 'pass': inside_box,
                   'detail': f'solid bounds {np.round(vertices.min(axis=0), 1).tolist()} to '
                             f'{np.round(vertices.max(axis=0), 1).tolist()}; data span {np.round(low, 1).tolist()} '
                             f'to {np.round(high, 1).tolist()}, margin {margin:g} (where the solid meets the model box it is '
                             f'cut there by the data\'s reach, not by geology)'})
    from scipy.spatial import cKDTree
    data = np.vstack([iso, grad_at]) if len(grad_at) else iso
    reach = cKDTree(data).query(vertices, workers=-1)[0]
    checks.append({'name': 'extrapolation_stated', 'pass': True,
                   'detail': f'the solid reaches {float(reach.max()):,.1f} grid units from the nearest contact or '
                             f'orientation (95th percentile {float(np.percentile(reach, 95)):,.1f}); beyond the '
                             f'drilling the unit is carried on by the field, not seen'})
    checks.append({'name': 'size_under_the_caps', 'pass': len(glb) <= MAX_MESH_BYTES and len(faces) <= MAX_TRIANGLES,
                   'detail': f'{len(glb):,} bytes, {len(faces):,} triangles'})
    checks.append({'name': 'frame_and_units', 'pass': True,
                   'detail': f'vertices in the project local grid, Z up, in {unit}'})
    checks.append({'name': 'volume_stated', 'pass': closed,
                   'detail': f'{volume:,.0f} cubic grid units enclosed; no tonnage or grade is claimed'})
    return checks


def disclosure(p, how, n_iso, n_grad, thinned):
    return {
        'domain': f'the unit "{p["unit"]}" as logged',
        'sample_population': f'{n_iso} contacts (top and base of each logged intercept) and {n_grad} measured '
                             f'planes' + (f' of type(s) {", ".join(p["structure_types"])}' if p['structure_types'] else ''),
        'compositing': 'none (contacts are the logged interval ends)',
        'capping': 'none applied (no grades are used)',
        'metal_removed': 'none (no grades are used)',
        'declustering': 'none' + (f'; points thinned to one per {thinned:.2f} grid-unit cell to stay within '
                                  f'{p["max_points"]} solved at once' if thinned else ''),
        'transform': 'none (a potential field of the contacts, not of grades)',
        'below_detection': 'not applicable (no assay values are used)',
        'assumptions': ['the unit is one continuous body whose top and base are each one surface',
                        'dip directions are azimuths from true north, turned into the grid by its rotation',
                        'the measured planes are parallel to the unit\'s contacts'],
        'limitations': ['an interpolated solid for visualisation, not a mineral resource estimate',
                        'away from the drilling the unit is carried on to the model box by the field'
                        + (f' (clipped at {p["clip_to_drilling"]:g} grid units from the data)' if p['clip_to_drilling']
                           is not None else '; the extrapolation distance is in the checks, and the volume includes it'),
                        'no uncertainty is given (no simulations are run)',
                        'folds that repeat the unit down a hole, faults that offset it and overturned limbs are '
                        'not modelled by this recipe (use a structural modeller for those)'],
        'interpolant': how.get('solver', 'gstlearn potential kriging'),
        'range_anisotropy_source': 'the covariance range in the parameters (isotropic)',
    }


def main(argv):
    args, options = arguments(argv)
    offline = options['inputs']
    p = dict(DEFAULTS)
    if args:
        with open(args[0], encoding='utf-8') as handle:
            given = json.load(handle)
        unknown = sorted(set(given) - set(DEFAULTS))
        if unknown:
            raise SystemExit(f'Unknown parameters: {", ".join(unknown)}')
        p.update(given)
    missing = [key for key in ('project', 'unit') if p[key] is None]
    if missing:
        raise SystemExit(f'Set {", ".join(missing)} in the parameters file.')
    with open(os.path.abspath(__file__), encoding='utf-8') as handle:
        recipe = handle.read()
    env = environment()
    say(f'recipe {os.path.basename(__file__)} {RECIPE_VERSION}, sha256 '
        f'{hashlib.sha256(recipe.encode("utf-8")).hexdigest()}; python {env["python"]}; '
        + ', '.join(f'{k} {v}' for k, v in sorted(env['packages'].items())))
    say('offline: every pull read from the snapshot ' + offline if offline else 'online: pulling from ' + BASE)

    grid, liths, structures, inputs, texts = pull_inputs(p, snapshot=offline)
    if offline and options['check_against']:
        with open(options['check_against'], encoding='utf-8') as handle:
            recorded = json.load(handle).get('inputs', [])
        for index, item in enumerate(inputs):
            stated = recorded[index].get('fingerprint') if index < len(recorded) else None
            if stated != item['fingerprint']:
                raise SystemExit(f'The snapshot of pull {index} ({item["read"]}) is not the data the filed run '
                                 f'recorded (fingerprint {item["fingerprint"]}, filed {stated}). Nothing was built.')
    for item in inputs:
        say(f'pull {item["read"]}: {item["rows"]} rows, fingerprint {item["fingerprint"]}')
    iso, family, inside, outside = contacts(p, liths)
    grad_at, normals = gradients(p, structures, float(grid.get('rotation_degrees') or 0.0))
    if len(iso) < 4 or not (family == 1).any() or not (family == 2).any():
        raise SystemExit(f'Only {len(iso)} positioned contacts of "{p["unit"]}": a solid needs its top and base in '
                         f'several holes. Check the unit name with the user. Nothing was built.')
    if not len(grad_at):
        raise SystemExit('No measured plane with a dip, a dip direction and a position: without orientations '
                         'use the grade-shell recipe (or ask the user for structure measurements). Nothing was built.')
    budget = int(p['max_points'])
    iso_keep, family, thinned_iso = thin(iso, family, max(budget - min(len(grad_at), budget // 3), 4))
    grad_keep, normals, thinned_grad = thin(grad_at, normals, max(budget - len(iso_keep), 1))
    thinned = thinned_iso or thinned_grad
    if thinned:
        say(f'thinned to {len(iso_keep)} contacts and {len(grad_keep)} orientations (one per {thinned:.2f} cell)')
    signed, origin, cell, values, how = solve(p, iso_keep, family, grad_keep, normals)
    say(f'solve: {how}')
    vertices, faces = solid(signed, origin, cell)
    vertices, faces, _pieces, _kept = drop_speckle(vertices, faces, 50)
    if len(faces) == 0:
        raise SystemExit('The field gives no solid between the two contacts. Nothing was built.')
    faces, volume = outward(vertices, faces)
    glb = write_glb(vertices, faces, p['color'])
    unit = 'feet' if str(grid.get('xy_unit') or grid.get('length_unit') or '').lower().startswith('f') else 'grid units'
    checks = run_checks(vertices, faces, volume, signed, origin, cell, iso_keep, family, inside, outside, grad_keep,
                        normals, glb, unit, values, float(p['margin']))
    checks.append(environment_check(env))
    for check in checks:
        say(f'check {check["name"]}: {"pass" if check["pass"] else "FAIL"}: {check.get("detail", "")}')

    name = p['name'] or f'{p["unit"]} solid'
    file_name = re.sub(r'[^a-z0-9]+', '_', str(p['unit']).lower()).strip('_') + '_solid.glb'
    mesh_sha256 = hashlib.sha256(glb).hexdigest()
    say(f'output {file_name}: {len(faces):,} triangles, sha256 {mesh_sha256}')
    manifest = {
        'manifest_version': 1,
        'kind': 'solid',
        'title': name,
        'made_by': p['made_by'] or f'geoDB reference potential-field recipe {RECIPE_VERSION}',
        'replaces': p['layer'],
        'inputs': [{k: v for k, v in item.items() if k != 'snapshot'} for item in inputs],
        'parameters': p,
        'recipe': {'file': os.path.basename(__file__), 'sha256': hashlib.sha256(recipe.encode('utf-8')).hexdigest(),
                   'entry': f'uv run {os.path.basename(__file__)} parameters.json'},
        'environment': env,
        'outputs': [{'file': file_name, 'sha256': mesh_sha256, 'role': 'mesh', 'frame': 'project_local_grid',
                     'up': 'Z', 'length_unit': unit, 'triangles': int(len(faces)), 'volume': round(volume),
                     'contacts': int(len(iso_keep)), 'orientations': int(len(grad_keep)),
                     'iso_values': [round(v, 6) for v in values], 'how': how}],
        'checks': checks,
        'disclosure': disclosure(p, how, len(iso_keep), len(grad_keep), thinned),
        'caveats': CAVEAT,
    }
    summary = {'name': name, 'triangles': int(len(faces)), 'bytes': len(glb), 'volume': round(volume),
               'mesh_sha256': mesh_sha256, 'checks': checks, 'how': how}

    if offline:
        folder = os.path.join(os.path.dirname(os.path.abspath(offline.rstrip('/'))), 'rerun')
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, file_name), 'wb') as handle:
            handle.write(glb)
        with open(os.path.join(folder, 'manifest.json'), 'w', encoding='utf-8') as handle:
            json.dump(manifest, handle, indent=2)
        with open(os.path.join(folder, 'run_log.txt'), 'w', encoding='utf-8') as handle:
            handle.write('\n'.join(LOG) + '\n')
        result = {**summary, 'filed': False, 'offline': True, 'wrote': folder}
        if options['check_against']:
            with open(options['check_against'], encoding='utf-8') as handle:
                filed = json.load(handle)
            stated = next((o['sha256'] for o in filed.get('outputs', []) if o.get('role') == 'mesh'), None)
            result['matches_filed_run'] = stated == mesh_sha256
            result['filed_mesh_sha256'] = stated
        sys.stdout.write(json.dumps(result, indent=2) + '\n')
        return

    snapshot = 'snapshot'
    for index, (item, rows) in enumerate(zip(inputs, texts, strict=True)):
        item['snapshot'] = write_snapshot(snapshot, index, item, rows)
    with open(os.path.join(snapshot, SNAPSHOT_INDEX), 'w', encoding='utf-8') as handle:
        json.dump(inputs, handle, indent=2)
    manifest['inputs'] = [{k: v for k, v in item.items() if k != 'snapshot'} for item in inputs]
    if p['dry_run']:
        with open(file_name, 'wb') as handle:
            handle.write(glb)
        with open('manifest.json', 'w', encoding='utf-8') as handle:
            json.dump(manifest, handle, indent=2)
        with open('run_log.txt', 'w', encoding='utf-8') as handle:
            handle.write('\n'.join(LOG) + '\n')
        sys.stdout.write(json.dumps({**summary, 'filed': False,
                                     'wrote': [file_name, 'manifest.json', 'run_log.txt', snapshot]}, indent=2) + '\n')
        return

    project_file = upload(p, glb, file_name)
    for index, item in enumerate(inputs):
        with open(os.path.join(snapshot, item['snapshot']), 'rb') as handle:
            data = handle.read()
        manifest['outputs'].append({'file': item['snapshot'], 'sha256': hashlib.sha256(data).hexdigest(),
                                    'role': 'snapshot', 'input': index, 'fingerprint': item['fingerprint'],
                                    'project_file': upload(p, data, item['snapshot'], category='OT')})
    method = (f'Potential-field kriging (gstlearn) of the logged top and base of {p["unit"]} and '
              f'{len(grad_keep)} measured planes; the solid between the two iso-values.')
    run = {'manifest': manifest, 'recipe': recipe, 'recipe_name': os.path.basename(__file__), 'log': '\n'.join(LOG)}
    if p['layer'] is None:
        record, intent = {'project': p['project'], 'project_file': project_file, 'name': name, 'method': method,
                          'run': run}, 'create'
    else:
        record, intent = {'id': p['layer'], 'project_file': project_file, 'method': method, 'run': run}, 'update'
    body = {'model': 'MeshLayer', 'intent': intent, 'records': [record]}
    _answer, checked = write({**body, 'dry_run': True})
    answer, row = write({**body, 'dry_run': False}, key=str(uuid.uuid4()))
    filed = {**summary, 'filed': True, 'layer': row['id'], 'project_file': project_file,
             'write_id': answer.get('write_id'), 'status': row['status'], 'url': row['result']['url'],
             'warnings': [w['code'] for w in (checked.get('warnings') or []) + (row.get('warnings') or [])]}
    sys.stdout.write(json.dumps(filed, indent=2) + '\n')


if __name__ == '__main__':
    main(sys.argv)
