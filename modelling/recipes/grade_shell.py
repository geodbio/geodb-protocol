#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "numpy==2.2.5",
#     "scipy==1.16.2",
#     "scikit-image==0.25.2",
#     "pyarrow==24.0.0",
# ]
# ///
"""Reference recipe: a grade shell from drill assays, filed with its run.

This is the method geoDB's own grade-shell solver uses, written as one script
an AI or a person can run in any Python sandbox and file through the open
protocol:

    pull the drill samples and their laboratory values
    -> fixed-length composites down each hole (length-weighted)
    -> collapse near-coincident points, log10 transform
    -> radial basis interpolation (linear kernel) onto a regular grid
    -> the isosurface at the cutoff, speckle removed, decimated to a budget
    -> one .glb in the project's local grid, Z up
    -> checks -> upload -> a MeshLayer with its run (manifest + this file)

It is re-runnable as written. Every setting comes from the parameters (a JSON
file, or the defaults below); every input comes from the API pulls it makes;
the key comes from the environment. Nothing is pasted in by hand.

    export GEODB_SESSION_KEY=...        # or GEODB_TOKEN for a key of your own
    uv run grade_shell.py parameters.json

``uv run`` reads the pinned header at the top of this file and builds exactly
that environment, so anyone can reproduce it from the script alone. The
manifest records the versions actually installed; a check says whether they
match the header.

Offline, with no key and no network (an audit package):

    uv run grade_shell.py parameters.json --inputs ./snapshot/ [--check-against manifest.json]

reads every pull from the snapshot (one Parquet file per pull, written by the
online run), refuses to go on if a file does not give the fingerprint the
manifest recorded, builds the same shell and writes it beside the snapshot;
with ``--check-against`` it compares the result's hash with the filed one.

parameters.json, at least:  {"project": 123, "element": "Cu", "cutoff": 2000, "units": "ppm"}
To file the next version of an existing layer, add "layer": <its id>.
To build and check without writing anything to geoDB, add "dry_run": true.

Needs the packages pinned in the header (pyvista too, only if you add it to the
header: it gives geoDB's own isosurface and decimation). The
result is an interpolated surface for visualisation. It is not a mineral
resource estimate, and the user chooses the cutoff.
"""
import hashlib
import json
import re
import math
import os
import platform
import struct
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone

import numpy as np

RECIPE_VERSION = '1.1'

#: Every setting. A parameters file overrides any of them; the manifest
#: records the full set a run used. The solver settings are the defaults of
#: geoDB's own grade-shell solver.
DEFAULTS = {
    'project': None,            # the project id (required)
    'element': None,            # for example "Cu" (required)
    'cutoff': None,             # the grade the shell is drawn at (required; the user confirms it)
    'units': 'ppm',             # the cutoff's units: ppm, ppb, pct or g/t
    'layer': None,              # an existing mesh layer id: file this run as its next version
    'name': None,               # the layer name (default: "<element> <cutoff> <units> shell")
    'made_by': None,            # who ran it, as they report themselves
    'dry_run': False,           # build and check, write nothing to geoDB
    'source_type': 'lab',       # laboratory values only (never pool field XRF silently)
    'sample_set': None,         # one sampling pass, by id; required when the project has several
    'composite_length': 2.0,    # metres down the hole
    'bdl': 'half',              # a below-detection result counts as half its detection limit
    'merge_strategy': 'high',   # several results for one sample: the highest
    'merge_tol': None,          # collapse points closer than this (default composite_length / 4)
    'transform': 'log10',       # 'log10' for trace grades, 'none' for percent-scale values
    'floor': 1e-3,              # added before the log
    'kernel': 'linear',         # the radial basis function
    'smoothing': 1e-3,
    'neighbors': 64,            # local interpolation above dense_cutoff points
    'dense_cutoff': 4000,
    'grid_res': 96,             # cells along the longest side of the model box
    'margin': None,             # padding around the data (default composite_length)
    'min_component_tris': 50,   # pieces smaller than this are dropped as speckle
    'decimate_budget': 150000,  # the most triangles delivered (needs pyvista; else reported)
    'color': [230, 159, 0],     # the shell's colour, RGB 0 to 255
    # From a fitted variogram (optional): the search ellipse that scales the
    # interpolant, {"azimuth": deg clockwise from grid north, "dip": deg down
    # of the major axis, "ranges": [major, semi-major, minor] in grid units}.
    'anisotropy': None,
    'variogram_run': None,      # the ModelRun id the anisotropy came from (recorded as an input)
    'variogram_fingerprint': None,  # that run's manifest_sha256, as model-runs/ served it
    'cutoff_confirmed_by': None,    # who confirmed the cutoff, in words ("the user, in chat")
}
TO_PPM = {'ppm': 1.0, 'g/t': 1.0, 'gpt': 1.0, 'ppb': 1e-3, 'pct': 1e4, '%': 1e4, 'percent': 1e4}
MAX_MESH_BYTES = 104_857_600        # 100 MB: the most a mesh layer takes
MAX_TRIANGLES = 2_000_000
CAVEAT = ('An interpolated surface for visualisation, made by radial basis interpolation of drill composites. '
          'It is not a mineral resource estimate and carries no tonnage or grade claim.')


