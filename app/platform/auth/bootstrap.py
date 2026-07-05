"""Create the initial admin user from environment variables.

Usage (inside the api container or a dev shell):

    ICM_BOOTSTRAP_ADMIN_EMAIL=admin@example.com \
    ICM_BOOTSTRAP_ADMIN_PASSWORD=... \
    python -m app.platform.auth.bootstrap

Idempotent: exits successfully without changes if the user already exists.
"""

import os
import sys
import uuid

from app.platform.auth.models import Role
from app.platform.auth.service import AuthService
from app.platform.db.session import get_sessionmaker
from app.platform.ids.generator import new_uuid


def main() -> int:
    email = os.environ.get("ICM_BOOTSTRAP_ADMIN_EMAIL")
    password = os.environ.get("ICM_BOOTSTRAP_ADMIN_PASSWORD")
    if not email or not password:
        print(
            "ICM_BOOTSTRAP_ADMIN_EMAIL and ICM_BOOTSTRAP_ADMIN_PASSWORD are required",
            file=sys.stderr,
        )
        return 1

    raw_tenant = os.environ.get("ICM_BOOTSTRAP_TENANT_ID")
    tenant_id = uuid.UUID(raw_tenant) if raw_tenant else new_uuid()

    with get_sessionmaker()() as session:
        service = AuthService(session)
        if service.get_by_email(email) is not None:
            print(f"user {email} already exists; nothing to do")
            return 0
        user = service.create_user(
            tenant_id=tenant_id,
            email=email,
            full_name=os.environ.get("ICM_BOOTSTRAP_ADMIN_NAME", "Platform Admin"),
            password=password,
            role=Role.admin,
        )
        session.commit()
        print(f"created admin {user.email} (tenant {user.tenant_id})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
