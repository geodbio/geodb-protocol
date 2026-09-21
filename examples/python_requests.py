#!/usr/bin/env python3
"""Pull collars and assays with nothing but `requests` — no client library.

    pip install requests && export GEODB_TOKEN=<your grant>   # sandbox works
    python examples/python_requests.py       # GEODB_BASE_URL optional

The whole protocol in one file: one header, one envelope, limit/offset paging,
and the rule that a coordinate means whatever `epsg` says. Port this.
"""

import os
from decimal import Decimal

import requests

BASE = os.environ.get("GEODB_BASE_URL", "https://api.geodb.io").rstrip("/")
TOKEN = os.environ.get("GEODB_TOKEN")
if not TOKEN:
    raise SystemExit("set GEODB_TOKEN (see AGENTS.md section 2)")
AUTH = {"Authorization": f"Grant {TOKEN}"}        # `Grant`, not `Bearer`


def get(url, params=None):
    r = requests.get(url, params=params, headers=AUTH, timeout=60)
    if not r.ok:                                   # every 4xx has this shape
        b = r.json()
        raise SystemExit(f"{r.status_code} {b['reason_code']}: {b['detail']}\n"
                         f"  remedy: {b.get('remedy')}")
    return r.json()


def pull(resource, **params):
    """Every row, following `next` to exhaustion. Keeps the deletion feed."""
    url, query = f"{BASE}/api/v2/{resource}/", {"limit": 500, **params}
    rows, deleted = [], []
    while url:
        body = get(url, query)
        rows.extend(body["results"])
        deleted.extend(body.get("deleted_ids") or [])
        url, query = body.get("next"), None        # `next` already carries them
    return rows, deleted


context = get(f"{BASE}/api/v2/grant-context/")
print(f"project : {context['project']['name']} (id {context['project']['id']})")
print(f"protocol: {context['protocol_version']}   read-only: {context['read_only']}")

collars, _ = pull("drill-collars")
assays, _ = pull("assays")
print(f"\ncollars : {len(collars)} rows\nassays  : {len(assays)} rows")

# The CRS is per record, in `epsg`. It decides what the scalars MEAN.
epsgs = sorted({c["epsg"] for c in collars if c.get("epsg")})
print(f"\nCRS (EPSG): {epsgs}  "
      + ("(WGS84 degrees)" if epsgs == [4326] else "(PROJECTED: easting/northing)"))

# ⚠️ latitude/longitude are the ORIGINAL coordinate in `epsg`, NOT degrees.
c = collars[0]
print(f"\n{c['name']}")
print(f"  latitude / longitude : {c['latitude']} / {c['longitude']}  "
      f"<- in EPSG {c['epsg']} ({c['xy_units']})")
print(f"  source_coordinate    : {c['source_coordinate']}")
print(f"  geometry_geojson     : {c['geometry_geojson']}")

values = [(e["element"], Decimal(e["value"]), e["units"])   # STRING -> Decimal
          for a in assays for e in a.get("elements", [])]
print(f"\nassay values: {len(values)}")
for el, val, units in values[:3]:
    print(f"  {el:3s} {val} {units}")
