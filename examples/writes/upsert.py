#!/usr/bin/env python3
"""intent=upsert — create what is new, overwrite exactly the fields sent on
what exists. It changes the user's data: dry-run, show them, then send."""
from _records import RUN, finish, new_hole, post, samples, show

hole, hole_write = new_hole("UPSERT")
pass_ = {"name": f"example pass {RUN}", "create": True}
made = show("create 2", post({"model": "DrillSample", "intent": "create", "set": pass_,
                              "records": samples(hole, 2)}))

rows = samples(hole, 3)                       # 2 existing + 1 new
rows[0]["notes"] = "re-logged"                # a change to an existing record
body = {"model": "DrillSample", "intent": "upsert", "set": pass_["name"], "records": rows}
preview = show("upsert, dry run", post(dict(body, dry_run=True)))
print("  before_writing:", (preview.get("before_writing") or {}).get("say", "")[:120], "…")
# ... show the user what will change, and wait for their yes ...
done = show("upsert", post(body))

finish(hole_write, made["write_id"], done["write_id"])
