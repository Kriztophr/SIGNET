import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.platform.auth.models import Role, User
from app.platform.auth.passwords import dummy_hash, hash_password, verify_password
from app.platform.errors import DomainValidationError

MIN_PASSWORD_LENGTH = 12


class AuthService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create_user(
        self,
        *,
        tenant_id: uuid.UUID,
        email: str,
        full_name: str,
        password: str,
        role: Role,
    ) -> User:
        if len(password) < MIN_PASSWORD_LENGTH:
            raise DomainValidationError(
                f"password must be at least {MIN_PASSWORD_LENGTH} characters"
            )
        user = User(
            tenant_id=tenant_id,
            email=email.strip().lower(),
            full_name=full_name,
            hashed_password=hash_password(password),
            role=role,
        )
        self._session.add(user)
        self._session.flush()
        return user

    def get_by_email(self, email: str) -> User | None:
        return self._session.scalar(select(User).where(User.email == email.strip().lower()))

    def authenticate(self, email: str, password: str) -> User | None:
        """Returns the user on success, None on any failure (fail closed)."""
        user = self.get_by_email(email)
        if user is None:
            verify_password(password, dummy_hash())
            return None
        if not verify_password(password, user.hashed_password):
            return None
        if not user.is_active:
            return None
        return user
