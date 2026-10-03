#!/usr/bin/env python3
"""
Validate the repo's schemas + examples offline (no network, no geoDB checkout).

- Every schema in schemas/ and stac/xpl/schema.json is a valid JSON Schema
  (draft 2020-12).
- spec/openapi.yaml parses as YAML and declares an OpenAPI version.
- Every STAC example under stac/xpl/examples/ validates against stac/xpl/schema.json
  (the xpl: properties) and carries the STAC Item required fields.
- Every schema in schemas/ is what spec/openapi.yaml currently emits (ruling
  R4: the OpenAPI document is normative and the schemas are generated from its
  core-profile components, so a schema that disagrees with the spec is the
  audit's finding A1 coming back and fails here).
- The docs/ tree GitHub Pages serves is byte-identical to the source schemas, so
  a schema edit that never reached docs/ fails here instead of serving a stale
  copy at its own `$id`.

Requires: jsonschema (+ pyyaml for the openapi check). Exit non-zero on any failure.

    python scripts/validate.py
"""

import glob
import json
import os
import sys

from jsonschema.validators import Draft202012Validator

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from regenerate import publish as _publish_docs  # noqa: E402
import emit_schemas  # noqa: E402

STAC_ITEM_REQUIRED = ('type', 'stac_version', 'id', 'geometry', 'properties',
                      'links', 'assets')


def _load(path):
    with open(path, encoding='utf-8') as fh:
        return json.load(fh)


def main():
    failures = []

    # 1. All JSON Schemas are themselves valid.
    schema_files = sorted(glob.glob(os.path.join(REPO, 'schemas', '*.json')))
    schema_files.append(os.path.join(REPO, 'stac', 'xpl', 'schema.json'))
    for f in schema_files:
        try:
            Draft202012Validator.check_schema(_load(f))
            print(f'[OK] schema valid: {os.path.relpath(f, REPO)}')
        except Exception as exc:  # noqa: BLE001
            failures.append(f'{f}: {exc}')

    # 2. openapi.yaml parses + declares a version.
    try:
        import yaml
        spec = yaml.safe_load(open(os.path.join(REPO, 'spec', 'openapi.yaml')))
        assert spec.get('openapi', '').startswith('3.'), 'missing openapi: 3.x'
        assert spec.get('paths'), 'no paths'
        print(f"[OK] openapi.yaml: {spec['openapi']}, {len(spec['paths'])} paths")
    except Exception as exc:  # noqa: BLE001
        failures.append(f'spec/openapi.yaml: {exc}')

    # 3. Examples validate against the xpl schema + carry STAC Item required fields.
    xpl_validator = Draft202012Validator(
        _load(os.path.join(REPO, 'stac', 'xpl', 'schema.json')))
    for f in sorted(glob.glob(os.path.join(REPO, 'stac', 'xpl', 'examples', '*.json'))):
        item = _load(f)
        rel = os.path.relpath(f, REPO)
        missing = [k for k in STAC_ITEM_REQUIRED if k not in item]
        if missing:
            failures.append(f'{rel}: missing STAC Item fields {missing}')
            continue
        errs = sorted(xpl_validator.iter_errors(item), key=lambda e: list(e.path))
        if errs:
            failures.append(f'{rel}: xpl errors ' + '; '.join(e.message for e in errs))
        else:
            print(f'[OK] example valid: {rel}')

    # 4. Every schema is what the normative spec emits right now (R4). A file
    #    that drifted from the spec is the audit's A1 finding regenerating
    #    itself, so it fails here rather than reaching a vendor.
    try:
        schema_stale = emit_schemas.stale_schemas(emit_schemas.load_spec())
    except Exception as exc:  # noqa: BLE001
        failures.append(f'schemas/: could not compare against the spec: {exc}')
    else:
        if schema_stale:
            for name in schema_stale:
                failures.append(f'{name}: does not match spec/openapi.yaml — '
                                f'run `python scripts/regenerate.py --emit-only`')
        else:
            print(f'[OK] schemas/ matches spec/openapi.yaml '
                  f'({len(emit_schemas.SCHEMA_FOR_COMPONENT)} core schemas)')

    # 5. The served docs/ copies match their source (GitHub Pages serves docs/;
    #    every `$id` resolves there, so a stale copy is a wrong published schema).
    stale = _publish_docs(check_only=True)
    if stale:
        for path in stale:
            failures.append(f'{path}: stale served copy — run '
                            f'`python scripts/regenerate.py --publish-only`')
    else:
        print('[OK] docs/ served copies match the source schemas')

    # The write profile (B10): well formed, every code complete, and
    # partitioned from errors.json (a code is a read code or a write code).
    profile_path = os.path.join(REPO, 'conformance', 'geodb_conformance', 'contract',
                                'write-profile.json')
    try:
        with open(profile_path, encoding='utf-8') as fh:
            profile = json.load(fh)
        with open(os.path.join(REPO, 'errors.json'), encoding='utf-8') as fh:
            registry = json.load(fh)['reason_codes']
        read_codes = set(registry)
        problems = []
        if profile.get('profile') != 'write' or profile.get('status') not in ('dark', 'published'):
            problems.append('profile/status')
        for code, entry in (profile.get('reason_codes') or {}).items():
            missing = [k for k in ('http', 'meaning', 'remedy', 'retry') if not entry.get(k)]
            if missing:
                problems.append(f'{code}: no {missing}')
        write_codes = profile.get('reason_codes') or {}
        if profile.get('status') == 'dark':
            # Dark: the read registry and the write profile partition the codes.
            both = sorted(read_codes & set(write_codes))
            if both:
                problems.append(f'in errors.json AND the dark write profile: {both}')
        else:
            # Published (protocol 0.2.0): the write half is folded into the one
            # registry — errors.json carries every write code, word for word.
            missing = sorted(set(write_codes) - read_codes)
            if missing:
                problems.append(f'published write codes missing from errors.json: {missing}')
            differ = sorted(c for c in set(write_codes) & read_codes
                            if registry[c] != write_codes[c])
            if differ:
                problems.append(f'entries differ between errors.json and the profile: {differ}')
        for p in problems:
            failures.append(f'write-profile.json: {p}')
        if not problems:
            how = ('partitioned from errors.json' if profile.get('status') == 'dark'
                   else 'each one in errors.json, identical')
            print(f'[OK] write profile {profile.get("profile_version")} '
                  f'({profile.get("status")}): {len(write_codes)} write codes, {how}')
    except (OSError, ValueError, KeyError) as exc:
        failures.append(f'write-profile.json: {exc}')

    if failures:
        print('\nFAILURES:')
        for msg in failures:
            print('  [FAIL]', msg)
        sys.exit(1)
    print('\nAll protocol artifacts valid.')


if __name__ == '__main__':
    main()
