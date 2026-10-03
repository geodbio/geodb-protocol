#!/usr/bin/env python3
"""intent=make_default_set — make a set the project's default for its family:
what everyone on the project sees. Only through a PERSON's own key (one who
manages the project), only on their explicit request; its dry run returns the
"confirm" value the real request needs. A vendor key (the demo write key is
one) is always refused — this example shows that refusal."""
from _records import RUN, finish, new_hole, post, samples, show

hole, hole_write = new_hole("DEFAULT")
name = f"example pass {RUN}"
made = post({"model": "DrillSample", "intent": "create",
             "set": {"name": name, "create": True}, "records": samples(hole, 1)})

dry = post({"model": "DrillSample", "intent": "make_default_set", "set": name,
            "dry_run": True}, ok=(200, 403))
if dry.get("reason_code"):
    print(f"\n{dry['reason_code']}: {dry['detail']}\n  remedy: {dry['remedy']}")
else:
    show("make_default_set, dry run", dry)
    print("  send again with \"confirm\":", repr(dry.get("confirm")),
          "and \"dry_run\": false — only after the user says yes")

finish(hole_write, made["write_id"])
