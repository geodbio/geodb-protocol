"""The checks. Importing this package populates the registry.

Order matters only for readability: the registry preserves decoration order,
and that is the order the report prints. Auth first (nothing else means
anything if the credential is not accepted), then the envelope, then the
vocabulary, then the lanes.
"""

from . import auth, envelope, schemas, coordinates, sync, discovery, stac, exports, errors  # noqa: F401,E501
