import pytest
from fastapi import HTTPException

from app.platform.auth.dependencies import require_roles
from app.platform.auth.models import Role, User
from app.platform.auth.passwords import hash_password, verify_password
from app.platform.auth.service import AuthService
from app.platform.ids.generator import new_uuid

PASSWORD = "s3cure-Passw0rd!"


@pytest.fixture
def user(db) -> User:
    created = AuthService(db).create_user(
        tenant_id=new_uuid(),
        email="Admin@Example.com",
        full_name="Platform Admin",
        password=PASSWORD,
        role=Role.admin,
    )
    db.commit()
    return created


def test_password_hash_roundtrip() -> None:
    """A password verifies against its own bcrypt hash and nothing else."""
    hashed = hash_password(PASSWORD)
    assert hashed != PASSWORD
    assert verify_password(PASSWORD, hashed)
    assert not verify_password("wrong", hashed)


def test_password_over_72_bytes_rejected() -> None:
    with pytest.raises(ValueError):
        hash_password("x" * 73)
    assert not verify_password("x" * 73, hash_password("x" * 72))


def test_email_is_normalized_lowercase(user) -> None:
    assert user.email == "admin@example.com"


def test_login_and_me_flow(client, user) -> None:
    """A valid login returns a token that identifies the user on /users/me."""
    login = client.post("/auth/login", json={"email": "admin@example.com", "password": PASSWORD})
    assert login.status_code == 200
    token = login.json()["access_token"]

    me = client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    body = me.json()
    assert body["email"] == "admin@example.com"
    assert body["role"] == "admin"
    assert body["id"] == str(user.id)


def test_login_wrong_password_rejected(client, user) -> None:
    response = client.post("/auth/login", json={"email": "admin@example.com", "password": "wrong"})
    assert response.status_code == 401


def test_login_unknown_user_rejected(client) -> None:
    response = client.post(
        "/auth/login", json={"email": "nobody@example.com", "password": "whatever"}
    )
    assert response.status_code == 401


def test_inactive_user_cannot_login(client, db, user) -> None:
    user.is_active = False
    db.flush()
    response = client.post("/auth/login", json={"email": "admin@example.com", "password": PASSWORD})
    assert response.status_code == 401


def test_me_requires_token(client) -> None:
    """The identity endpoint is refused without a token."""
    assert client.get("/users/me").status_code == 401


def test_me_rejects_garbage_token(client) -> None:
    """The identity endpoint is refused for a malformed token."""
    response = client.get("/users/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert response.status_code == 401


def _user_with_role(role: Role) -> User:
    return User(
        tenant_id=new_uuid(),
        email=f"{role.value}@example.com",
        full_name="Test",
        hashed_password="irrelevant",
        role=role,
    )


def test_require_roles_allows_matching_role() -> None:
    checker = require_roles(Role.reviewer)
    reviewer = _user_with_role(Role.reviewer)
    assert checker(user=reviewer) is reviewer


def test_require_roles_always_allows_admin() -> None:
    checker = require_roles(Role.reviewer)
    admin = _user_with_role(Role.admin)
    assert checker(user=admin) is admin


def test_require_roles_rejects_other_roles() -> None:
    checker = require_roles(Role.reviewer)
    with pytest.raises(HTTPException) as exc:
        checker(user=_user_with_role(Role.operator))
    assert exc.value.status_code == 403
