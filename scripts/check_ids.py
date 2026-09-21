#!/usr/bin/env python3
"""
Every published schema URI resolves.

Collects every absolute ``spec.geodb.io`` URL the repo asserts — each schema's
``$id``, any ``$schema`` / ``$ref`` pointing at our own host, and every
``stac_extensions`` entry in the STAC examples — and checks that each one is
actually served.

Two modes:

  (default)  Offline. Maps ``https://spec.geodb.io/<path>`` to ``docs/<path>``
             and asserts the file exists and parses as JSON. This is the check
             that can run before GitHub Pages is enabled, and it is the one that
             catches the real mistake: an `$id` whose path nothing publishes.

  --live     Fetches each URL over HTTPS and asserts 200 + a JSON body whose
             own ``$id`` is that URL. Run this once Pages is live.

It also flags any leftover reference to a host we retired (ruling R1 consolidated
``schemas.geodb.io`` and ``stac.geodb.io`` onto one host), because a dead `$id`
fails every STAC validator that resolves ``stac_extensions``.

    python scripts/check_ids.py
    python scripts/check_ids.py --live
"""

import argparse
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
DOCS = os.path.join(REPO, 'docs')

HOST = 'spec.geodb.io'
RETIRED_HOSTS = ('schemas.geodb.io', 'stac.geodb.io')

URL_RE = re.compile(r'https://(?:%s)/[^\s"\',\]}]+' % '|'.join(
    re.escape(h) for h in (HOST,) + RETIRED_HOSTS))

# Files that assert a published URI. Everything else in the repo may mention the
# host in prose; only these are contracts.
SOURCE_GLOBS = (
    'schemas/*.json',
    'stac/xpl/schema.json',
    'stac/xpl/examples/*.json',
    'docs/exploration/v*/*.json',
    'docs/xpl/v*/*.json',
)


def collect():
    """{url: [repo-relative files that assert it]} plus retired-host hits."""
    urls, retired = {}, {}
    for pattern in SOURCE_GLOBS:
        for path in sorted(glob.glob(os.path.join(REPO, pattern))):
            rel = os.path.relpath(path, REPO)
            with open(path, encoding='utf-8') as fh:
                text = fh.read()
            for url in URL_RE.findall(text):
                bucket = retired if any(h in url for h in RETIRED_HOSTS) else urls
                bucket.setdefault(url, []).append(rel)
    return urls, retired


def check_offline(urls):
    failures = []
    for url in sorted(urls):
        path = url.split(f'https://{HOST}/', 1)[1]
        local = os.path.join(DOCS, path)
        if not os.path.exists(local):
            failures.append(f'{url}: nothing served at docs/{path} '
                            f'(asserted by {", ".join(urls[url])})')
            continue
        try:
            with open(local, encoding='utf-8') as fh:
                json.load(fh)
        except Exception as exc:  # noqa: BLE001
            failures.append(f'{url}: docs/{path} is not valid JSON: {exc}')
            continue
        print(f'[OK] {url} -> docs/{path}')
    return failures


def check_live(urls):
    import urllib.request
    failures = []
    for url in sorted(urls):
        try:
            with urllib.request.urlopen(url, timeout=20) as resp:
                if resp.status != 200:
                    failures.append(f'{url}: HTTP {resp.status}')
                    continue
                body = json.loads(resp.read().decode('utf-8'))
        except Exception as exc:  # noqa: BLE001
            failures.append(f'{url}: {exc}')
            continue
        declared = body.get('$id')
        if declared and declared != url:
            failures.append(f'{url}: served document declares $id {declared!r}')
            continue
        print(f'[OK] {url} -> 200, JSON, $id matches')
    return failures


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--live', action='store_true',
                    help='Fetch each URL over HTTPS instead of checking docs/.')
    args = ap.parse_args()

    urls, retired = collect()
    if not urls:
        print('No published URLs found — that is itself wrong.')
        sys.exit(1)

    failures = check_live(urls) if args.live else check_offline(urls)

    for url in sorted(retired):
        failures.append(f'{url}: retired host still referenced by '
                        f'{", ".join(retired[url])}')

    if failures:
        print('\nFAILURES:')
        for msg in failures:
            print('  [FAIL]', msg)
        sys.exit(1)

    mode = 'live' if args.live else 'offline (docs/ tree)'
    print(f'\nAll {len(urls)} published URIs resolve — {mode}.')


if __name__ == '__main__':
    main()
