#!/usr/bin/env python3
"""
Regenerate the machine-readable artifacts from a geoDB checkout, and publish the
served copies under docs/.

Four artifacts are generated from the reference implementation so they can
never drift from the running API:

  spec/openapi.yaml      <- manage.py spectacular          (the /api/v2/ read surface)
  stac/xpl/schema.json   <- manage.py export_xpl_schema    (api/stac/xpl.py source of truth)
  errors.json            <- manage.py export_reason_codes  (api/errors.py REASON_CODES)
  schemas/*.json         <- spec/openapi.yaml              (the core-profile Read components)
  PROFILE.md             <- spec/openapi.yaml              (the x-protocol-core flags)

``schemas/*.json`` used to be hand-authored, and by 2026-09-19 six of the seven
disagreed with the wire on almost every field name (audit A1). Ruling R4: the
OpenAPI document is NORMATIVE for the wire and the schemas are generated from
its core-profile components, so they keep their job — the vocabulary, readable
one file at a time — and lose their ability to contradict. See
``scripts/emit_schemas.py``.

A further step is pure copying. The repo is the source of truth for the schemas;
GitHub Pages serves them at the host named in every ``$id`` (``spec.geodb.io``,
ruling R1). Pages can only serve what is committed under docs/, and it does not
follow git symlinks, so docs/ holds byte-identical COPIES:

  schemas/<name>.json    -> docs/exploration/v0.1.0/<name>.json
  stac/xpl/schema.json   -> docs/xpl/v0.1.0/schema.json

A schema is therefore never edited by hand. A field's wording lives on the
serializer in the geoDB checkout, the spec is regenerated from it, and the
schema follows. ``--check`` writes nothing and exits non-zero if the committed
schemas differ from what the current spec emits, or if a served docs/ copy is
stale; ``scripts/validate.py`` runs the same two comparisons, so a schema that
never reached docs/ fails validation rather than silently serving yesterday's
copy.

Usage:
    python scripts/regenerate.py --geodb /path/to/geodb            # the Django project dir
    GEODB_DIR=/path/to/geodb python scripts/regenerate.py
    python scripts/regenerate.py --publish-only                    # refresh docs/ only
    python scripts/regenerate.py --check                           # verify docs/ is current
    python scripts/regenerate.py --check --geodb /path/to/geodb     # ...and errors.json
"""

import argparse
import filecmp
import glob
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import emit_profile  # noqa: E402
import emit_schemas  # noqa: E402

try:                                                        # noqa: SIM105
    import sync_conformance_contract  # noqa: E402
except ImportError:      # the script lands in a later task; stay green without it
    sync_conformance_contract = None

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

#: The reason-code registry (task A7). Generated from the reference
#: implementation like the spec and the xpl schema, for the same reason: a
#: published registry kept in step by hand is a registry that falls behind the
#: server, and the whole point of it is that an agent can enumerate what it
#: will be refused with.
ERRORS_PATH = os.path.join(REPO, 'errors.json')


def errors_are_stale(geodb_dir, python):
    """'' when errors.json matches the server's registry, else why not.

    Runs the SAME management command the generation step runs and compares its
    output to the committed file, so --check cannot disagree with --generate.
    """
    if not os.path.exists(ERRORS_PATH):
        return 'errors.json is not committed'
    try:
        emitted = subprocess.run(
            [python, 'manage.py', 'export_reason_codes'],
            cwd=geodb_dir, check=True, capture_output=True, text=True).stdout
    except (subprocess.CalledProcessError, OSError) as exc:
        return f'could not run export_reason_codes: {exc}'
    # The command prints the document and nothing else; compare parsed JSON so
    # a trailing-newline or key-order difference is not reported as drift.
    import json
    try:
        want = json.loads(emitted[emitted.index('{'):emitted.rindex('}') + 1])
    except (ValueError, IndexError):
        return 'export_reason_codes produced no JSON document'
    with open(ERRORS_PATH, encoding='utf-8') as fh:
        have = json.load(fh)
    if have == want:
        return ''
    missing = sorted(set(want['reason_codes']) - set(have['reason_codes']))
    extra = sorted(set(have['reason_codes']) - set(want['reason_codes']))
    if missing or extra:
        return (f'codes missing from the file: {missing or "none"}; '
                f'codes in the file the server does not register: '
                f'{extra or "none"}')
    changed = sorted(c for c in want['reason_codes']
                     if have['reason_codes'][c] != want['reason_codes'][c])
    return f'entries differ for: {changed}'


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


