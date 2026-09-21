#!/usr/bin/env python3
"""Run every example, and report which ones ran.

CI calls this (see .github/workflows/ci.yml). It is deliberately forgiving in
one direction and strict in the other:

  * an example that cannot run HERE is SKIPPED, not failed — no token in the
    environment, no TypeScript runtime on the box, no pandas installed;
  * an example that runs and exits non-zero is a FAILURE, and so is one whose
    output does not mention the CRS.

That second check is the point. Every example exists to demonstrate the same
thing — that a coordinate means whatever `epsg` says it means — so an example
that stops printing the CRS has stopped being the example we documented, even
if it still exits zero.

    python examples/run_all.py
"""

import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

#: (label, argv, the marker its output must contain)
EXAMPLES = [
    ('curl.sh', ['bash', os.path.join(HERE, 'curl.sh')], 'CRS (EPSG)'),
    ('python_requests.py', [sys.executable, os.path.join(HERE, 'python_requests.py')],
     'CRS (EPSG)'),
    ('python_client.py', [sys.executable, os.path.join(HERE, 'python_client.py')],
     'CRS (EPSG)'),
    ('typescript_fetch.ts', ['npx', '--yes', 'tsx',
                             os.path.join(HERE, 'typescript_fetch.ts')],
     'CRS (EPSG)'),
]


def runnable(argv):
    """Why this example cannot run here, or None if it can."""
    if shutil.which(argv[0]) is None:
        return f'{argv[0]} not installed'
    if argv[0] == sys.executable and 'python_client' in argv[-1]:
        try:
            import geodb  # noqa: F401
            import pandas  # noqa: F401
        except ImportError as exc:
            return f'{exc.name} not installed (pip install -r requirements.txt)'
    return None


def main():
    if not os.environ.get('GEODB_TOKEN'):
        print('GEODB_TOKEN is not set — skipping every example.')
        print('Set it to the public sandbox token (AGENTS.md section 2) to run them.')
        return 0

    base = os.environ.get('GEODB_BASE_URL', 'https://api.geodb.io')
    print(f'Running {len(EXAMPLES)} examples against {base}\n')

    failures, skipped, ran = [], [], []
    for label, argv, marker in EXAMPLES:
        why = runnable(argv)
        if why:
            print(f'  SKIP  {label:22s} ({why})')
            skipped.append(label)
            continue
        result = subprocess.run(argv, capture_output=True, text=True, timeout=600)
        if result.returncode != 0:
            print(f'  FAIL  {label:22s} exit {result.returncode}')
            print('        ' + (result.stderr.strip().splitlines() or ['(no stderr)'])[-1])
            failures.append(label)
        elif marker not in result.stdout:
            print(f'  FAIL  {label:22s} ran, but never printed {marker!r}')
            failures.append(label)
        else:
            print(f'  ok    {label:22s} {len(result.stdout.splitlines())} lines')
            ran.append(label)

    print(f'\n{len(ran)} ran, {len(skipped)} skipped, {len(failures)} failed.')
    if failures:
        print('failed: ' + ', '.join(failures))
        return 1
    if not ran:
        print('Nothing ran. That is not a pass — check the environment.')
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
