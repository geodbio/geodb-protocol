#!/usr/bin/env python3
"""intent=create — add records; an existing record is never overwritten.

Describe, validate (dry run), write; then re-send it to see that a create is
safe to repeat (external_id + Idempotency-Key), and send a conflicting value
to see that create never overwrites.
"""
import uuid

from _records import RUN, finish, new_hole, post, samples, show
import requests
from _records import AUTH, BASE

# 1 · describe: the identifying fields and the SET rule for samples
d = requests.get(f"{BASE}/api/v2/records/describe/DrillSample/", headers=AUTH, timeout=60).json()
print("identifying fields:", d["identifying_fields"])
print("sets:", [(s["name"], s["writable_by_this_key"]) for s in d["set"]["sets"]])

hole, hole_write = new_hole("CREATE")
rows = [dict(r, external_id=f"example:{r['name']}") for r in samples(hole)]
body = {"model": "DrillSample", "intent": "create",
        "set": {"name": f"example pass {RUN}", "create": True},   # ask the user which set!
        "records": rows}

# 2 · validate: the same body with dry_run — nothing is written
show("dry run", post(dict(body, dry_run=True)))

# 3 · write, with an Idempotency-Key so a retry replays instead of writing twice
key = str(uuid.uuid4())
first = show("create", post(body, idempotency_key=key))
show("same request retried (replayed)", post(body, idempotency_key=key))
show("same external_ids re-sent (unchanged)", post(body))

# 4 · a create that meets an existing record with different values is skipped
clash = dict(body, records=[dict(rows[0], depth_to=rows[0]["depth_to"] + 1)])
skipped = show("conflicting create (skipped, both values named)", post(clash))
print("  conflicts:", skipped["rows"][0].get("conflicts"))

finish(hole_write, first["write_id"])
