#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "numpy==2.2.5",
#     "scipy==1.16.2",
#     "scikit-image==0.25.2",
#     "pandas==2.2.3",
#     "gstlearn==1.11.1",
#     "LoopStructural==1.12.0",
#     "ferreus_rbf==0.3.0",
# ]
# ///
"""Modelling engine benchmark on SYNTHETIC drilling with an analytic truth.

Which engine, at which size? This measures it in YOUR sandbox, so the numbers
in ENGINES.md (one sandbox, one day) can be checked and refreshed. Nothing here
touches geoDB or any real data: the drilling is generated, and every result is
compared with the exact answer.

Two cases, each drilled by vertical holes on a regular pattern, 300 samples per
hole (1 m each), in a 640 x 480 x 300 m box:

  unit   a folded tabular unit 30 m thick (vertically):
             top(x, y) = 160 + 25 sin(2 pi x / 800) + 0.05 y,  base = top - 30
         each sample carries its signed distance along the hole to the nearer
         contact (positive inside); contacts and their normals feed the
         potential-field and finite-difference engines.
  grade  an ellipsoidal grade body, lognormal: grade = 5000 exp(-3 r^2) with
         multiplicative lognormal noise (sigma 0.3), r the ellipsoid radius
         (semi-axes 200 x 130 x 70 m, centre of the box, turned 30 degrees);
         the shell is drawn at 500 (the truth: r = sqrt(ln 10 / 3)).

The radial basis engines interpolate the unit in a space whose vertical is
stretched by --stretch (default 8, the hole spacing over the unit's thickness):
an isotropic interpolant cannot carry a 30 m unit across holes 150 m apart, and
an implicit modeller would use the same anisotropy. The potential-field and
finite-difference engines take the orientations instead.

Engines (each run in its own process, killed at --timeout seconds):
  scipy_global   scipy RBFInterpolator over every sample (linear kernel)
  scipy_c2f      thinned interior samples, coarse grid, exact again only in
                 cells that straddle the surface
  scipy_local    scipy RBFInterpolator with a local neighbourhood (--neighbors)
  gst_potential  gstlearn potential-field kriging (unit; contacts + normals,
                 cubic covariance, no drift; never simulatePotential)
  gst_spde       gstlearn SPDE kriging (grade; Matern covariance)
  loop_fdi       LoopStructural's finite-difference interpolator (unit)
  ferreus_rbf    ferreus_rbf's fast RBF (both cases)

    uv run benchmark.py --sizes 2400,24900 --cases unit,grade --timeout 900 --out results.csv

Each row: the columns of results_2026-11-26.csv (the first data set, kept beside
this script). err_mean_m / err_p95_m: the distance of the mesh's vertices from
the true surface (unit: vertical; grade: along the ellipsoid radius, in metres);
volume_err_pct against the analytic volume; honour_inside / honour_outside: the
share of samples inside / outside by the data that the field puts on the same
side (read from the field's sign). Approximate by design: a guide to the
right engine for a size, not a certification of any engine.
"""
import argparse
import csv
import math
import multiprocessing as mp
import os
import platform
import resource
import sys
import time

import numpy as np

COLUMNS = ['dataset', 'case', 'engine', 'n_points', 'n_holes', 'status', 'grid_m', 'grid_nodes', 'fit_s', 'eval_s',
           'mesh_s', 'wall_s', 'peak_rss_mb', 'err_mean_m', 'err_p95_m', 'volume_m3', 'volume_true_m3',
           'volume_err_pct', 'watertight', 'honour_inside', 'honour_outside', 'points_after_thinning',
           'share_fine_evaluated', 'contacts', 'gradients', 'equations', 'nelements', 'iso_spread', 'neighbors',
           'neighbourhood', 'note']
