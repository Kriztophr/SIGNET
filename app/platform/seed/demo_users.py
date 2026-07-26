"""Seed role demo accounts into the tenant.

Creates 6 role-specific demo accounts so non-admin roles can be tested cleanly.

Security gate: seeding only happens when ICM_SEED_DEMO_USERS is truthy AND
ICM_DEMO_USERS_PASSWORD is set — passwords are never stored in the repo.
When the flag is off (the default, and always on production), any demo
accounts that exist from an earlier deploy are deactivated instead, so a
redeploy self-heals an environment that was seeded by mistake.

Usage:
    ICM_SEED_DEMO_USERS=1 ICM_DEMO_USERS_PASSWORD=... python -m app.platform.seed.demo_users
"""

from __future__ import annotations

import os
import sys

from sqlalchemy.orm import Session

from app.platform.auth.models import Role, User
from app.platform.auth.service import MIN_PASSWORD_LENGTH, AuthService
from app.platform.db.session import get_sessionmaker

# example.com passes the login schema's EmailStr validation; .local does not.
DEMO_USERS = [
    ("demo-operator@example.com", "Signet Operator", Role.operator),
    ("demo-reviewer@example.com", "Signet Reviewer", Role.reviewer),
    ("demo-evaluator@example.com", "Signet Evaluator", Role.evaluator),
    ("demo-auditor@example.com", "Signet Auditor", Role.auditor),
    ("demo-manager@example.com", "Signet Environment Manager", Role.environment_manager),
    ("demo-resilience@example.com", "Signet Resilience Manager", Role.resilience_manager),
]

# An earlier deploy seeded these. EmailStr rejects .local at /auth/login so
# they could never authenticate, but they still get deactivated on sight.
LEGACY_DEMO_EMAILS = [
    "operator@signet.local",
    "reviewer@signet.local",
    "evaluator@signet.local",
    "auditor@signet.local",
    "manager@signet.local",
    "resilience@signet.local",
]


def _flag_enabled() -> bool:
    return os.environ.get("ICM_SEED_DEMO_USERS", "").strip().lower() in {"1", "true", "yes"}


def _deactivate(service: AuthService, emails: list[str]) -> int:
    deactivated = 0
    for email in emails:
        user = service.get_by_email(email)
        if user is not None and user.is_active:
            user.is_active = False
            deactivated += 1
    return deactivated


def reconcile_demo_users(session: Session) -> tuple[int, str]:
    """Seed or deactivate demo accounts per the env gate. Returns (exit_code, message)."""
    service = AuthService(session)

    # Legacy .local accounts are dead weight in any environment: purge always.
    legacy_deactivated = _deactivate(service, LEGACY_DEMO_EMAILS)
    session.commit()

    if not _flag_enabled():
        deactivated = legacy_deactivated + _deactivate(
            service, [email for email, _full_name, _role in DEMO_USERS]
        )
        session.commit()
        if deactivated:
            return 0, f"ICM_SEED_DEMO_USERS not set — deactivated {deactivated} demo account(s)"
        return 0, "ICM_SEED_DEMO_USERS not set — nothing to do"

    password = os.environ.get("ICM_DEMO_USERS_PASSWORD", "")
    if len(password) < MIN_PASSWORD_LENGTH:
        return 1, (
            "ICM_DEMO_USERS_PASSWORD missing or shorter than "
            f"{MIN_PASSWORD_LENGTH} characters — refusing to seed"
        )

    first_user = session.query(User).first()
    if not first_user:
        return 0, "No users/tenants in system yet — run bootstrap first"

    tenant_id = first_user.tenant_id
    created_count = 0
    reactivated_count = 0
    for email, full_name, role in DEMO_USERS:
        existing = service.get_by_email(email)
        if existing is None:
            service.create_user(
                tenant_id=tenant_id,
                email=email,
                full_name=full_name,
                password=password,
                role=role,
            )
            created_count += 1
        elif not existing.is_active:
            existing.is_active = True
            reactivated_count += 1

    session.commit()
    return 0, (
        f"seeded {created_count} and reactivated {reactivated_count} "
        f"demo user accounts for tenant {tenant_id}"
    )


def main() -> int:
    with get_sessionmaker()() as session:
        code, message = reconcile_demo_users(session)
    print(message, file=sys.stderr if code else sys.stdout)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
