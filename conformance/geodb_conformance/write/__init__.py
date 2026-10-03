"""
The WRITE half of the suite: ``python -m geodb_conformance write``.

Kept apart from the read half on purpose. The read profile is published; the
write profile (``contract/write-profile.json``) carries its own version and a
``status`` — ``dark`` until the write half is live on geoDB's production
servers. Its assertions live in their own registry, so ``read`` and its break
matrix are byte-for-byte what they were, and a server that implements only
the read half is never failed for a write it does not serve.

Every assertion WRITES. Point it at a project you may write test data into —
geoDB's public write twin (reset nightly) or your own staging server. Each
assertion creates its own uniquely named rows, and the run ends by undoing
every write it made (``--keep`` leaves them for inspection).
"""

from ..harness import Registry

#: The write half's one registry (the read half's is ``harness.REGISTRY``).
WRITE_REGISTRY = Registry()


def load_write_checks():
    """Import the write checks, populating ``WRITE_REGISTRY``. Idempotent."""
    from . import checks  # noqa: F401
    return WRITE_REGISTRY
