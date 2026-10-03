#!/usr/bin/env python3
"""intent=retract — move records, and everything that belongs to them, to
the Trash. The dry run lists exactly what goes (`cascade`); the real request
needs "confirm": "retract". Undo (or restore) brings it all back."""
from _records import RUN, finish, new_hole, post, samples, show

hole, hole_write = new_hole("RETRACT")
made = post({"model": "DrillSample", "intent": "create",
             "set": {"name": f"example pass {RUN}", "create": True},
             "records": samples(hole, 3)})

body = {"model": "DrillCollar", "intent": "retract", "records": [{"name": hole}]}
preview = show("retract, dry run", post(dict(body, dry_run=True)))
print("  would go:", preview.get("cascade"))
refused = post(body, ok=(400,))                     # no confirm -> refused
print("\nwithout the confirm:", refused["reason_code"], "—", refused["remedy"])
# ... show the user the cascade; after their yes:
done = show("retract", post(dict(body, confirm="retract")))
print("  went:", done.get("cascade"))

finish(hole_write, made["write_id"], done["write_id"])