def sync_conformance():
    """Refresh the conformance package's own copy of the contract.

    It ships spec + schemas + errors as package data so a vendor who pip
    installs the runner gets the published contract with it. Regenerating
    without this leaves the suite checking servers against the previous
    protocol, silently.
    """
    if sync_conformance_contract is None:
        return
    print('\nSyncing the conformance package\'s copy of the contract ...')
    sync_conformance_contract.main([])


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--geodb', default=os.environ.get('GEODB_DIR'),
                    help='Path to the geoDB Django project (contains manage.py).')
    ap.add_argument('--python', default=sys.executable,
                    help='Python interpreter for the geoDB venv.')
    ap.add_argument('--publish-only', action='store_true',
                    help='Skip generation; only refresh the docs/ served copies.')
    ap.add_argument('--emit-only', action='store_true',
                    help='Skip the geoDB generation step; re-emit schemas/ from '
                         'the committed spec/openapi.yaml, then publish docs/.')
    ap.add_argument('--check', action='store_true',
                    help='Verify docs/ matches the source schemas; write nothing. '
                         'Exits non-zero on any difference.')
    args = ap.parse_args()

    if args.check:
        failed = False

        # 1. The committed schemas ARE what the current spec emits. This is the
        #    check that makes ruling R4 hold: a schema that drifted from the
        #    spec is the exact defect the audit found, and it is now a red CI
        #    job rather than something a vendor discovers at runtime.
        schema_stale = emit_schemas.stale_schemas(emit_schemas.load_spec())
        if schema_stale:
            failed = True
            print('schemas/ is stale — these differ from what spec/openapi.yaml '
                  'emits:')
            for name in schema_stale:
                print('  [STALE]', name)
            print('\nRun: python scripts/regenerate.py --emit-only')

        # 2. PROFILE.md names the profile the spec actually publishes.
        if emit_profile.is_stale(emit_schemas.load_spec()):
            failed = True
            print('PROFILE.md is stale — it does not match the x-protocol-core '
                  'flags in spec/openapi.yaml.')
            print('\nRun: python scripts/regenerate.py --emit-only')

        # 3. errors.json IS what the server registers. A code added at a call
        #    site without a registry entry fails the server's own drift test;
        #    this is the other half — a registry entry that never reached the
        #    published file, which is what a consumer actually reads.
        if args.geodb:
            stale_errors = errors_are_stale(args.geodb, args.python)
            if stale_errors:
                failed = True
                print('errors.json is stale — it differs from what '
                      'api/errors.py::REASON_CODES exports:')
                print('  ' + stale_errors)
                print('\nRun: python scripts/regenerate.py --geodb <dir>')
        elif not os.path.exists(ERRORS_PATH):
            failed = True
            print('errors.json is missing, and no --geodb checkout was given '
                  'to regenerate it.')

        # 4. The served docs/ copies are byte-identical to the source schemas.
        stale = publish(check_only=True)
        if stale:
            failed = True
            print('docs/ is stale — these served copies differ from their source:')
            for path in stale:
                print('  [STALE]', path)
            print('\nRun: python scripts/regenerate.py --publish-only')

        # 5. The conformance package's copy of the contract is current. It
        #    ships spec + schemas + errors as package data because a runner
        #    that fetched them from the server under test would pass against
        #    any self-consistent server — so that copy is load-bearing, and a
        #    stale one means a vendor is being checked against last month's
        #    protocol.
        if sync_conformance_contract is not None:
            if sync_conformance_contract.main(['--check']) != 0:
                failed = True

        if failed:
            sys.exit(1)
        print(f'[OK] schemas/ matches spec/openapi.yaml '
              f'({len(emit_schemas.SCHEMA_FOR_COMPONENT)} core schemas), '
              f'PROFILE.md matches its core flags, '
              f'{"errors.json matches the server registry, " if args.geodb else ""}'
              f'and docs/ matches all {len(published_pairs())} source schemas.')
        return

    if args.emit_only:
        print('Emitting schemas/ + PROFILE.md from spec/openapi.yaml ...')
        spec = emit_schemas.load_spec()
        emit_schemas.write_all(spec)
        emit_profile.write(spec)
        print('\nPublishing the served copies under docs/ ...')
        if not publish():
            print('  (already current)')
        sync_conformance()
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
        run([args.python, 'manage.py', 'export_reason_codes',
             '--output', ERRORS_PATH])
        print(f'\nWrote:\n  {openapi}\n  {xpl}\n  {ERRORS_PATH}')

    # schemas/ is generated FROM the spec, so it runs whether or not the geoDB
    # generation step did — --publish-only still re-derives them from whatever
    # spec is committed, which is what keeps the three trees in step.
    print('\nEmitting schemas/ + PROFILE.md from spec/openapi.yaml ...')
    _spec = emit_schemas.load_spec()
    emit_schemas.write_all(_spec)
    emit_profile.write(_spec)

    print('\nPublishing the served copies under docs/ ...')
    if not publish():
        print('  (already current)')
    sync_conformance()
    print('\nNow run: python scripts/validate.py')


if __name__ == '__main__':
    main()
