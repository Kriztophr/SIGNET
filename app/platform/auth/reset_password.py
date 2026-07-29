"""Reset a user's password from the environment (operator recovery path).

Authority here is database access: anyone who can run this module already
controls the deployment, so no current password is required. Self-service
change (which does require the current password) is POST /auth/change-password.

Usage (inside the api container or a dev shell):

    ICM_RESET_EMAIL=admin@example.com \
    ICM_RESET_PASSWORD=... \
    python -m app.platform.auth.reset_password

Also reactivates the account, so this doubles as the recovery path for a user
who was deactivated. Exits non-zero when the user does not exist, so a typo
fails loudly instead of looking like success.
"""

import os
import sys

from app.platform.auth.service import AuthService
from app.platform.db.session import get_sessionmaker


def main() -> int:
    email = os.environ.get("ICM_RESET_EMAIL")
    password = os.environ.get("ICM_RESET_PASSWORD")
    if not email or not password:
        print(
            "ICM_RESET_EMAIL and ICM_RESET_PASSWORD are required",
            file=sys.stderr,
        )
        return 1

    with get_sessionmaker()() as session:
        service = AuthService(session)
        user = service.get_by_email(email)
        if user is None:
            print(f"no user with email {email!r}", file=sys.stderr)
            return 1
        service.set_password(user, password)
        reactivated = not user.is_active
        user.is_active = True
        session.commit()
        suffix = " (account reactivated)" if reactivated else ""
        print(f"password reset for {user.email}{suffix}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
