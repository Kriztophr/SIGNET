import enum
import uuid

from sqlalchemy import Boolean, Enum, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.db.base import Base, TimestampedMixin, UuidPkMixin


class Role(enum.StrEnum):
    """Platform roles per spec section 20."""

    admin = "admin"
    operator = "operator"
    reviewer = "reviewer"
    evaluator = "evaluator"
    auditor = "auditor"
    environment_manager = "environment_manager"
    resilience_manager = "resilience_manager"


class User(UuidPkMixin, TimestampedMixin, Base):
    __tablename__ = "users"

    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[Role] = mapped_column(Enum(Role, native_enum=False, length=50), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
