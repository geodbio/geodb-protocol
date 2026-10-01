#!/usr/bin/env python3
"""intent=update — change fields on EXISTING records (by geoDB id or by their
identifying fields); never creates. Only the fields sent change; Undo puts
the old values back."""
from _records import BASE, AUTH, RUN, finish, new_hole, post, samples, show
import requests

hole, hole_write = new_hole("UPDATE")
made = post({"model": "DrillSample", "intent": "create",
             "set": {"name": f"example pass {RUN}", "create": True},
             "records": samples(hole, 2)})
sample_id = made["rows"][0]["id"]

fix = {"model": "DrillSample", "intent": "update",
       "records": [{"id": sample_id, "depth_to": 2.5, "notes": "depth corrected"}]}
show("update, dry run", post(dict(fix, dry_run=True)))
# ... the user says yes ...
done = show("update", post(fix))
row = requests.get(f"{BASE}/api/v2/drill-samples/{sample_id}/", headers=AUTH, timeout=60).json()
print("  now:", row["depth_from"], "-", row["depth_to"], row["notes"])

finish(hole_write, made["write_id"], done["write_id"])
