#!/usr/bin/env python3
"""
Execute AGENTS.md's quickstart LITERALLY, so a drifted AGENTS.md fails CI.

``AGENTS.md`` is the file an AI agent reads before it reads anything else, and
the quickstart is the code it is most likely to copy verbatim. A quickstart
that no longer runs is worse than no quickstart: the agent follows it, gets an
exception, and starts guessing — which is precisely the five-minutes-to-stuck
failure this whole task exists to remove.

So nothing here re-implements the quickstart. It extracts the fenced python
block out of the markdown and ``exec``s it. If somebody edits AGENTS.md and
breaks the code, this goes red. If somebody changes the API and forgets
AGENTS.md, this goes red. There is no third copy to keep in step.

    export GEODB_TOKEN=<sandbox token>
    python conformance/agent_smoke.py                # against the default base
    GEODB_BASE_URL=http://localhost:8001 python conformance/agent_smoke.py

Without ``GEODB_TOKEN`` it still parses and compiles the block (so a syntax
error or a vanished quickstart fails anywhere, credentials or not) and skips
the execution.
"""

import argparse
import io
import os
import re
import sys
import contextlib

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
AGENTS = os.path.join(REPO, 'AGENTS.md')

#: The heading whose fenced python block is THE quickstart. Named rather than
#: "the last block in the file" so that adding prose below it cannot silently
#: point this at different code.
QUICKSTART_HEADING = '## Quickstart'

#: Strings the quickstart's OUTPUT must contain. These are the claims AGENTS.md
#: makes about itself: it tells an agent that it will learn the project, the
#: row counts, and — the one that matters — the CRS. A quickstart that runs but
#: stops reporting the CRS has quietly stopped teaching the trap.
REQUIRED_OUTPUT = ('project:', 'collars:', 'collar CRS (EPSG):', 'native',
                   'WGS84', 'assay values:')


def extract_quickstart(markdown):
    """The fenced ```python block under the quickstart heading."""
    if QUICKSTART_HEADING not in markdown:
        raise SystemExit(
            f'AGENTS.md has no {QUICKSTART_HEADING!r} section. Either it was '
            f'renamed (update QUICKSTART_HEADING here in the same commit) or '
            f'the quickstart is gone.')
    tail = markdown[markdown.index(QUICKSTART_HEADING):]
    blocks = re.findall(r'```python\n(.*?)```', tail, re.S)
    if not blocks:
        raise SystemExit(
            f'AGENTS.md {QUICKSTART_HEADING!r} contains no ```python block. '
            f'The quickstart must be runnable code, not prose about code.')
    return blocks[0]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--offline', action='store_true',
                    help='Parse and compile only; never call the network. '
                         'This is what CI runs without credentials.')
    args = ap.parse_args()

    with open(AGENTS, encoding='utf-8') as fh:
        code = extract_quickstart(fh.read())
    print(f'[agent_smoke] extracted {len(code.splitlines())} lines from '
          f'AGENTS.md {QUICKSTART_HEADING!r}')

    # Compiles anywhere, credentials or not. A quickstart with a syntax error
    # is broken for every reader, including the ones who never run it.
    try:
        compiled = compile(code, '<AGENTS.md quickstart>', 'exec')
    except SyntaxError as exc:
        raise SystemExit(f'[agent_smoke] FAIL — the quickstart does not '
                         f'compile: {exc}')
    print('[agent_smoke] compiles')

    if args.offline:
        print('[agent_smoke] --offline: not executing. OK')
        return 0
    if not os.environ.get('GEODB_TOKEN'):
        print('[agent_smoke] GEODB_TOKEN not set; skipping execution. OK')
        return 0

    base = os.environ.get('GEODB_BASE_URL', 'https://api.geodb.io')
    print(f'[agent_smoke] executing against {base}')
    captured = io.StringIO()
    namespace = {'__name__': '__agents_md_quickstart__'}
    try:
        with contextlib.redirect_stdout(captured):
            exec(compiled, namespace)          # noqa: S102 — the point of the file
    except Exception as exc:                    # noqa: BLE001 — report anything
        sys.stdout.write(captured.getvalue())
        raise SystemExit(f'[agent_smoke] FAIL — the quickstart raised '
                         f'{type(exc).__name__}: {exc}\n'
                         f'  AGENTS.md tells an agent to run this. Fix '
                         f'AGENTS.md, or the server, before shipping.')
    output = captured.getvalue()
    sys.stdout.write(output)

    missing = [token for token in REQUIRED_OUTPUT if token not in output]
    if missing:
        raise SystemExit(
            f'[agent_smoke] FAIL — the quickstart ran but never reported: '
            f'{missing}. AGENTS.md promises a reader it will learn these; a '
            f'quickstart that stops printing the CRS has stopped teaching the '
            f'one trap this protocol most needs taught.')
    print('[agent_smoke] OK — the documented quickstart runs and reports '
          'the project, the counts and the CRS.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
