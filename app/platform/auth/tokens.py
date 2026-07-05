from datetime import timedelta
from typing import Any

import jwt

from app.platform.auth.models import User
from app.platform.settings.config import get_settings
from app.platform.time.clock import utc_now

ALGORITHM = "HS256"
ISSUER = "icm-platform"


def create_access_token(user: User) -> str:
    settings = get_settings()
    now = utc_now()
    payload = {
        "iss": ISSUER,
        "sub": str(user.id),
        "tenant_id": str(user.tenant_id),
        "role": user.role.value,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """Raises jwt.InvalidTokenError on any invalid, expired, or tampered token."""
    return jwt.decode(
        token,
        get_settings().secret_key,
        algorithms=[ALGORITHM],
        issuer=ISSUER,
        options={"require": ["exp", "iss", "sub"]},
    )
