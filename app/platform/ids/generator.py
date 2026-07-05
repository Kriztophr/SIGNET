import uuid


def new_uuid() -> uuid.UUID:
    """Time-ordered UUIDv7: sortable by creation time, safe as a primary key."""
    return uuid.uuid7()
