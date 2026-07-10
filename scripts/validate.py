#!/usr/bin/env python3
"""
Validate the repo's schemas + examples offline (no network, no geoDB checkout).

- Every schema in schemas/ and stac/xpl/schema.json is a valid JSON Schema
  (draft 2020-12).
- spec/openapi.yaml parses as YAML and declares an OpenAPI version.
- Every STAC example under stac/xpl/examples/ validates against stac/xpl/schema.json
  (the xpl: properties) and carries the STAC Item required fields.

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

    if failures:
        print('\nFAILURES:')
        for msg in failures:
            print('  [FAIL]', msg)
        sys.exit(1)
    print('\nAll protocol artifacts valid.')


if __name__ == '__main__':
    main()
