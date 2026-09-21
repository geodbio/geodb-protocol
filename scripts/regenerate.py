#!/usr/bin/env python3
"""
Regenerate the machine-readable artifacts from a geoDB checkout, and publish the
served copies under docs/.

Two artifacts are generated from the reference implementation so they can never
drift from the running API:

  spec/openapi.yaml      <- manage.py spectacular         (the /api/v2/ read surface)
  stac/xpl/schema.json   <- manage.py export_xpl_schema   (api/stac/xpl.py source of truth)

A third step is pure copying. The repo is the source of truth for the schemas;
GitHub Pages serves them at the host named in every ``$id`` (``spec.geodb.io``,
ruling R1). Pages can only serve what is committed under docs/, and it does not
follow git symlinks, so docs/ holds byte-identical COPIES:

  schemas/<name>.json    -> docs/exploration/v0.1.0/<name>.json
  stac/xpl/schema.json   -> docs/xpl/v0.1.0/schema.json

Editing a schema therefore means running this script (or
``python scripts/regenerate.py --publish-only`` when there is no geoDB checkout
to hand). ``--check`` publishes nothing and exits non-zero if the two trees
differ; ``scripts/validate.py`` runs the same comparison, so a stale docs/ copy
fails validation rather than silently serving yesterday's schema.

Usage:
    python scripts/regenerate.py --geodb /path/to/geodb            # the Django project dir
    GEODB_DIR=/path/to/geodb python scripts/regenerate.py
    python scripts/regenerate.py --publish-only                    # refresh docs/ only
    python scripts/regenerate.py --check                           # verify docs/ is current
"""

import argparse
import filecmp
import glob
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

# The served layout. Keys are repo-relative source files, values are the path
# under docs/ that Pages serves — which must match the `$id` in the file.
VERSION = '0.1.0'
DOCS = os.path.join(REPO, 'docs')


def published_pairs():
    """[(source path, docs path)] for every file served at an `$id` URL."""
    pairs = []
    for src in sorted(glob.glob(os.path.join(REPO, 'schemas', '*.json'))):
        pairs.append((src, os.path.join(
            DOCS, 'exploration', f'v{VERSION}', os.path.basename(src))))
    pairs.append((os.path.join(REPO, 'stac', 'xpl', 'schema.json'),
                  os.path.join(DOCS, 'xpl', f'v{VERSION}', 'schema.json')))
    return pairs


def publish(check_only=False):
    """Copy every source schema into docs/. Returns the list of stale paths."""
    stale = []
    for src, dst in published_pairs():
        current = os.path.exists(dst) and filecmp.cmp(src, dst, shallow=False)
        if current:
            continue
        stale.append(os.path.relpath(dst, REPO))
        if not check_only:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copyfile(src, dst)
            print(f'  published {os.path.relpath(src, REPO)} -> '
                  f'{os.path.relpath(dst, REPO)}')
    return stale


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--geodb', default=os.environ.get('GEODB_DIR'),
                    help='Path to the geoDB Django project (contains manage.py).')
    ap.add_argument('--python', default=sys.executable,
                    help='Python interpreter for the geoDB venv.')
    ap.add_argument('--publish-only', action='store_true',
                    help='Skip generation; only refresh the docs/ served copies.')
    ap.add_argument('--check', action='store_true',
                    help='Verify docs/ matches the source schemas; write nothing. '
                         'Exits non-zero on any difference.')
    args = ap.parse_args()

    if args.check:
        stale = publish(check_only=True)
        if stale:
            print('docs/ is stale — these served copies differ from their source:')
            for path in stale:
                print('  [STALE]', path)
            print('\nRun: python scripts/regenerate.py --publish-only')
            sys.exit(1)
        print(f'[OK] docs/ matches all {len(published_pairs())} source schemas.')
        return

    if not args.publish_only:
        if not args.geodb or not os.path.exists(os.path.join(args.geodb, 'manage.py')):
            ap.error('Pass --geodb <dir containing manage.py> (or set GEODB_DIR), '
                     'or use --publish-only to refresh docs/ alone.')

        openapi = os.path.join(REPO, 'spec', 'openapi.yaml')
        xpl = os.path.join(REPO, 'stac', 'xpl', 'schema.json')

        def run(cmd):
            print('$', ' '.join(cmd))
            subprocess.run(cmd, cwd=args.geodb, check=True)

        run([args.python, 'manage.py', 'spectacular', '--file', openapi])
        run([args.python, 'manage.py', 'export_xpl_schema', '--output', xpl])
        print(f'\nWrote:\n  {openapi}\n  {xpl}')

    print('\nPublishing the served copies under docs/ ...')
    if not publish():
        print('  (already current)')
    print('\nNow run: python scripts/validate.py')


if __name__ == '__main__':
    main()
