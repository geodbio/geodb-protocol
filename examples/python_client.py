#!/usr/bin/env python3
"""Pull collars and assays into DataFrames with the geodb-client library.

    pip install geodb-client pandas
    export GEODB_TOKEN=<your grant>              # the public sandbox token works
    export GEODB_BASE_URL=https://api.geodb.io   # optional; this is the default
    python examples/python_client.py

The library handles paging, the 302 asset hop, and the auth header. What it
deliberately does NOT do is decide what a coordinate means — that is the one
thing you have to get right yourself. See AGENTS.md section 3.1.
"""

import os
from decimal import Decimal

import geodb

BASE = os.environ.get("GEODB_BASE_URL", "https://api.geodb.io")
TOKEN = os.environ.get("GEODB_TOKEN")
if not TOKEN:
    raise SystemExit("set GEODB_TOKEN (see AGENTS.md section 2)")

gx = geodb.Client(token=TOKEN, base_url=BASE)

context = gx.project()
print(f"project : {context['project']['name']} (id {context['project']['id']})")
print(f"protocol: {context['protocol_version']}   read-only: {context['read_only']}")

# ── records ────────────────────────────────────────────────────────────────
collars = gx.collars().to_dataframe()
assays = gx.assays().to_dataframe()
print(f"\ncollars : {len(collars)} rows")
print(f"assays  : {len(assays)} rows")

# ── the CRS, and why you must not read latitude/longitude as degrees ───────
epsgs = sorted(set(collars["epsg"].dropna().astype(int)))
print(f"\nCRS (EPSG): {epsgs}")
for code in epsgs:
    kind = "WGS84 degrees" if code == 4326 else "PROJECTED — easting/northing"
    print(f"  EPSG {code}: {kind}")

print("\nhead — the original coordinate, in its own CRS:")
print(collars[["name", "longitude", "latitude", "epsg", "xy_units"]].head().to_string(index=False))
print("\n  ^ for a projected CRS, `longitude` is the EASTING and `latitude` the")
print("    NORTHING. Read `source_coordinate` for the same values unambiguously")
print("    named, or `geometry_geojson` for WGS84.")
print(f"\n  native : {collars['source_coordinate'].iloc[0]}")
print(f"  wgs84  : {collars['geometry_geojson'].iloc[0]}")

# ── assay values are decimal STRINGS ───────────────────────────────────────
values = [(e["element"], Decimal(e["value"]), e["units"])
          for elements in assays["elements"] for e in elements]
print(f"\nassay values: {len(values)} (parsed as Decimal, never float)")
for element, value, units in values[:3]:
    print(f"  {element:3s} {value} {units}")