# --------------------------------------------------------------------------- #
# The API                                                                       #
# --------------------------------------------------------------------------- #
BASE = os.environ.get('GEODB_BASE_URL', 'https://api.geodb.io').rstrip('/')


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


# --------------------------------------------------------------------------- #
# The snapshot: one Parquet file per pull                                       #
# --------------------------------------------------------------------------- #
SNAPSHOT_INDEX = 'inputs.json'


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


#: The fields of each pull this recipe uses (and so fingerprints).
GRID_FIELDS = ['crs_epsg', 'origin_x', 'origin_y', 'rotation_degrees']
SAMPLE_FIELDS = ['id', 'bhid', 'depth_from', 'depth_to', 'xyz_from', 'xyz_to', 'set_id']
VALUE_FIELDS = ['sample_type', 'sample_id', 'excluded', 'value', 'units', 'below_detection', 'detection_limit']


def now():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


# --------------------------------------------------------------------------- #
# The data                                                                      #
# --------------------------------------------------------------------------- #
def pull_inputs(p, snapshot=None):
    """The samples' positions and the laboratory values, what the manifest
    says about each pull, and each pull's rows as the fingerprint rule writes
    them (the snapshot's content). Positions (``xyz_from`` / ``xyz_to``) are
    already in the project's local grid, in the grid's own unit: the mesh's
    frame.

    Online, the three pulls come from the API; offline (``snapshot``: a
    folder written by an earlier run), from that folder, with no key. Either
    way the recipe computes on the pulled rows REDUCED to the fingerprinted
    fields and in the rule's sorted order, so an offline re-run sees exactly
    what the online run saw and makes the same bytes."""
    project = p['project']
    sample_filters = {'project_id': project}
    value_filters = {'project_id': project, 'element': p['element'], 'source_type': p['source_type']}
    inputs = [
        {'what': 'the project local grid', 'read': f'projects/{project}/coordinate-system/', 'filters': {},
         'fields': GRID_FIELDS},
        {'what': 'drill samples: depths and desurveyed positions on the local grid', 'read': 'drill-samples/',
         'filters': sample_filters, 'fields': SAMPLE_FIELDS},
        {'what': f'laboratory values of {p["element"]} (the drill samples\' rows are used)',
         'read': 'assay-results/', 'filters': value_filters, 'fields': VALUE_FIELDS},
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
            raise SystemExit('This project has no local grid a mesh can be placed in (no located data yet, or a '
                             'custom calibrated mine grid). Tell the user; nothing was built.')
        pulled = [[grid], pull('drill-samples/', **sample_filters), pull('assay-results/', **value_filters)]
        texts = []
        for item, rows in zip(inputs, pulled, strict=True):
            texts.append(row_texts(rows, item['fields']))
            item.update({'rows': len(rows), 'fingerprint': fingerprint_of_texts(texts[-1]), 'pulled_at': now()})
    grid_rows, sample_rows, value_rows = ([json.loads(t) for t in group] for group in texts)
    sets = sorted({s.get('set_id') for s in sample_rows if s.get('set_id') is not None})
    if p['sample_set'] is None and len(sets) > 1:
        raise SystemExit(f'This project has {len(sets)} sampling passes (set ids {sets}). Two passes over the same '
                         f'ground would be counted twice: ask the user which one and set "sample_set".')
    kept = [{**s, 'hole': s['bhid']['hole_id']} for s in sample_rows
            if p['sample_set'] is None or s.get('set_id') == p['sample_set']]
    values = [v for v in value_rows if v.get('sample_type') == 'drill' and not v.get('excluded')]
    return grid_rows[0], kept, values, inputs, texts


def sample_grades(p, values):
    """``{sample id: grade in the cutoff's units}`` and what was assumed."""
    target = TO_PPM[p['units'].lower()]
    grades, notes = {}, {'below_detection': 0, 'below_detection_no_limit': 0, 'unknown_units': 0, 'merged': 0}
    for v in values:
        factor = TO_PPM.get(str(v['units'] or '').lower())
        if factor is None:
            notes['unknown_units'] += 1
            continue
        value = float(v['value'])
        if v['below_detection'] and p['bdl'] == 'half':
            notes['below_detection'] += 1
            if v['detection_limit'] is not None:
                value = float(v['detection_limit']) / 2.0
            else:
                notes['below_detection_no_limit'] += 1
                value = value / 2.0
        value = value * factor / target
        if v['sample_id'] in grades:
            notes['merged'] += 1
            value = max(value, grades[v['sample_id']]) if p['merge_strategy'] == 'high' else grades[v['sample_id']]
        grades[v['sample_id']] = value
    return grades, notes


def composites(p, samples, grades):
    """Fixed-length composites down each hole from the collar, length-weighted
    over the samples that carry a value; each placed at its mid-depth on the
    line between its samples' desurveyed ends. Returns ``(points, values,
    grid units per metre)``."""
    length = float(p['composite_length'])
    holes, scales = {}, []
    for s in samples:
        if s['xyz_from'] is None or s['xyz_to'] is None or s['depth_to'] <= s['depth_from']:
            continue
        holes.setdefault(s['hole'], []).append(s)
        span = math.dist(s['xyz_from'], s['xyz_to'])
        if span > 0:
            scales.append(span / (s['depth_to'] - s['depth_from']))
    points, values = [], []
    for rows in holes.values():
        rows.sort(key=lambda r: r['depth_from'])
        bottom = max(r['depth_to'] for r in rows)
        for k in range(int(math.ceil(bottom / length))):
            top, base = k * length, (k + 1) * length
            weight = total = 0.0
            for r in rows:
                overlap = min(base, r['depth_to']) - max(top, r['depth_from'])
                if overlap > 0 and r['id'] in grades:
                    weight += overlap
                    total += overlap * grades[r['id']]
            if weight <= 0:
                continue
            middle = (top + min(base, bottom)) / 2.0
            host = next((r for r in rows if r['depth_from'] <= middle <= r['depth_to']), None)
            if host is None:
                continue
            t = (middle - host['depth_from']) / (host['depth_to'] - host['depth_from'])
            points.append([a + t * (b - a) for a, b in zip(host['xyz_from'], host['xyz_to'], strict=True)])
            values.append(total / weight)
    scale = float(np.median(scales)) if scales else 1.0
    return np.asarray(points, dtype=np.float64).reshape(-1, 3), np.asarray(values, dtype=np.float64), scale


def transform(values, p):
    values = np.asarray(values, dtype=np.float64)
    return np.log10(np.maximum(values, 0.0) + p['floor']) if p['transform'] == 'log10' else values


def precondition(points, values, p, scale):
    """Drop non-finite rows, collapse points closer than ``merge_tol`` to their
    centroid (the mean taken in transformed space), and transform the values."""
    keep = np.isfinite(values) & np.all(np.isfinite(points), axis=1)
    points, solved = points[keep], transform(values[keep], p)
    tolerance = (p['merge_tol'] if p['merge_tol'] is not None else p['composite_length'] / 4.0) * scale
    if tolerance > 0 and len(solved):
        keys = np.floor(points / tolerance).astype(np.int64)
        _, inverse, counts = np.unique(keys, axis=0, return_inverse=True, return_counts=True)
        inverse = inverse.ravel()
        merged = np.column_stack([np.bincount(inverse, weights=points[:, d], minlength=counts.size)
                                  for d in range(3)]) / counts[:, None]
        solved = np.bincount(inverse, weights=solved, minlength=counts.size) / counts
        points = merged
    return points, solved


# --------------------------------------------------------------------------- #
# The solve                                                                     #
# --------------------------------------------------------------------------- #
def anisotropy_matrix(anisotropy):
    """The linear map that makes the search ellipse a sphere (None: isotropic).

    Convention (state it with any numbers you carry over): X east, Y north,
    Z up, in grid units. The major axis points along ``azimuth`` (degrees
    clockwise from grid north) and plunges ``dip`` degrees below horizontal;
    the semi-major axis is horizontal, 90 degrees clockwise of the major;
    the minor axis is perpendicular to both. Distances along each axis are
    divided by its range and multiplied by the major range, so the major
    direction keeps its own scale."""
    if not anisotropy:
        return None
    az, dip = math.radians(float(anisotropy['azimuth'])), math.radians(float(anisotropy.get('dip', 0.0)))
    major, semi, minor = (float(r) for r in anisotropy['ranges'])
    u = np.array([math.sin(az) * math.cos(dip), math.cos(az) * math.cos(dip), -math.sin(dip)])
    v = np.array([math.cos(az), -math.sin(az), 0.0])
    w = np.cross(u, v)
    return np.vstack([u, v * (major / semi), w * (major / minor)])


def solve_field(points, solved, p, scale):
    """Radial basis interpolation onto a regular grid of cubic cells over the
    data's box plus a margin, in the anisotropy's stretched space when one is
    given. Returns ``(field[nx, ny, nz], origin, cell)``."""
    from scipy.interpolate import RBFInterpolator
    stretch = anisotropy_matrix(p['anisotropy'])
    to_space = (lambda xyz: xyz) if stretch is None else (lambda xyz: xyz @ stretch.T)
    margin = (p['margin'] if p['margin'] is not None else p['composite_length']) * scale
    low, high = points.min(axis=0) - margin, points.max(axis=0) + margin
    extent = np.maximum(high - low, 1e-6)
    cell = float(extent.max()) / float(max(int(p['grid_res']), 2))
    dims = np.maximum(np.ceil(extent / cell).astype(int) + 1, 2)
    options = {'kernel': p['kernel'], 'smoothing': p['smoothing']}
    if len(solved) > p['dense_cutoff']:
        options['neighbors'] = int(min(p['neighbors'], max(len(solved) - 1, 1)))
    interpolator = RBFInterpolator(to_space(points), solved, **options)
    nx, ny, nz = (int(d) for d in dims)
    xs, ys, zs = (low[i] + cell * np.arange(n) for i, n in enumerate((nx, ny, nz)))
    gx, gy = np.meshgrid(xs, ys, indexing='ij')
    flat = np.column_stack([gx.ravel(), gy.ravel()])
    field = np.empty((nx, ny, nz), dtype=np.float32)
    for k in range(nz):
        field[:, :, k] = interpolator(to_space(np.column_stack([flat, np.full(nx * ny, zs[k])]))).reshape(nx, ny)
    return field, low, cell


def isosurface(field, origin, cell, level, p):
    """The triangles of ``field == level``: speckle dropped, decimated to the
    budget when pyvista is here. Returns ``(vertices, faces, how)``."""
    how = {}
    pyvista = None
    if 'pyvista' in pinned():
        # Only when the header pins it: a package the header does not name
        # would make the run's environment differ from its own header.
        import pyvista
    if pyvista is not None:
        grid = pyvista.ImageData(dimensions=field.shape, spacing=(cell,) * 3, origin=tuple(float(o) for o in origin))
        grid.point_data['v'] = field.ravel(order='F')
        surface = grid.contour(isosurfaces=[level], scalars='v', method='flying_edges')
        vertices = np.asarray(surface.points, dtype=np.float64)
        faces = np.asarray(surface.faces).reshape(-1, 4)[:, 1:] if surface.n_cells else np.zeros((0, 3), dtype=int)
        how['isosurface'] = 'flying edges (pyvista)'
    else:
        from skimage import measure
        if not field.min() < level < field.max():
            return np.zeros((0, 3)), np.zeros((0, 3), dtype=int), {'isosurface': 'empty'}
        vertices, faces, _normals, _values = measure.marching_cubes(field, level=level, spacing=(cell,) * 3)
        vertices = vertices + np.asarray(origin, dtype=np.float64)
        how['isosurface'] = 'marching cubes (scikit-image)'
    if len(faces) == 0:
        return vertices, faces, how
    vertices, faces, how['pieces'], how['pieces_kept'] = drop_speckle(vertices, faces, int(p['min_component_tris']))
    how['triangles_before_decimation'] = int(len(faces))
    if len(faces) > p['decimate_budget']:
        if pyvista is None:
            how['decimated'] = 'no (needs pyvista); over the budget, delivered as it is'
        else:
            mesh = pyvista.PolyData(vertices, np.column_stack([np.full(len(faces), 3), faces]).ravel())
            for _ in range(2):
                if mesh.n_cells <= p['decimate_budget']:
                    break
                mesh = mesh.decimate(max(0.0, min(0.999, 1.0 - p['decimate_budget'] / mesh.n_cells))).triangulate()
            vertices = np.asarray(mesh.points, dtype=np.float64)
            faces = np.asarray(mesh.faces).reshape(-1, 4)[:, 1:]
            how['decimated'] = 'quadric (pyvista)'
    return vertices, faces, how


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


# --------------------------------------------------------------------------- #
# The checks                                                                    #
# --------------------------------------------------------------------------- #
def run_checks(p, vertices, faces, volume, points, values, field, origin, cell, level, glb, unit, scale):
    from scipy.ndimage import map_coordinates
    checks = []
    edges = np.sort(np.vstack([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]]), axis=1)
    _, shared = np.unique(edges, axis=0, return_counts=True)
    areas = np.linalg.norm(np.cross(vertices[faces[:, 1]] - vertices[faces[:, 0]],
                                    vertices[faces[:, 2]] - vertices[faces[:, 0]]), axis=1)
    closed = bool(np.all(shared == 2))
    checks.append({'name': 'closed_surface', 'pass': closed,
                   'detail': ('every edge is shared by exactly two triangles' if closed else
                              f'{int(np.count_nonzero(shared != 2))} edges are not shared by exactly two triangles '
                              f'(the shell runs to the edge of the model box, or was decimated open)')
                   + f'; {int(np.count_nonzero(areas <= 0))} degenerate triangles'})
    margin = (p['margin'] if p['margin'] is not None else p['composite_length']) * scale
    low, high = points.min(axis=0) - margin, points.max(axis=0) + margin
    inside = bool(np.all(vertices.min(axis=0) >= low - 1e-6) and np.all(vertices.max(axis=0) <= high + 1e-6))
    checks.append({'name': 'inside_drilled_volume', 'pass': inside,
                   'detail': f'mesh bounds {np.round(vertices.min(axis=0), 1).tolist()} to '
                             f'{np.round(vertices.max(axis=0), 1).tolist()}; composites span '
                             f'{np.round(points.min(axis=0), 1).tolist()} to {np.round(points.max(axis=0), 1).tolist()}'})
    at_points = map_coordinates(field, ((points - origin) / cell).T, order=1, mode='nearest')
    above = values >= p['cutoff']
    if above.any() and (~above).any():
        captured = float(np.mean(at_points[above] >= level))
        excluded = float(np.mean(at_points[~above] < level))
        checks.append({'name': 'honours_data', 'pass': captured >= 0.9 and excluded >= 0.9,
                       'detail': f'{captured:.0%} of the {int(above.sum())} composites at or above the cutoff are '
                                 f'inside the shell and {excluded:.0%} of the {int((~above).sum())} below it are '
                                 f'outside (read on the interpolated field at each composite)'})
    else:
        checks.append({'name': 'honours_data', 'pass': False,
                       'detail': 'the composites are all on one side of the cutoff: there is no shell to test'})
    checks.append({'name': 'size_under_the_caps', 'pass': len(glb) <= MAX_MESH_BYTES and len(faces) <= MAX_TRIANGLES,
                   'detail': f'{len(glb):,} bytes, {len(faces):,} triangles'})
    checks.append({'name': 'frame_and_units', 'pass': True,
                   'detail': f'vertices in the project local grid, Z up, in {unit} '
                             f'({scale:.4g} grid units per metre of hole)'})
    checks.append({'name': 'volume_stated', 'pass': closed,
                   'detail': f'{volume:,.0f} cubic grid units enclosed; no tonnage or grade is claimed'})
    return checks


