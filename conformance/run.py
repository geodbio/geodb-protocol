#!/usr/bin/env python3
"""
The entry point CI calls, and the one to reach for from a bare checkout.

    python conformance/run.py --offline                  # no server, no creds
    python conformance/run.py --base-url URL --token TOK # against a server

``--offline`` runs the BREAK MATRIX: every assertion against a mock server
broken in exactly the one way that assertion exists to catch. That needs no
credentials and no network, which is why it is what GitHub CI runs — and it
is a stronger check than it sounds, because it proves each assertion both
passes against a correct implementation and fails against a wrong one.

The credentialed run against a real endpoint is a separate job in our own CI.

This file only forwards to the package so that a bare checkout works without
installing anything; the real CLI is ``python -m geodb_conformance``.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if '--offline' in argv:
        argv.remove('--offline')
        from geodb_conformance.__main__ import main as cli
        return cli(['selftest'] + argv)
    from geodb_conformance.__main__ import main as cli
    return cli(['read'] + argv)


if __name__ == '__main__':
    sys.exit(main())
