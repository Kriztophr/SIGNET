"""Seed role demo accounts into the tenant.

Creates 6 role-specific demo accounts so non-admin roles can be tested cleanly.

Usage:
    python -m app.platform.seed.demo_users
"""

from __future__ import annotations

import sys

from app.platform.auth.models import Role, User
from app.platform.auth.service import AuthService
from app.platform.db.session import get_sessionmaker


DEMO_USERS = [
    ("operator@signet.local", "Signet Operator", Role.operator, "SignetOperator123!"),
    ("reviewer@signet.local", "Signet Reviewer", Role.reviewer, "SignetReviewer123!"),
    ("evaluator@signet.local", "Signet Evaluator", Role.evaluator, "SignetEvaluator123!"),
    ("auditor@signet.local", "Signet Auditor", Role.auditor, "SignetAuditor123!"),
    ("manager@signet.local", "Signet Environment Manager", Role.environment_manager, "SignetManager123!"),
    ("resilience@signet.local", "Signet Resilience Manager", Role.resilience_manager, "SignetResilience123!"),
]


def main() -> int:
    with get_sessionmaker()() as session:
        first_user = session.query(User).first()
        if not first_user:
            print("No users/tenants in system yet — run bootstrap first", file=sys.stderr)
            return 0

        tenant_id = first_user.tenant_id
        service = AuthService(session)

        created_count = 0
        for email, full_name, role, password in DEMO_USERS:
            if service.get_by_email(email) is None:
                service.create_user(
                    tenant_id=tenant_id,
                    email=email,
                    full_name=full_name,
                    password=password,
                    role=role,
                )
                created_count += 1

        session.commit()
        print(f"seeded {created_count} demo user accounts for tenant {tenant_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
