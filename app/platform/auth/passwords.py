from functools import lru_cache

import bcrypt

# bcrypt only uses the first 72 bytes; reject longer input instead of silently truncating.
MAX_PASSWORD_BYTES = 72


def hash_password(password: str) -> str:
    raw = password.encode()
    if len(raw) > MAX_PASSWORD_BYTES:
        raise ValueError(f"password exceeds {MAX_PASSWORD_BYTES} bytes")
    return bcrypt.hashpw(raw, bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    raw = password.encode()
    if len(raw) > MAX_PASSWORD_BYTES:
        return False
    try:
        return bcrypt.checkpw(raw, hashed.encode())
    except ValueError:
        return False


@lru_cache
def dummy_hash() -> str:
    """Hash compared against when the user does not exist, keeping login timing
    indistinguishable between unknown-user and wrong-password failures."""
    return hash_password("not-a-real-password")
