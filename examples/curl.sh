#!/usr/bin/env bash
# Pull collars and assays with nothing but curl, and report the CRS.
#
#   export GEODB_TOKEN=<your grant>            # the public sandbox token works
#   export GEODB_BASE_URL=https://api.geodb.io # optional; this is the default
#   ./curl.sh
#
# Needs: curl, python3 (for reading JSON — no jq dependency).
set -euo pipefail

BASE="${GEODB_BASE_URL:-https://api.geodb.io}"
: "${GEODB_TOKEN:?set GEODB_TOKEN (see AGENTS.md section 2)}"
AUTH="Authorization: Grant ${GEODB_TOKEN}"

# 1. What does this credential see? The cheapest first call there is.
echo "== grant context =="
curl -sS -H "$AUTH" "$BASE/api/v2/grant-context/" |
  python3 -c 'import json,sys; c=json.load(sys.stdin)
print(f"  project   : {c["project"]["name"]} (id {c["project"]["id"]})")
print(f"  read only : {c["read_only"]}   throttle: {c["throttle_rate"]}")
print(f"  protocol  : {c["protocol_version"]}")'

# 2. Collars. Lists page with limit/offset — `page_size` is silently ignored.
echo "== drill collars =="
curl -sS -H "$AUTH" "$BASE/api/v2/drill-collars/?limit=500" > /tmp/geodb_collars.json
python3 -c 'import json
d=json.load(open("/tmp/geodb_collars.json"))
rows=d["results"]
print(f"  {len(rows)} of {d["count"]} rows; more pages: {bool(d["next"])}")
epsgs=sorted({r["epsg"] for r in rows if r.get("epsg")})
print(f"  CRS (EPSG): {epsgs}")
r=rows[0]
# latitude/longitude are the ORIGINAL coordinate in `epsg` — easting/northing
# unless epsg is 4326. Read source_coordinate / geometry_geojson instead.
print(f"  {r["name"]}: native={r["source_coordinate"]} units={r["xy_units"]}")
print(f"  {r["name"]}: wgs84 ={r["geometry_geojson"]}")'

# 3. Assays. `value` is a decimal STRING; parse it with a decimal type.
echo "== assays =="
curl -sS -H "$AUTH" "$BASE/api/v2/assays/?limit=500" > /tmp/geodb_assays.json
python3 -c 'import json
from decimal import Decimal
d=json.load(open("/tmp/geodb_assays.json"))
vals=[(e["element"], Decimal(e["value"]), e["units"])
      for a in d["results"] for e in a.get("elements",[])]
print(f"  {d["count"]} assays carrying {len(vals)} values")
for v in vals[:3]: print(f"    {v[0]:3s} {v[1]} {v[2]}")'

echo "done."