ENGINES = ('scipy_global', 'scipy_c2f', 'scipy_local', 'gst_potential', 'gst_spde', 'loop_fdi', 'ferreus_rbf')
CASE_ENGINES = {'unit': ('scipy_global', 'scipy_c2f', 'scipy_local', 'gst_potential', 'loop_fdi', 'ferreus_rbf'),
                'grade': ('scipy_global', 'scipy_c2f', 'scipy_local', 'gst_spde', 'ferreus_rbf')}
BOX = np.array([640.0, 480.0, 300.0])
CELL = np.array([10.0, 8.0, 3.0])
PER_HOLE = 300
THICKNESS = 30.0
CUTOFF, PEAK, NOISE = 500.0, 5000.0, 0.3
AXES, TURN = np.array([200.0, 130.0, 70.0]), math.radians(30.0)
R0 = math.sqrt(math.log(PEAK / CUTOFF) / 3.0)


# --------------------------------------------------------------------------- #
# The synthetic drilling and its truth                                          #
# --------------------------------------------------------------------------- #
def top(x, y):
    return 160.0 + 25.0 * np.sin(2 * np.pi * x / 800.0) + 0.05 * y


def radius(p):
    """The grade body's ellipsoid radius at points ``p``."""
    c, s = math.cos(TURN), math.sin(TURN)
    d = p - BOX / 2.0
    u = np.column_stack([c * d[:, 0] + s * d[:, 1], -s * d[:, 0] + c * d[:, 1], d[:, 2]])
    return np.sqrt(((u / AXES) ** 2).sum(axis=1))


def holes(n_points):
    n = max(int(round(n_points / PER_HOLE)), 4)
    ny = max(int(round(math.sqrt(n * BOX[1] / BOX[0]))), 2)
    nx = max(int(math.ceil(n / ny)), 2)
    # Fences across the middle of the box, as drilling aimed at a target is:
    # two fences at the fewest holes, more and wider as holes are added.
    xs = np.linspace(BOX[0] * 0.1, BOX[0] * 0.9, nx)
    ys = np.linspace(BOX[1] * 0.3, BOX[1] * 0.7, ny) if ny <= 3 else np.linspace(BOX[1] * 0.1, BOX[1] * 0.9, ny)
    collars = np.array([(x, y) for x in xs for y in ys])[:n]
    return collars


def drill(case, n_points, seed=7):
    """``(points[n, 3], values[n], labels[n] (True inside), extras)``."""
    rng = np.random.default_rng(seed)
    collars = holes(n_points)
    z = BOX[2] - 0.5 - np.arange(PER_HOLE, dtype=float)
    pts = np.array([(x, y, zz) for x, y in collars for zz in z])
    if case == 'unit':
        t = top(pts[:, 0], pts[:, 1])
        # Signed distance along the hole to the nearer contact (positive inside),
        # clipped to one thickness either way: far values carry no shape and,
        # unclipped, their trend swamps the unit between sparse holes.
        values = np.clip(np.minimum(pts[:, 2] - (t - THICKNESS), t - pts[:, 2]), -THICKNESS, THICKNESS)
        contacts, normals, family = [], [], []
        for x, y in collars:
            zt = float(top(np.array([x]), np.array([y]))[0])
            dz_dx = 25.0 * 2 * np.pi / 800.0 * math.cos(2 * np.pi * x / 800.0)
            normal = np.array([-dz_dx, -0.05, 1.0])
            normal /= np.linalg.norm(normal)
            for z_c, fam in ((zt, 1), (zt - THICKNESS, 2)):
                contacts.append([x, y, z_c])
                family.append(fam)
                normals.append(normal)
        extras = {'contacts': np.array(contacts), 'family': np.array(family, float), 'normals': np.array(normals)}
        return pts, values, values > 0, extras, len(collars)
    grade = PEAK * np.exp(-3.0 * radius(pts) ** 2) * np.exp(rng.normal(0.0, NOISE, len(pts)))
    values = np.log(grade) - math.log(CUTOFF)                                     # positive above the cutoff
    return pts, values, values > 0, {}, len(collars)


