"""
The CLI.

    python -m geodb_conformance read --base-url URL --token TOKEN
    python -m geodb_conformance read --base-url URL --token TOKEN --profile full
    python -m geodb_conformance read --base-url URL --token TOKEN \
        --junit report.xml --markdown report.md
    python -m geodb_conformance selftest          # the broken-mock matrix
    python -m geodb_conformance list              # every assertion, no server

Exit code is 0 when the server honoured the contract and 1 when it did not.
"""

from __future__ import annotations

import argparse
import os
import sys

from . import load_checks
from .harness import run
from .report import (exit_code, summarise, to_console, to_junit, to_markdown)
from .session import DEFAULT_BASE_URL, Session


def _add_read_arguments(parser):
    parser.add_argument('--base-url', default=DEFAULT_BASE_URL,
                        help='the server under test (default: $GEODB_BASE_URL '
                             'or https://api.geodb.io)')
    parser.add_argument('--token', default=os.environ.get('GEODB_TOKEN'),
                        help='a read grant token (default: $GEODB_TOKEN)')
    parser.add_argument('--profile', choices=('core', 'full'), default='core',
                        help='core: what every conforming server owes. '
                             'full: plus geoDB extensions and checks needing '
                             'network or a populated asset lane.')
    parser.add_argument('--junit', metavar='FILE',
                        help='write a JUnit XML report here')
    parser.add_argument('--markdown', metavar='FILE',
                        help='write the markdown contract table here')
    parser.add_argument('--only', metavar='NAME', action='append',
                        help='run only this assertion (repeatable)')
    parser.add_argument('--strict', action='store_true',
                        help='treat a skipped assertion as a failure')
    parser.add_argument('--timeout', type=float, default=60.0,
                        help='per-request timeout in seconds (default 60)')
    parser.add_argument('--quiet', action='store_true',
                        help='print only the summary line')


def _emit(results, args, base_url):
    counts = summarise(results)
    if not args.quiet:
        print(to_console(results, base_url=base_url, profile=args.profile,
                         counts=counts))
    else:
        print(f'{counts["pass"]} passed · {counts["fail"]} failed · '
              f'{counts["error"]} errored · {counts["skip"]} skipped')
    if args.junit:
        with open(args.junit, 'w', encoding='utf-8') as handle:
            handle.write(to_junit(results, base_url=base_url,
                                  profile=args.profile, counts=counts))
        print(f'[geodb-conformance] JUnit XML -> {args.junit}')
    if args.markdown:
        with open(args.markdown, 'w', encoding='utf-8') as handle:
            handle.write(to_markdown(results, base_url=base_url,
                                     profile=args.profile, counts=counts))
        print(f'[geodb-conformance] markdown -> {args.markdown}')


def cmd_read(args):
    registry = load_checks()
    assertions = registry.select(profile=args.profile, only=args.only)
    if not assertions:
        print('[geodb-conformance] no assertions selected', file=sys.stderr)
        return 2
    if not args.token:
        print('[geodb-conformance] no token: pass --token or set GEODB_TOKEN.\n'
              '  A conformance run needs a read grant on a project with data '
              'in it.\n'
              '  To check the suite itself without a server: '
              'python -m geodb_conformance selftest',
              file=sys.stderr)
        return 2
    session = Session(args.base_url, args.token, timeout=args.timeout,
                      profile=args.profile)
    results = run(assertions, session)
    _emit(results, args, args.base_url)
    return exit_code(results, strict=args.strict)


def cmd_selftest(args):
    """Every assertion, against a mock broken in exactly that one way.

    This is the acceptance line for the suite itself: an assertion that cannot
    be made to fail is not testing anything.
    """
    from .selftest import run_break_matrix
    return run_break_matrix(verbose=not args.quiet,
                            markdown=args.markdown,
                            only=args.only)


def cmd_list(args):
    registry = load_checks()
    for assertion in registry.select(profile='full'):
        marker = ' ' if assertion.profile == 'core' else '+'
        print(f'{marker} {assertion.name}\n    {assertion.proves}')
    print(f'\n{len(registry.select("core"))} core · '
          f'{len(registry.select("full"))} total  '
          f'(+ = full profile only)')
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog='python -m geodb_conformance',
        description='Does this server implement the geoDB Open Exploration '
                    'Protocol?')
    sub = parser.add_subparsers(dest='command', required=True)

    read = sub.add_parser('read', help='run the read-half conformance suite '
                                       'against a server')
    _add_read_arguments(read)
    read.set_defaults(func=cmd_read)

    selftest = sub.add_parser(
        'selftest',
        help='prove every assertion goes red against a mock broken in exactly '
             'that way (no server, no credentials)')
    selftest.add_argument('--markdown', metavar='FILE',
                          help='write the break matrix here')
    selftest.add_argument('--only', metavar='NAME', action='append',
                          help='check only this assertion (repeatable)')
    selftest.add_argument('--quiet', action='store_true')
    selftest.set_defaults(func=cmd_selftest)

    listing = sub.add_parser('list', help='print every assertion and what it '
                                          'proves')
    listing.set_defaults(func=cmd_list)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