# --------------------------------------------------------------------------- #
# Filing                                                                        #
# --------------------------------------------------------------------------- #
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


#: The run log: what the run printed, and each check with its numbers.
LOG = []


def say(line):
    LOG.append(line)
    sys.stderr.write(line + '\n')


def disclosure(p, assumed, how):
    """What a reviewer needs to read the shell, as this recipe made it (the
    AI or person running it corrects anything it changed)."""
    return {
        'domain': 'none: every positioned drill sample of the sampling pass, no geological domain split',
        'sample_population': (f'drill samples of sampling pass {p["sample_set"]}' if p['sample_set'] is not None
                              else 'drill samples of the project\'s one sampling pass')
                             + f', {p["source_type"]} values of {p["element"]}',
        'compositing': f'{p["composite_length"]:g} m fixed-length composites down each hole, length-weighted',
        'capping': 'none applied',
        'metal_removed': 'none (no capping)',
        'declustering': 'none (a shell is drawn, no mean is reported)',
        'transform': p['transform'],
        'below_detection': f'{p["bdl"]} the detection limit where one is on file '
                           f'({assumed.get("below_detection", 0)} values); '
                           f'{assumed.get("below_detection_no_limit", 0)} below-detection values had no limit '
                           f'on file and were left out',
        'assumptions': [f'several results for one sample: the {p["merge_strategy"]} is kept',
                        f'points closer than {p["merge_tol"] if p["merge_tol"] is not None else p["composite_length"] / 4.0:g} m are merged'],
        'limitations': ['an interpolated surface for visualisation, not a mineral resource estimate',
                        'no geological domain constrains the interpolation'],
        'cutoff': f'{p["cutoff"]:g} {p["units"]}',
        'cutoff_confirmed_by': p.get('cutoff_confirmed_by') or 'not stated',
        'interpolant': f'radial basis function, {p["kernel"]} kernel, smoothing {p["smoothing"]:g}'
                       + (f', in the space of the search ellipse {p["anisotropy"]} (azimuth clockwise from grid '
                          f'north, dip down, ranges major / semi-major / minor in grid units)'
                          if p['anisotropy'] else ', isotropic')
                       + f'; isosurface by {how.get("isosurface", "marching cubes")}',
        'range_anisotropy_source': ({'run': p['variogram_run']} if p['variogram_run'] else
                                    'stated in the parameters' if p['anisotropy'] else
                                    'none: an isotropic radial basis interpolant (no variogram used)'),
    }


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
    missing = [key for key in ('project', 'element', 'cutoff') if p[key] is None]
    if missing:
        raise SystemExit(f'Set {", ".join(missing)} in the parameters file (the user confirms the cutoff).')
    if str(p['units']).lower() not in TO_PPM:
        raise SystemExit(f'"units" must be one of {", ".join(sorted(TO_PPM))}.')
    p['cutoff'] = float(p['cutoff'])
    with open(os.path.abspath(__file__), encoding='utf-8') as handle:
        recipe = handle.read()
    env = environment()
    say(f'recipe {os.path.basename(__file__)} {RECIPE_VERSION}, sha256 '
        f'{hashlib.sha256(recipe.encode("utf-8")).hexdigest()}; python {env["python"]}; '
        + ', '.join(f'{k} {v}' for k, v in sorted(env['packages'].items())))
    say('offline: every pull read from the snapshot ' + offline if offline else 'online: pulling from ' + BASE)

    grid, samples, values, inputs, texts = pull_inputs(p, snapshot=offline)
    if offline and options['check_against']:
        # The snapshot must be the data the FILED run recorded, not only what its own index says.
        with open(options['check_against'], encoding='utf-8') as handle:
            recorded = json.load(handle).get('inputs', [])
        for index, item in enumerate(inputs):
            stated = recorded[index].get('fingerprint') if index < len(recorded) else None
            if stated != item['fingerprint']:
                raise SystemExit(f'The snapshot of pull {index} ({item["read"]}) is not the data the filed run '
                                 f'recorded (fingerprint {item["fingerprint"]}, filed {stated}). Nothing was built.')
    for item in inputs:
        say(f'pull {item["read"]}: {item["rows"]} rows, fingerprint {item["fingerprint"]}')
    if p['variogram_run'] is not None:
        # The fitted variogram this shell takes its anisotropy from (a ModelRun of the project):
        # a re-fitted variogram then flags the shell as "inputs may have changed".
        inputs.append({'what': 'model run', 'run': p['variogram_run'], 'read': 'model-runs/',
                       'filters': {'project': p['project'], 'id': p['variogram_run']},
                       'fingerprint': p['variogram_fingerprint']})
    grades, assumed = sample_grades(p, values)
    points, composite_values, scale = composites(p, samples, grades)
    if len(composite_values) < 4:
        raise SystemExit(f'Only {len(composite_values)} composites carry a {p["element"]} value on positioned '
                         f'samples; a shell needs data. Nothing was built.')
    solve_points, solved = precondition(points, composite_values, p, scale)
    field, origin, cell = solve_field(solve_points, solved, p, scale)
    level = float(transform([p['cutoff']], p)[0])
    vertices, faces, how = isosurface(field, origin, cell, level, p)
    if len(faces) == 0:
        raise SystemExit(f'No surface at {p["cutoff"]} {p["units"]}: the interpolated grades run from '
                         f'{composite_values.min():.4g} to {composite_values.max():.4g}. Ask the user for a cutoff '
                         f'inside that range. Nothing was built.')
    faces, volume = outward(vertices, faces)
    glb = write_glb(vertices, faces, p['color'])
    unit = 'feet' if scale > 2 else 'metres'
    checks = run_checks(p, vertices, faces, volume, points, composite_values, field, origin, cell, level, glb,
                        unit, scale)
    checks.append(environment_check(env))
    for check in checks:
        say(f'check {check["name"]}: {"pass" if check["pass"] else "FAIL"}: {check.get("detail", "")}')

    name = p['name'] or f'{p["element"]} {p["cutoff"]:g} {p["units"]} shell'
    file_name = f'{p["element"].lower()}_{p["cutoff"]:g}_{p["units"].replace("/", "").replace("%", "pct")}_shell.glb'
    mesh_sha256 = hashlib.sha256(glb).hexdigest()
    say(f'output {file_name}: {len(faces):,} triangles, sha256 {mesh_sha256}')
    outputs = [{'file': file_name, 'sha256': mesh_sha256, 'role': 'mesh',
                'frame': 'project_local_grid', 'up': 'Z', 'length_unit': unit,
                # What the run found on the way (facts of this output, not settings).
                'triangles': int(len(faces)), 'volume': round(volume), 'composites': int(len(composite_values)),
                'points_solved': int(len(solved)), 'grid_cell': round(cell, 4), 'assumed': assumed,
                'how': how}]
    manifest = {
        'manifest_version': 1,
        'kind': 'grade_shell',
        'title': name,
        'made_by': p['made_by'] or f'geoDB reference grade-shell recipe {RECIPE_VERSION}',
        'replaces': p['layer'],
        'inputs': [{k: v for k, v in item.items() if k != 'snapshot'} for item in inputs],
        # Exactly the settings: this block, saved as a parameters file, runs the recipe again.
        'parameters': p,
        'recipe': {'file': os.path.basename(__file__), 'sha256': hashlib.sha256(recipe.encode('utf-8')).hexdigest(),
                   'entry': f'uv run {os.path.basename(__file__)} parameters.json'},
        'environment': env,
        'outputs': outputs,
        'checks': checks,
        'disclosure': disclosure(p, assumed, how),
        'caveats': CAVEAT,
    }
    summary = {'name': name, 'triangles': int(len(faces)), 'bytes': len(glb), 'volume': round(volume),
               'composites': int(len(composite_values)), 'mesh_sha256': mesh_sha256, 'checks': checks,
               'assumed': assumed, 'how': how}

    if offline:
        # A re-run from an audit package: nothing is sent anywhere.
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

    # The snapshot: each pull as the run saw it, so the run can be made again offline.
    snapshot = 'snapshot'
    for index, (item, rows) in enumerate(zip(inputs[:len(texts)], texts, strict=True)):
        item['snapshot'] = write_snapshot(snapshot, index, item, rows)
    with open(os.path.join(snapshot, SNAPSHOT_INDEX), 'w', encoding='utf-8') as handle:
        json.dump([item for item in inputs if 'snapshot' in item], handle, indent=2)
    manifest['inputs'] = [{k: v for k, v in item.items() if k != 'snapshot'} for item in inputs]
    if p['dry_run']:
        with open(file_name, 'wb') as handle:
            handle.write(glb)
        with open('manifest.json', 'w', encoding='utf-8') as handle:
            json.dump(manifest, handle, indent=2)
        with open('run_log.txt', 'w', encoding='utf-8') as handle:
            handle.write('\n'.join(LOG) + '\n')
        sys.stdout.write(json.dumps({**summary, 'filed': False,
                                     'wrote': [file_name, 'manifest.json', 'run_log.txt', snapshot]},
                                    indent=2) + '\n')
        return

    project_file = upload(p, glb, file_name)
    for index, item in enumerate(inputs):
        if 'snapshot' not in item:
            continue
        with open(os.path.join(snapshot, item['snapshot']), 'rb') as handle:
            data = handle.read()
        manifest['outputs'].append({'file': item['snapshot'], 'sha256': hashlib.sha256(data).hexdigest(),
                                    'role': 'snapshot', 'input': index, 'fingerprint': item['fingerprint'],
                                    'project_file': upload(p, data, item['snapshot'], category='OT')})
    method = (f'Radial basis interpolation ({p["kernel"]} kernel) of {p["composite_length"]:g} m composites of '
              f'{p["element"]}, isosurface at {p["cutoff"]:g} {p["units"]}.')
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
             'run': {k: row['result']['run'].get(k) for k in ('manifest_file', 'recipe_file', 'mesh_sha256')},
             'warnings': [w['code'] for w in (checked.get('warnings') or []) + (row.get('warnings') or [])]}
    sys.stdout.write(json.dumps(filed, indent=2) + '\n')


if __name__ == '__main__':
    main(sys.argv)
