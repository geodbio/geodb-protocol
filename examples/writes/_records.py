"""The few lines every write example shares — bare `requests`, port them.

    export GEODB_BASE_URL=https://api.geodb.io     # or your server
    export GEODB_WRITE_TOKEN=<a key that may write: the demo write key works>
"""

import os
import sys
import uuid

import requests

BASE = os.environ.get("GEODB_BASE_URL", "https://api.geodb.io").rstrip("/")
TOKEN = os.environ.get("GEODB_WRITE_TOKEN")
if not TOKEN:
    raise SystemExit("set GEODB_WRITE_TOKEN to a key that may write records "
                     "(AGENTS.md, 'Managing data')")
AUTH = {"Authorization": f"Grant {TOKEN}"}          # `Grant`, not `Bearer`
RECORDS = f"{BASE}/api/v2/records/"                  # THE write endpoint
RUN = uuid.uuid4().hex[:6]                          # so two runs never collide


def post(body, *, idempotency_key=None, ok=(200,)):
    """One records call. A refusal of the WHOLE request is an HTTP error with
    {reason_code, detail, remedy}; a refusal of one ROW is inside `rows`."""
    headers = dict(AUTH)
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    r = requests.post(RECORDS, json=body, headers=headers, timeout=60)
    b = r.json()
    if r.status_code not in ok:
        raise SystemExit(f"{r.status_code} {b.get('reason_code')}: {b.get('detail')}\n"
                         f"  remedy: {b.get('remedy')}")
    return b


def show(label, body):
    print(f"\n{label}: {body.get('summary')}  write_id={body.get('write_id')}")
    for row in body.get("rows", []):
        line = f"  row {row.get('index', '-')}: {row.get('status')}"
        if row.get("reason_code"):
            line += f"  {row['reason_code']} — {row.get('remedy')}"
        print(line)
    return body


def undo(write_id):
    return show("undo", post({"intent": "undo", "write_id": write_id}))


def new_hole(label="EX"):
    """A collar to hang samples on. Coordinates carry their own epsg."""
    name = f"{label}-{RUN}"
    body = post({"model": "DrillCollar", "intent": "create", "records": [
        {"name": name, "latitude": 37.95, "longitude": -90.9, "epsg": 4326}]})
    return name, body["write_id"]


def samples(hole, n=3):
    return [{"bhid": hole, "name": f"{hole}-S{i + 1:02d}",
             "depth_from": 2.0 * i, "depth_to": 2.0 * i + 2.0} for i in range(n)]


def finish(*write_ids):
    """Leave the project as we found it: undo, newest first."""
    for write_id in reversed([w for w in write_ids if w]):
        undo(write_id)
    sys.exit(0)
