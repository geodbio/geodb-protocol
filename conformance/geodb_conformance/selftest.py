"""
The break matrix: every assertion, against a mock broken in exactly that way.

⭐ This is the acceptance line for the whole task. "Probe must fail before it
can pass" — an assertion that has never been observed to go red is a line in a
report, not a test. So for each entry in ``mock_server.BREAKAGES`` this:

1. starts the mock serving the protocol CORRECTLY and asserts the assertion
   passes (otherwise the assertion is simply broken, and its red under the
   breakage would prove nothing);
2. restarts it broken in that one way and asserts the SAME assertion goes red;
3. asserts no OTHER assertion was needed to catch it — the breakage is
   attributed to the check that names it.

Step 1 matters as much as step 2. A check that fails against a correct server
is red for a reason that has nothing to do with the breakage, and a matrix
that only looked for red would call that a pass.

Runs with no credentials and no network, which is what lets CI run it:

    python -m geodb_conformance selftest
    python conformance/run.py --offline
"""

from __future__ import annotations

import sys

from . import load_checks
from .harness import run
from .mock_server import BREAKAGES, TOKEN, UNBREAKABLE, serve
from .mock_write import WRITE_BREAKAGES, WRITE_TOKEN
from .session import Session
from .write import load_write_checks
from .write.session import WriteSession

#: Write assertions a mock cannot meaningfully break (none today; kept so a
#: new one is either in WRITE_BREAKAGES or declared here with a reason).
WRITE_UNBREAKABLE = {}

#: The two matrices: (title, breakages, unbreakable, registry loader, token,
#: session class).
MATRICES = (
    ('read', BREAKAGES, UNBREAKABLE, load_checks, TOKEN, Session),
    ('write', WRITE_BREAKAGES, WRITE_UNBREAKABLE, load_write_checks, WRITE_TOKEN,
     WriteSession),
)

MARK = {True: '✅', False: '❌'}


def _run_one(assertion_name, breakage, registry, token=TOKEN, session_cls=Session):
    """Run one assertion against a mock. Returns the Result."""
    server, base_url = serve(0, breakage)
    try:
        session = session_cls(base_url, token, timeout=20, profile='full')
        assertions = registry.select(profile='full', only=[assertion_name])
        if not assertions:
            raise SystemExit(f'no assertion named {assertion_name!r}')
        return run(assertions, session)[0]
    finally:
        server.shutdown()
        server.server_close()


def run_break_matrix(*, verbose=True, markdown=None, only=None, which=('read', 'write')):
    rows = []
    failures = []
    for title, breakages, unbreakable, loader, token, session_cls in MATRICES:
        if title not in which:
            continue
        registry = loader()
        names = sorted(breakages)
        if only:
            names = [name for name in names if name in set(only)]
        if verbose and names:
            print(f'\n  {title} profile')
        matrix_rows = []
        for breakage in names:
            assertion_name, description = breakages[breakage]

            healthy = _run_one(assertion_name, None, registry, token, session_cls)
            broken = _run_one(assertion_name, breakage, registry, token, session_cls)

            green_when_correct = healthy.status == 'pass'
            red_when_broken = broken.status in ('fail', 'error')
            ok = green_when_correct and red_when_broken
            matrix_rows.append({
                'profile': title,
                'assertion': assertion_name,
                'breakage': description,
                'healthy': healthy.status,
                'broken': broken.status,
                'ok': ok,
                'detail': broken.detail if red_when_broken else '',
            })
            if not ok:
                if not green_when_correct:
                    failures.append(
                        f'{assertion_name}: does NOT pass against a correct '
                        f'server ({healthy.status}: {healthy.detail[:300]}) — its '
                        f'red under a breakage would prove nothing')
                else:
                    failures.append(
                        f'{assertion_name}: stayed {broken.status.upper()} while '
                        f'the server {description}')
            if verbose:
                print(f'  {MARK[ok]}  {assertion_name.ljust(48)} '
                      f'correct={healthy.status:<5} broken={broken.status}')

        # Every assertion is either in the matrix or explicitly declared
        # unbreakable-by-a-mock, with a reason. A new assertion with neither
        # is a hole, and it fails here rather than shipping untested.
        covered = {breakages[name][0] for name in breakages}
        uncovered = [a.name for a in registry.select(profile='full')
                     if a.name not in covered and a.name not in unbreakable]
        if uncovered and not only:
            failures.append(
                f'{title} assertions with no breakage in the matrix and no '
                f'unbreakable declaration (an untested assertion): '
                + ', '.join(uncovered))

        if verbose and names:
            print()
            for name, reason in sorted(unbreakable.items()):
                print(f'  ⏭️   {name.ljust(48)} not breakable by a mock: {reason}')
            passed = sum(1 for row in matrix_rows if row['ok'])
            print(f'  {title} break matrix: {passed}/{len(matrix_rows)} assertions go red '
                  f'under their own breakage and green against a correct server '
                  f'({len(unbreakable)} declared unbreakable)')
        rows.extend(matrix_rows)

    if verbose:
        for failure in failures:
            print(f'  ❌ {failure}', file=sys.stderr)

    if markdown:
        with open(markdown, 'w', encoding='utf-8') as handle:
            handle.write(matrix_markdown(rows))
        print(f'[geodb-conformance] break matrix -> {markdown}')

    return 1 if failures else 0


def matrix_markdown(rows):
    lines = ['# Conformance break matrix', '',
             'Every assertion, run against a mock server broken in exactly '
             'the one way that assertion exists to catch. An assertion is '
             'only trustworthy if it is **green against a correct server** '
             'and **red against its own breakage**.', '',
             '| | Profile | Assertion | The breakage | Correct server | Broken server |',
             '|---|---|---|---|---|---|']
    for row in rows:
        lines.append(
            f'| {MARK[row["ok"]]} | {row["profile"]} | `{row["assertion"]}` | '
            f'{row["breakage"]} | {row["healthy"]} | {row["broken"]} |')
    lines.append('')
    passed = sum(1 for row in rows if row['ok'])
    lines.append(f'**{passed}/{len(rows)}** assertions verified.')
    lines.append('')
    if UNBREAKABLE:
        lines.append('## Not breakable by a mock')
        lines.append('')
        for name, reason in sorted(UNBREAKABLE.items()):
            lines.append(f'- `{name}` — {reason}')
        lines.append('')
    return '\n'.join(lines)
