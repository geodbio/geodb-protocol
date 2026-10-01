#!/usr/bin/env python3
"""intent=restore — bring a removed batch back from the Trash, by the
retract's write_id (or a Trash batch's audit_batch_id). It is a write of its
own, with its own write_id."""
from _records import finish, new_hole, post, show

hole, hole_write = new_hole("RESTORE")
gone = show("retract", post({"model": "DrillCollar", "intent": "retract",
                             "confirm": "retract", "records": [{"name": hole}]}))
back = show("restore", post({"intent": "restore", "write_id": gone["write_id"]}))

finish(hole_write, gone["write_id"], back["write_id"])
