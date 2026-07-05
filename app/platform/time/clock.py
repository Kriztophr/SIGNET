from datetime import UTC, datetime


def utc_now() -> datetime:
    """The platform's single source of time: timezone-aware UTC."""
    return datetime.now(UTC)