def truth_volume(case):
    if case == 'unit':
        return float(BOX[0] * BOX[1] * THICKNESS)
    return float(4.0 / 3.0 * math.pi * AXES.prod() * R0 ** 3)


def surface_error(case, vertices):
    if case == 'unit':
        t = top(vertices[:, 0], vertices[:, 1])
        return np.minimum(np.abs(vertices[:, 2] - t), np.abs(vertices[:, 2] - (t - THICKNESS)))
    return np.abs(radius(vertices) - R0) * float(np.cbrt(AXES.prod()))


# --------------------------------------------------------------------------- #
# The grid, the mesh, the checks                                               #
# --------------------------------------------------------------------------- #
def grid_axes():
    dims = (np.floor(BOX / CELL).astype(int) + 1)
    return [CELL[i] * np.arange(dims[i]) for i in range(3)], dims


def grid_points():
    axes, dims = grid_axes()
    g = np.meshgrid(*axes, indexing='ij')
    return np.column_stack([a.ravel() for a in g]), dims


def mesh(field, dims):
    """Marching cubes of ``field == 0`` (positive inside), padded so it closes."""
    from skimage import measure
    f = field.reshape(dims)
    pad = np.pad(f, 1, mode='constant', constant_values=-float(np.abs(f).max() or 1.0))
    if pad.max() <= 0:
        return np.zeros((0, 3)), np.zeros((0, 3), int)
    vertices, faces, _n, _v = measure.marching_cubes(pad, level=0.0, spacing=tuple(CELL))
    return vertices - CELL, faces.astype(np.int64)


def volume_of(vertices, faces):
    if not len(faces):
        return 0.0
    a, b, c = (vertices[faces[:, i]] for i in range(3))
    return abs(float(np.einsum('ij,ij->i', a, np.cross(b, c)).sum() / 6.0))


def watertight(faces):
    if not len(faces):
        return False
    edges = np.sort(np.vstack([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]]), axis=1)
    _, shared = np.unique(edges, axis=0, return_counts=True)
    return bool(np.all(shared == 2))


def at_points(field, dims, pts):
    from scipy.ndimage import map_coordinates
    return map_coordinates(field.reshape(dims), (pts / CELL).T, order=1, mode='nearest')


# --------------------------------------------------------------------------- #
# The engines: each returns (field on the grid, facts); positive inside        #
# --------------------------------------------------------------------------- #
def stretch(case, args):
    """The radial basis engines' anisotropy (see the docstring)."""
    return np.array([1.0, 1.0, float(args.stretch) if case == 'unit' else 1.0])


