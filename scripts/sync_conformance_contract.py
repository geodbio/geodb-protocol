#!/usr/bin/env python3
"""
Copy the normative contract into the conformance package, or check it has not
drifted.

``conformance/geodb_conformance/contract/`` holds the suite's own copy of
``spec/openapi.yaml``, ``errors.json`` and ``schemas/*.json``. It is packaged
as package data and read from the INSTALLED package, so a vendor who does
``pip install geodb-conformance`` gets the published contract with the runner
and never has to have this repository checked out.

That copy is the whole design — a runner that asked the server under test for
its own spec would pass against any self-consistent server — but a copy is a
copy, and copies drift. So this script exists in two modes, and the
``--check`` mode is wired into ``scripts/regenerate.py --check`` and CI:

    python scripts/sync_conformance_contract.py            # copy
    python scripts/sync_conformance_contract.py --check    # fail if drifted
"""

import filecmp
import glob
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
DEST = os.path.join(REPO, 'conformance', 'geodb_conformance', 'contract')

#: ``source (relative to the repo) -> destination (relative to DEST)``
FILES = {
    'spec/openapi.yaml': 'openapi.yaml',
    'errors.json': 'errors.json',
}
SCHEMA_GLOB = 'schemas/*.json'
SCHEMA_DEST = 'schemas'


def _pairs():
    pairs = [(os.path.join(REPO, src), os.path.join(DEST, dst))
             for src, dst in FILES.items()]
    for path in sorted(glob.glob(os.path.join(REPO, SCHEMA_GLOB))):
        pairs.append((path, os.path.join(DEST, SCHEMA_DEST,
                                         os.path.basename(path))))
    return pairs


def main(argv=None):
    check = '--check' in (sys.argv[1:] if argv is None else argv)
    os.makedirs(os.path.join(DEST, SCHEMA_DEST), exist_ok=True)

    drifted, copied = [], []
    for source, destination in _pairs():
        if not os.path.exists(destination) or \
                not filecmp.cmp(source, destination, shallow=False):
            if check:
                drifted.append(os.path.relpath(destination, REPO))
                continue
            shutil.copy2(source, destination)
            copied.append(os.path.relpath(destination, REPO))

    # A schema deleted upstream must leave the package too, or the suite
    # validates rows against a record type the protocol no longer publishes.
    expected = {os.path.basename(path) for path
                in glob.glob(os.path.join(REPO, SCHEMA_GLOB))}
    for path in sorted(glob.glob(os.path.join(DEST, SCHEMA_DEST, '*.json'))):
        if os.path.basename(path) not in expected:
            if check:
                drifted.append(os.path.relpath(path, REPO) + ' (no longer in '
                                                             'schemas/)')
            else:
                os.remove(path)
                copied.append(os.path.relpath(path, REPO) + ' (removed)')

    if check:
        if drifted:
            print('The conformance package\'s copy of the contract has '
                  'drifted from the normative files:', file=sys.stderr)
            for path in drifted:
                print(f'  {path}', file=sys.stderr)
            print('\nRun: python scripts/sync_conformance_contract.py',
                  file=sys.stderr)
            return 1
        print(f'[OK] conformance/ carries the current contract '
              f'({len(_pairs())} files)')
        return 0

    if copied:
        print(f'Synced {len(copied)} file(s) into conformance/:')
        for path in copied:
            print(f'  {path}')
    else:
        print(f'[OK] conformance/ already current ({len(_pairs())} files)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
