"""
geodb-conformance — does this server implement the geoDB Open Exploration
Protocol?

    python -m geodb_conformance read --base-url https://api.geodb.io --token $GEODB_TOKEN

Point it at your own server. Every assertion is named and carries a one-line
statement of the contract clause it establishes, so the markdown report reads
as the contract with a verdict beside each clause.

The suite ships its own copy of the published contract — ``spec/openapi.yaml``,
``schemas/*.json``, ``errors.json`` — and checks your server against THAT,
never against a spec fetched from the server under test.
"""

from .harness import REGISTRY, Assertion, Failed, Result, Skipped  # noqa: F401

__version__ = '0.1.0'

#: The protocol version this suite's packaged contract describes. Read from
#: the packaged spec at call time rather than pinned here, so the two cannot
#: drift.
def protocol_version():
    from .session import Contract
    return Contract().version


def load_checks():
    """Import every check module, populating the registry. Idempotent."""
    from .checks import (auth, coordinates, discovery, envelope,  # noqa: F401
                         errors, exports, schemas, stac)
    return REGISTRY
