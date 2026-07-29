"""Password recovery and self-service change.

Two authority models: the reset CLI trusts database access (operator recovery),
while the endpoint trusts the current password (so a stolen token alone cannot
lock an owner out of their own account).
"""

import uuid

import pytest

from app.platform.auth.models import Role
from app.platform.auth.reset_password import main as reset_main
from app.platform.auth.service import AuthService
from app.platform.errors import DomainValidationError
from tests.conftest import PASSWORD, login_headers

NEW_PASSWORD = "brand-New-Password-9!"


def _make_user(db, email="reset-me@example.com", role=Role.admin):
    user = AuthService(db).create_user(
        tenant_id=uuid.uuid4(),
        email=email,
        full_name="Reset Target",
        password=PASSWORD,
        role=role,
    )
    db.commit()
    return user


# --------------------------------------------------------------------------- #
# Operator recovery path (the CLI)
# --------------------------------------------------------------------------- #


def test_reset_cli_sets_a_working_password(db, monkeypatch) -> None:
    """The recovery path an operator runs when the admin password is lost."""
    _make_user(db)
    monkeypatch.setattr("app.platform.auth.reset_password.get_sessionmaker", lambda: lambda: db)
    monkeypatch.setenv("ICM_RESET_EMAIL", "reset-me@example.com")
    monkeypatch.setenv("ICM_RESET_PASSWORD", NEW_PASSWORD)

    assert reset_main() == 0

    service = AuthService(db)
    assert service.authenticate("reset-me@example.com", NEW_PASSWORD) is not None
    assert service.authenticate("reset-me@example.com", PASSWORD) is None


def test_reset_cli_reactivates_a_disabled_account(db, monkeypatch) -> None:
    """Recovery also un-disables, so a deactivated admin is not a dead end."""
    user = _make_user(db)
    user.is_active = False
    db.commit()
    monkeypatch.setattr("app.platform.auth.reset_password.get_sessionmaker", lambda: lambda: db)
    monkeypatch.setenv("ICM_RESET_EMAIL", "reset-me@example.com")
    monkeypatch.setenv("ICM_RESET_PASSWORD", NEW_PASSWORD)

    assert reset_main() == 0
    assert AuthService(db).authenticate("reset-me@example.com", NEW_PASSWORD) is not None


def test_reset_cli_fails_loudly_on_unknown_user(db, monkeypatch) -> None:
    """A typo'd email must not look like a successful reset."""
    monkeypatch.setattr("app.platform.auth.reset_password.get_sessionmaker", lambda: lambda: db)
    monkeypatch.setenv("ICM_RESET_EMAIL", "nobody@example.com")
    monkeypatch.setenv("ICM_RESET_PASSWORD", NEW_PASSWORD)

    assert reset_main() == 1


def test_reset_cli_requires_both_env_vars(db, monkeypatch) -> None:
    monkeypatch.delenv("ICM_RESET_EMAIL", raising=False)
    monkeypatch.delenv("ICM_RESET_PASSWORD", raising=False)
    assert reset_main() == 1


def test_reset_refuses_a_weak_password(db) -> None:
    """The minimum-length floor holds on the recovery path too."""
    user = _make_user(db)
    with pytest.raises(DomainValidationError):
        AuthService(db).set_password(user, "short")


# --------------------------------------------------------------------------- #
# Self-service path (the endpoint)
# --------------------------------------------------------------------------- #


def test_change_password_rotates_the_credential(client, db) -> None:
    headers = login_headers(client, db, Role.operator, "rotator@example.com")

    response = client.post(
        "/auth/change-password",
        headers=headers,
        json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
    )
    assert response.status_code == 200, response.text
    assert response.json()["access_token"]

    assert (
        client.post(
            "/auth/login", json={"email": "rotator@example.com", "password": NEW_PASSWORD}
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/auth/login", json={"email": "rotator@example.com", "password": PASSWORD}
        ).status_code
        == 401
    )


def test_change_password_requires_the_current_password(client, db) -> None:
    """A valid token is not enough — otherwise a stolen token locks the owner out."""
    headers = login_headers(client, db, Role.operator, "guarded@example.com")

    response = client.post(
        "/auth/change-password",
        headers=headers,
        json={"current_password": "not-the-password", "new_password": NEW_PASSWORD},
    )
    assert response.status_code == 422

    # The original credential is untouched by the failed attempt.
    assert (
        client.post(
            "/auth/login", json={"email": "guarded@example.com", "password": PASSWORD}
        ).status_code
        == 200
    )


def test_change_password_enforces_the_length_floor(client, db) -> None:
    headers = login_headers(client, db, Role.operator, "shortie@example.com")

    response = client.post(
        "/auth/change-password",
        headers=headers,
        json={"current_password": PASSWORD, "new_password": "short"},
    )
    assert response.status_code == 422
    assert (
        client.post(
            "/auth/login", json={"email": "shortie@example.com", "password": PASSWORD}
        ).status_code
        == 200
    )


def test_change_password_rejects_anonymous_callers(client) -> None:
    response = client.post(
        "/auth/change-password",
        json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
    )
    assert response.status_code in (401, 403)
