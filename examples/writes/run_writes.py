#!/usr/bin/env python3
"""Run every write example against GEODB_BASE_URL with GEODB_WRITE_TOKEN.

Not part of CI (`examples/run_all.py`): these WRITE, so point them at a
project you may write to — the demo write twin, or your own staging server.
Each example undoes what it wrote."""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXAMPLES = ["create.py", "upsert.py", "update.py", "retract.py", "restore.py",
            "undo.py", "make_default_set.py"]

failed = []
for name in EXAMPLES:
    print(f"\n===== {name} =====")
    if subprocess.run([sys.executable, os.path.join(HERE, name)], cwd=HERE).returncode:
        failed.append(name)
print(f"\n{len(EXAMPLES) - len(failed)}/{len(EXAMPLES)} write examples ran"
      + (f"; FAILED: {failed}" if failed else ""))
sys.exit(1 if failed else 0)
