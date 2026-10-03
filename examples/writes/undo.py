#!/usr/bin/env python3
"""intent=undo — reverse one earlier write by its write_id. A row someone
changed since is left as it is and named (undo_stale); a second undo is
refused (already_undone). Lost a write_id? GET /api/v2/records/writes/."""
import requests

from _records import AUTH, BASE, RUN, new_hole, post, samples, show, undo

hole, hole_write = new_hole("UNDO")
made = post({"model": "DrillSample", "intent": "create",
             "set": {"name": f"example pass {RUN}", "create": True},
             "records": samples(hole, 2)})
sid = made["rows"][0]["id"]
first = post({"model": "DrillSample", "intent": "update",
              "records": [{"id": sid, "notes": "first edit"}]})
later = post({"model": "DrillSample", "intent": "update",
              "records": [{"id": sid, "notes": "later edit"}]})

stale = undo(first["write_id"])                     # the row changed since
print("  complete:", stale["complete"])

log = requests.get(f"{BASE}/api/v2/records/writes/?undone=false", headers=AUTH,
                   timeout=60).json()
print("\nthis key's open writes, newest first:",
      [(w["intent"], w["model"]) for w in log["results"]][:5])

for write_id in (later["write_id"], first["write_id"], made["write_id"], hole_write):
    undo(write_id)                                  # newest first: nothing is stale
again = post({"intent": "undo", "write_id": hole_write}, ok=(409,))
print("\na second undo:", again["reason_code"])
