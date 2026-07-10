#!/usr/bin/env python3
"""
Regenerate the machine-readable artifacts from a geoDB checkout.

Two artifacts are generated from the reference implementation so they can never
drift from the running API:

  spec/openapi.yaml      <- manage.py spectacular         (the /api/v2/ read surface)
  stac/xpl/schema.json   <- manage.py export_xpl_schema   (api/stac/xpl.py source of truth)

Usage:
    python scripts/regenerate.py --geodb /path/to/geodb            # the Django project dir
    GEODB_DIR=/path/to/geodb python scripts/regenerate.py

The hand-authored chain-of-custody schemas under schemas/ and the STAC examples
under stac/xpl/examples/ are NOT generated — they are curated for readability and
version-controlled directly. Run scripts/validate.py after regenerating.
"""

import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--geodb', default=os.environ.get('GEODB_DIR'),
                    help='Path to the geoDB Django project (contains manage.py).')
    ap.add_argument('--python', default=sys.executable,
                    help='Python interpreter for the geoDB venv.')
    args = ap.parse_args()

    if not args.geodb or not os.path.exists(os.path.join(args.geodb, 'manage.py')):
        ap.error('Pass --geodb <dir containing manage.py> (or set GEODB_DIR).')

    openapi = os.path.join(REPO, 'spec', 'openapi.yaml')
    xpl = os.path.join(REPO, 'stac', 'xpl', 'schema.json')

    def run(cmd):
        print('$', ' '.join(cmd))
        subprocess.run(cmd, cwd=args.geodb, check=True)

    run([args.python, 'manage.py', 'spectacular', '--file', openapi])
    run([args.python, 'manage.py', 'export_xpl_schema', '--output', xpl])
    print(f'\nWrote:\n  {openapi}\n  {xpl}\nNow run: python scripts/validate.py')


if __name__ == '__main__':
    main()
