"""Application UUIDv7 generation, independent of existing database defaults."""

from uuid import UUID, uuid7


def new_uuid7() -> UUID:
    """Generate a standard UUID using Python 3.14; never fall back to UUIDv4."""
    return uuid7()