def scipy_global(case, pts, values, extras, args):
    from scipy.interpolate import RBFInterpolator
    t = time.time()
    k = stretch(case, args)
    rbf = RBFInterpolator(pts * k, values, kernel='linear')
    fit = time.time() - t
    g, dims = grid_points()
    t = time.time()
    field = np.concatenate([rbf(chunk * k) for chunk in np.array_split(g, max(len(g) // 50000, 1))])
    return field, {'fit_s': fit, 'eval_s': time.time() - t, 'neighbourhood': 'global'}


def scipy_local(case, pts, values, extras, args):
    from scipy.interpolate import RBFInterpolator
    t = time.time()
    k = stretch(case, args)
    rbf = RBFInterpolator(pts * k, values, kernel='linear', neighbors=args.neighbors)
    fit = time.time() - t
    g, dims = grid_points()
    t = time.time()
    field = np.concatenate([rbf(chunk * k) for chunk in np.array_split(g, max(len(g) // 50000, 1))])
    return field, {'fit_s': fit, 'eval_s': time.time() - t, 'neighbors': args.neighbors, 'neighbourhood': 'moving'}


def scipy_c2f(case, pts, values, extras, args):
    """Thin interior samples (keep every sample within a band of the surface,
    one in ``thin`` elsewhere), solve on a grid twice as coarse, then exactly
    again only in the fine cells of coarse cells that straddle the surface."""
    from scipy.interpolate import RBFInterpolator
    from scipy.ndimage import map_coordinates
    band = np.abs(values) <= np.percentile(np.abs(values), 25)
    keep = band | (np.arange(len(values)) % 8 == 0)
    t = time.time()
    k = stretch(case, args)
    rbf = RBFInterpolator(pts[keep] * k, values[keep], kernel='linear')
    fit = time.time() - t
    axes, dims = grid_axes()
    coarse_axes = [a[::2] for a in axes]
    cg = np.column_stack([a.ravel() for a in np.meshgrid(*coarse_axes, indexing='ij')])
    t = time.time()
    coarse = rbf(cg * k).reshape([len(a) for a in coarse_axes])
    idx = np.meshgrid(*(np.arange(n) / 2.0 for n in dims), indexing='ij')
    fine = map_coordinates(coarse, idx, order=1, mode='nearest')
    s = np.sign(coarse)
    cd = coarse.shape
    corners = np.stack([s[i:i + cd[0] - 1, j:j + cd[1] - 1, k:k + cd[2] - 1]
                        for i in (0, 1) for j in (0, 1) for k in (0, 1)])
    straddle = corners.min(axis=0) != corners.max(axis=0)
    chosen = np.zeros(tuple(dims), bool)
    for ci, cj, ck in np.argwhere(straddle):
        chosen[ci * 2:ci * 2 + 3, cj * 2:cj * 2 + 3, ck * 2:ck * 2 + 3] = True
    g, _ = grid_points()
    flat = chosen.ravel()
    fine = fine.ravel()
    if flat.any():
        fine[flat] = rbf(g[flat] * k)
    return fine, {'fit_s': fit, 'eval_s': time.time() - t, 'points_after_thinning': int(keep.sum()),
                  'share_fine_evaluated': round(float(flat.mean()), 4)}


def gst_potential(case, pts, values, extras, args):
    """Contacts as two iso-potential families, normals as gradients; cubic
    covariance, no drift, unique neighbourhood (the method takes no other)."""
    import gstlearn as gl
    gl.defineDefaultSpace(gl.ESpaceType.RN, 3)
    iso, family, normals = extras['contacts'], extras['family'], extras['normals']
    dbiso = gl.Db.createFromSamples(len(iso), gl.ELoadBy.SAMPLE, np.column_stack([iso, family]).ravel().tolist(),
                                    ['x', 'y', 'z', 'layer'], ['x1', 'x2', 'x3', 'layer'])
    grads = iso[::2]
    dbgrd = gl.Db.createFromSamples(len(grads), gl.ELoadBy.SAMPLE,
                                    np.column_stack([grads, normals[::2]]).ravel().tolist(),
                                    ['x', 'y', 'z', 'gx', 'gy', 'gz'], ['x1', 'x2', 'x3', 'g1', 'g2', 'g3'])
    reach = float(BOX.max())
    base = gl.Model.createFromParam(gl.ECov.CUBIC, range=reach)
    model = gl.Model.createFromParam(gl.ECov.CUBIC, range=reach)
    model.setCov(gl.CovGradientAnalytic(base.getCovAniso(0)))
    _axes, dims = grid_axes()
    grid = gl.DbGrid.create(nx=[int(d) for d in dims], dx=[float(c) for c in CELL], x0=[0.0, 0.0, 0.0])
    t = time.time()
    if gl.krigingPotential(dbiso, dbgrd, None, grid, model, flag_save_data=True) != 0:
        raise RuntimeError('krigingPotential failed')
    pot = np.array(grid.getColumn('Potential'))
    at_data = np.array(dbiso.getColumn('Potential'))
    lo, hi = sorted(float(at_data[family == f].mean()) for f in (1, 2))
    spread = max(float(at_data[family == f].std()) for f in (1, 2))
    # The field's natural order (X fastest) back to the grid's (Z fastest).
    pot = pot.reshape(tuple(dims), order='F').ravel()
    field = np.minimum(pot - lo, hi - pot)
    return field, {'fit_s': 0.0, 'eval_s': time.time() - t, 'contacts': len(iso), 'gradients': len(grads),
                   'equations': len(iso) + 3 * len(grads), 'iso_spread': round(spread, 6), 'neighbourhood': 'unique'}


def gst_spde(case, pts, values, extras, args):
    import gstlearn as gl
    gl.defineDefaultSpace(gl.ESpaceType.RN, 3)
    mean = float(values.mean())
    db = gl.Db.createFromSamples(len(pts), gl.ELoadBy.SAMPLE, np.column_stack([pts, values - mean]).ravel().tolist(),
                                 ['x', 'y', 'z', 'v'], ['x1', 'x2', 'x3', 'z1'])
    _axes, dims = grid_axes()
    grid = gl.DbGrid.create(nx=[int(d) for d in dims], dx=[float(c) for c in CELL], x0=[0.0, 0.0, 0.0])
    model = gl.Model.createFromParam(gl.ECov.MATERN, range=150.0, sill=float(values.var()) or 1.0, param=1.0)
    t = time.time()
    if gl.krigingSPDE(db, grid, model) != 0:
        raise RuntimeError('krigingSPDE failed')
    est = np.array(grid.getColumn(grid.getAllNames()[-1])).reshape(tuple(dims), order='F').ravel() + mean
    return est, {'fit_s': 0.0, 'eval_s': time.time() - t}


def loop_fdi(case, pts, values, extras, args):
    import pandas as pd
    from LoopStructural import GeologicalModel
    iso, family, normals = extras['contacts'], extras['family'], extras['normals']
    rows = [{'X': p[0], 'Y': p[1], 'Z': p[2], 'val': 0.0 if f == 1 else -THICKNESS, 'feature_name': 'unit'}
            for p, f in zip(iso, family, strict=True)]
    rows += [{'X': p[0], 'Y': p[1], 'Z': p[2], 'nx': n[0], 'ny': n[1], 'nz': n[2], 'feature_name': 'unit'}
             for p, n in zip(iso[::2], normals[::2], strict=True)]
    model = GeologicalModel([0.0, 0.0, 0.0], list(BOX))
    model.data = pd.DataFrame(rows)
    t = time.time()
    model.create_and_add_foliation('unit', interpolatortype='FDI', nelements=args.nelements)
    fit = time.time() - t
    g, dims = grid_points()
    t = time.time()
    val = model.evaluate_feature_value('unit', g)
    field = np.minimum(val + THICKNESS, -val)
    return field, {'fit_s': fit, 'eval_s': time.time() - t, 'contacts': len(iso), 'gradients': len(iso[::2]),
                   'nelements': args.nelements}


def ferreus(case, pts, values, extras, args):
    import ferreus_rbf as f
    ic = f.interpolant_config
    settings = ic.InterpolantSettings(ic.RBFKernelType.Linear, drift=ic.Drift.Linear)
    t = time.time()
    k = stretch(case, args)
    rbf = f.RBFInterpolator(np.ascontiguousarray(pts * k), np.ascontiguousarray(values.reshape(-1, 1)), settings)
    fit = time.time() - t
    g, dims = grid_points()
    t = time.time()
    field = np.asarray(rbf.evaluate(np.ascontiguousarray(g * k))).reshape(-1)
    return field, {'fit_s': fit, 'eval_s': time.time() - t}


RUNNERS = {'scipy_global': scipy_global, 'scipy_c2f': scipy_c2f, 'scipy_local': scipy_local,
           'gst_potential': gst_potential, 'gst_spde': gst_spde, 'loop_fdi': loop_fdi, 'ferreus_rbf': ferreus}


# --------------------------------------------------------------------------- #
# One run in its own process                                                    #
# --------------------------------------------------------------------------- #
def _child(engine, case, n_points, args, queue):
    started = time.time()
    try:
        pts, values, labels, extras, n_holes = drill(case, n_points, seed=args.seed)
        field, facts = RUNNERS[engine](case, pts, values, extras, args)
        _axes, dims = grid_axes()
        t = time.time()
        vertices, faces = mesh(field, dims)
        mesh_s = time.time() - t
        error = surface_error(case, vertices) if len(vertices) else np.array([np.nan])
        vol, true = volume_of(vertices, faces), truth_volume(case)
        side = at_points(field, dims, pts) > 0
        row = {'status': 'ok', 'n_holes': n_holes, 'grid_nodes': int(np.prod(dims)), 'mesh_s': round(mesh_s, 2),
               'err_mean_m': round(float(np.nanmean(error)), 2), 'err_p95_m': round(float(np.nanpercentile(error, 95)), 2),
               'volume_m3': round(vol), 'volume_true_m3': round(true), 'volume_err_pct': round(100.0 * (vol - true) / true, 2),
               'watertight': watertight(faces),
               'honour_inside': round(float(np.mean(side[labels])), 4) if labels.any() else '',
               'honour_outside': round(float(np.mean(~side[~labels])), 4) if (~labels).any() else ''}
        row.update({k: (round(v, 2) if isinstance(v, float) else v) for k, v in facts.items()})
    except ImportError as exc:
        row = {'status': f'not run: {exc.name or "a package"} not installed'}
    except Exception as exc:  # noqa: BLE001 - a failing engine is a result, never a crash of the benchmark
        row = {'status': f'error: {type(exc).__name__}: {str(exc)[:120]}'}
    row['wall_s'] = round(time.time() - started, 2)
    row['peak_rss_mb'] = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0, 1)
    queue.put(row)


def run_one(engine, case, n_points, args):
    queue = mp.get_context('spawn').Queue()
    proc = mp.get_context('spawn').Process(target=_child, args=(engine, case, n_points, args, queue))
    proc.start()
    proc.join(args.timeout)
    if proc.is_alive():
        proc.kill()
        proc.join()
        return {'status': f'timeout after {args.timeout} s', 'wall_s': float(args.timeout)}
    try:
        return queue.get(timeout=5)
    except Exception:  # noqa: BLE001 - a child that died (memory, signal) left no row
        return {'status': f'error: the process ended with code {proc.exitcode}'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--sizes', default='2400,24900', help='samples per case, comma separated')
    parser.add_argument('--cases', default='unit,grade')
    parser.add_argument('--engines', default=','.join(ENGINES))
    parser.add_argument('--timeout', type=int, default=900, help='seconds per engine run')
    parser.add_argument('--neighbors', type=int, default=64)
    parser.add_argument('--stretch', type=float, default=8.0, help='the unit case\'s vertical stretch (RBF engines)')
    parser.add_argument('--nelements', type=int, default=100000)
    parser.add_argument('--seed', type=int, default=7)
    parser.add_argument('--out', default='results.csv')
    args = parser.parse_args(argv)
    wanted = [e.strip() for e in args.engines.split(',') if e.strip()]
    sys.stderr.write(f'sandbox: {os.cpu_count()} CPUs, python {platform.python_version()}\n')
    with open(args.out, 'w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        for case in [c.strip() for c in args.cases.split(',') if c.strip()]:
            for size in [int(s) for s in args.sizes.split(',') if s.strip()]:
                for engine in [e for e in CASE_ENGINES[case] if e in wanted]:
                    row = run_one(engine, case, size, args)
                    full = {k: '' for k in COLUMNS}
                    full.update({'dataset': f'synthetic_{size}', 'case': case, 'engine': engine, 'n_points': size,
                                 'grid_m': 'x'.join(f'{c:g}' for c in CELL)})
                    full.update({k: v for k, v in row.items() if k in full})
                    writer.writerow(full)
                    handle.flush()
                    sys.stderr.write(f'{case} {engine} {size}: {full["status"]} {full["wall_s"]} s, '
                                     f'error {full["err_mean_m"]} m, volume {full["volume_err_pct"]} %\n')


if __name__ == '__main__':
    main()
