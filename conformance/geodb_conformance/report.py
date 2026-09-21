"""
Two outputs: JUnit XML for a CI system, and a markdown table for a human.

⭐ The markdown table is the deliverable. Its middle column is every
assertion's ``proves`` line, so the report reads as the contract with a
verdict beside each clause — which is what a vendor wants to paste into a
ticket, and what makes "we are conformant" a statement with evidence rather
than an assurance.
"""

from __future__ import annotations

import datetime as dt
import xml.etree.ElementTree as ET

STATUS_MARK = {
    'pass': '✅',
    'fail': '❌',
    'skip': '⏭️',
    'error': '💥',
}


def summarise(results):
    counts = {'pass': 0, 'fail': 0, 'skip': 0, 'error': 0}
    for result in results:
        counts[result.status] += 1
    return counts


def exit_code(results, *, strict=False):
    """0 when the server honoured the contract, 1 otherwise.

    A skip is not a failure by default — a project with no geophysical assets
    cannot prove the asset lane, and that is a property of the data, not of
    the server. ``--strict`` makes skips fail, for a run that is meant to be
    complete (ours, against the sandbox).
    """
    counts = summarise(results)
    if counts['fail'] or counts['error']:
        return 1
    if strict and counts['skip']:
        return 1
    return 0


def to_markdown(results, *, base_url, profile, counts=None, when=None):
    counts = counts or summarise(results)
    when = when or dt.datetime.now(dt.timezone.utc)
    lines = []
    lines.append('# geoDB Open Exploration Protocol — conformance report')
    lines.append('')
    lines.append(f'- **Server:** `{base_url}`')
    lines.append(f'- **Profile:** `{profile}`')
    lines.append(f'- **Run:** {when.strftime("%Y-%m-%d %H:%M:%SZ")}')
    lines.append(f'- **Result:** {counts["pass"]} passed · '
                 f'{counts["fail"]} failed · {counts["error"]} errored · '
                 f'{counts["skip"]} skipped')
    lines.append('')
    lines.append('| | Assertion | What this proves | Detail |')
    lines.append('|---|---|---|---|')
    for result in results:
        detail = result.detail.replace('\n', '<br>').replace('|', '\\|')
        if len(detail) > 400:
            detail = detail[:400] + '…'
        proves = result.assertion.proves.replace('|', '\\|')
        lines.append(
            f'| {STATUS_MARK[result.status]} | `{result.assertion.name}` | '
            f'{proves} | {detail} |')
    lines.append('')

    failures = [r for r in results if r.status in ('fail', 'error')]
    if failures:
        lines.append('## Failures in full')
        lines.append('')
        for result in failures:
            lines.append(f'### `{result.assertion.name}`')
            lines.append('')
            lines.append(f'*{result.assertion.proves}*')
            lines.append('')
            lines.append('```')
            lines.append(result.detail or '(no detail)')
            lines.append('```')
            lines.append('')
    return '\n'.join(lines)


def to_junit(results, *, base_url, profile, counts=None):
    counts = counts or summarise(results)
    suite = ET.Element('testsuite', {
        'name': f'geodb-conformance ({profile})',
        'tests': str(len(results)),
        'failures': str(counts['fail']),
        'errors': str(counts['error']),
        'skipped': str(counts['skip']),
        'time': f'{sum(r.duration_s for r in results):.3f}',
        'hostname': base_url,
    })
    for result in results:
        case = ET.SubElement(suite, 'testcase', {
            'classname': 'geodb_conformance',
            'name': result.assertion.name,
            'time': f'{result.duration_s:.3f}',
        })
        # The contract clause travels into the XML too, so a CI failure email
        # says what broke rather than only which test id.
        ET.SubElement(case, 'system-out').text = result.assertion.proves
        if result.status == 'fail':
            ET.SubElement(case, 'failure',
                          {'message': result.detail[:200],
                           'type': 'ConformanceFailure'}).text = result.detail
        elif result.status == 'error':
            ET.SubElement(case, 'error',
                          {'message': result.detail[:200],
                           'type': 'RunnerError'}).text = (
                result.trace or result.detail)
        elif result.status == 'skip':
            ET.SubElement(case, 'skipped', {'message': result.detail})
    return ET.tostring(suite, encoding='unicode')


def to_console(results, *, base_url, profile, counts=None):
    counts = counts or summarise(results)
    width = max((len(r.assertion.name) for r in results), default=10)
    lines = [f'geodb-conformance — {base_url} (profile: {profile})', '']
    for result in results:
        lines.append(f'  {STATUS_MARK[result.status]}  '
                     f'{result.assertion.name.ljust(width)}  '
                     f'{result.assertion.proves}')
        if result.detail and result.status != 'pass':
            for line in result.detail.splitlines():
                lines.append(f'        {line}')
    lines.append('')
    lines.append(f'  {counts["pass"]} passed · {counts["fail"]} failed · '
                 f'{counts["error"]} errored · {counts["skip"]} skipped')
    return '\n'.join(lines)
