"""
The coordinate contract — the trap that produces confidently wrong answers.

`latitude`/`longitude` hold the ORIGINAL imported coordinate in the CRS named
by `epsg`: easting and northing for a projected import, degrees only when
`epsg == 4326`. The derived WGS84 lives in `geometry` / `geometry_geojson`.

A suite can check that those fields are PRESENT. What it cannot do by
inspection is check that they are CONSISTENT — that the WGS84 the server
derived is actually the native coordinate reprojected. So this module does the
reprojection itself, with pyproj, and compares. That is the difference between
"the server sent a geometry" and "the server sent the RIGHT geometry", and it
is the one check here that would catch a server that silently reprojected into
the native fields and lost the customer's numbers.
"""

from __future__ import annotations

from ..harness import REGISTRY, Failed, Skipped, require, require_in

#: Metres. A derived WGS84 point should agree with a fresh reprojection of the
#: native coordinate to well inside this; the allowance is for the server
#: rounding its stored degrees for transport, not for a different datum.
TOLERANCE_M = 1.0


def _collar_rows(session, limit=10):
    body = session.get_json('/api/v2/drill-collars/', params={'limit': limit})
    return body.get('results') or []


@REGISTRY.add(
    'coords.source_coordinate_present',
    'Every located row carries `source_coordinate` = `{x, y, epsg}`, the '
    'original coordinate under a name that cannot be mistaken for degrees.')
def coords_source_coordinate_present(session):
    rows = _collar_rows(session)
    if not rows:
        raise Skipped('this project holds no drill collars')
    problems = []
    for row in rows:
        located = row.get('latitude') is not None or row.get('longitude') is not None
        if not located:
            continue
        source = row.get('source_coordinate')
        if not isinstance(source, dict):
            problems.append(f'collar {row.get("name")!r}: no `source_coordinate`')
            continue
        for key in ('x', 'y', 'epsg'):
            if source.get(key) is None:
                problems.append(
                    f'collar {row.get("name")!r}: `source_coordinate` has no '
                    f'{key!r} ({source!r})')
    require(not problems,
            'rows with a location but no unambiguous source coordinate:\n'
            + '\n'.join(f'  {row}' for row in problems[:10]))


@REGISTRY.add(
    'coords.source_matches_scalars',
    '`source_coordinate` carries the same numbers as the `latitude` / '
    '`longitude` scalars — x IS longitude-the-field (the easting) and y IS '
    'latitude-the-field (the northing), so the two spellings cannot drift.')
def coords_source_matches_scalars(session):
    rows = _collar_rows(session)
    if not rows:
        raise Skipped('this project holds no drill collars')
    problems = []
    compared = 0
    for row in rows:
        source = row.get('source_coordinate')
        if not isinstance(source, dict):
            continue
        if row.get('latitude') is None or row.get('longitude') is None:
            continue
        compared += 1
        if abs(float(source['x']) - float(row['longitude'])) > 1e-6:
            problems.append(
                f'collar {row.get("name")!r}: source_coordinate.x '
                f'{source["x"]!r} != longitude {row["longitude"]!r}')
        if abs(float(source['y']) - float(row['latitude'])) > 1e-6:
            problems.append(
                f'collar {row.get("name")!r}: source_coordinate.y '
                f'{source["y"]!r} != latitude {row["latitude"]!r}')
        if row.get('epsg') is not None and source.get('epsg') != row.get('epsg'):
            problems.append(
                f'collar {row.get("name")!r}: source_coordinate.epsg '
                f'{source.get("epsg")!r} != epsg {row.get("epsg")!r}')
    if not compared:
        raise Skipped('no collar carries both the scalars and a source '
                      'coordinate')
    require(not problems,
            'the two spellings of the original coordinate disagree:\n'
            + '\n'.join(f'  {row}' for row in problems[:10]))


@REGISTRY.add(
    'coords.epsg_consistent_with_geometry',
    'Reprojecting the native coordinate from its own `epsg` lands on the WGS84 '
    'the server derived — the server is not silently reprojecting into the '
    'native fields and losing the customer\'s numbers.')
def coords_epsg_consistent(session):
    try:
        from pyproj import Transformer
    except ImportError:
        raise Skipped('pyproj is not installed — install '
                      '`geodb-conformance[geo]` to check the derived WGS84 '
                      'against a fresh reprojection')

    rows = _collar_rows(session)
    if not rows:
        raise Skipped('this project holds no drill collars')

    problems = []
    compared = 0
    transformers = {}
    for row in rows:
        epsg = row.get('epsg')
        geojson = row.get('geometry_geojson')
        if epsg is None or not isinstance(geojson, dict):
            continue
        coordinates = geojson.get('coordinates') or []
        if len(coordinates) < 2:
            continue
        native_x, native_y = row.get('longitude'), row.get('latitude')
        if native_x is None or native_y is None:
            continue

        if epsg not in transformers:
            try:
                transformers[epsg] = Transformer.from_crs(
                    f'EPSG:{epsg}', 'EPSG:4326', always_xy=True)
            except Exception as exc:                       # noqa: BLE001
                problems.append(f'EPSG:{epsg} is not a CRS pyproj knows: {exc}')
                transformers[epsg] = None
        transformer = transformers[epsg]
        if transformer is None:
            continue

        lon, lat = transformer.transform(float(native_x), float(native_y))
        compared += 1
        served_lon, served_lat = float(coordinates[0]), float(coordinates[1])
        # Degrees -> metres, good enough for a 1 m tolerance check.
        import math
        dy = (lat - served_lat) * 111_320.0
        dx = ((lon - served_lon) * 111_320.0
              * math.cos(math.radians((lat + served_lat) / 2)))
        offset = math.hypot(dx, dy)
        if offset > TOLERANCE_M:
            problems.append(
                f'collar {row.get("name")!r}: native ({native_x}, {native_y}) '
                f'in EPSG:{epsg} reprojects to ({lon:.7f}, {lat:.7f}) but the '
                f'server served ({served_lon:.7f}, {served_lat:.7f}) — '
                f'{offset:,.1f} m apart')
    if not compared:
        raise Skipped('no collar carries both a native coordinate with an '
                      'epsg and a derived geometry')
    require(not problems,
            f'derived WGS84 does not agree with the native coordinate '
            f'({compared} rows reprojected, tolerance {TOLERANCE_M} m):\n'
            + '\n'.join(f'  {row}' for row in problems[:10]))
    session.shared['coords_compared'] = compared


@REGISTRY.add(
    'coords.geometry_is_ewkt_4326',
    '`geometry` is an EWKT string always in SRID 4326, whatever `epsg` says, '
    'because it is the derived value and not the original.')
def coords_geometry_ewkt(session):
    rows = _collar_rows(session)
    if not rows:
        raise Skipped('this project holds no drill collars')
    problems = []
    seen = 0
    for row in rows:
        geometry = row.get('geometry')
        if geometry is None:
            continue
        seen += 1
        if not isinstance(geometry, str):
            problems.append(
                f'collar {row.get("name")!r}: `geometry` is '
                f'{type(geometry).__name__}, must be an EWKT string')
            continue
        if not geometry.startswith('SRID=4326;'):
            problems.append(
                f'collar {row.get("name")!r}: `geometry` is {geometry[:40]!r}, '
                f'must carry SRID=4326 — it is the DERIVED WGS84')
    if not seen:
        raise Skipped('no collar carries a geometry')
    require(not problems,
            'geometry values that are not EWKT in 4326:\n'
            + '\n'.join(f'  {row}' for row in problems[:10]))
