import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.main import create_app
from app.platform.auth.models import Role
from app.platform.auth.service import MIN_PASSWORD_LENGTH, AuthService
from app.platform.auth.tokens import ALGORITHM, ISSUER
from app.platform.errors import DomainValidationError
from app.platform.ids.generator import new_uuid
from app.platform.settings.config import (
    Settings,
    get_settings,
    validate_production_settings,
)
from tests.conftest import login_headers

# Endpoints that are legitimately reachable without a bearer token.
PUBLIC_PATHS = {"/health", "/auth/login"}


def _all_protected_routes() -> list[tuple[str, str]]:
    routes = []
    for path, operations in create_app().openapi()["paths"].items():
        if path in PUBLIC_PATHS:
            continue
        for method in operations:
            routes.append((method.upper(), path))
    return sorted(routes)


@pytest.mark.parametrize(("method", "path"), _all_protected_routes())
def test_every_endpoint_requires_authentication(client, method, path) -> None:
    """Sweep: no route except /health and /auth/login may answer without a token."""
    concrete = path
    while "{" in concrete:
        start, end = concrete.index("{"), concrete.index("}")
        concrete = concrete[:start] + str(uuid.uuid4()) + concrete[end + 1 :]
    response = client.request(method, concrete, json={})
    assert response.status_code == 401, f"{method} {path} answered {response.status_code}"


def test_expired_token_rejected(client, db, tenant_id) -> None:
    payload = {
        "iss": ISSUER,
        "sub": str(new_uuid()),
        "tenant_id": str(tenant_id),
        "role": "admin",
        "iat": datetime.now(UTC) - timedelta(hours=2),
        "exp": datetime.now(UTC) - timedelta(hours=1),
    }
    token = jwt.encode(payload, get_settings().secret_key, algorithm=ALGORITHM)
    response = client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_token_with_wrong_signature_rejected(client) -> None:
    payload = {
        "iss": ISSUER,
        "sub": str(new_uuid()),
        "tenant_id": str(new_uuid()),
        "role": "admin",
        "exp": datetime.now(UTC) + timedelta(hours=1),
    }
    token = jwt.encode(payload, "attacker-controlled-key-of-decent-length", algorithm=ALGORITHM)
    response = client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_token_without_issuer_rejected(client, db) -> None:
    headers = login_headers(client, db, Role.operator, "iss-test@example.com")
    # A forged token missing iss/exp claims must fail even with the right key.
    bare = jwt.encode({"sub": str(new_uuid())}, get_settings().secret_key, algorithm=ALGORITHM)
    assert client.get("/users/me", headers={"Authorization": f"Bearer {bare}"}).status_code == 401
    # Sanity: the legitimately issued token still works.
    assert client.get("/users/me", headers=headers).status_code == 200


def test_login_throttled_after_repeated_failures(client, db) -> None:
    email = f"throttle-{uuid.uuid4().hex[:8]}@example.com"
    AuthService(db).create_user(
        tenant_id=new_uuid(),
        email=email,
        full_name="Throttle Target",
        password="correct-horse-battery",
        role=Role.operator,
    )
    db.commit()

    for _ in range(get_settings().login_max_failures):
        wrong = client.post("/auth/login", json={"email": email, "password": "wrong-password"})
        assert wrong.status_code == 401

    # Budget exhausted: even the CORRECT password is refused until the window passes.
    throttled = client.post(
        "/auth/login", json={"email": email, "password": "correct-horse-battery"}
    )
    assert throttled.status_code == 429


def test_successful_login_resets_throttle(client, db) -> None:
    email = f"reset-{uuid.uuid4().hex[:8]}@example.com"
    AuthService(db).create_user(
        tenant_id=new_uuid(),
        email=email,
        full_name="Reset Target",
        password="correct-horse-battery",
        role=Role.operator,
    )
    db.commit()

    for _ in range(get_settings().login_max_failures - 1):
        client.post("/auth/login", json={"email": email, "password": "wrong"})
    ok = client.post("/auth/login", json={"email": email, "password": "correct-horse-battery"})
    assert ok.status_code == 200
    # The window is clean again after success.
    wrong = client.post("/auth/login", json={"email": email, "password": "wrong"})
    assert wrong.status_code == 401  # not 429


def test_password_policy_enforced(db) -> None:
    with pytest.raises(DomainValidationError, match=str(MIN_PASSWORD_LENGTH)):
        AuthService(db).create_user(
            tenant_id=new_uuid(),
            email="weak@example.com",
            full_name="Weak",
            password="short",
            role=Role.operator,
        )


def test_security_headers_present(client) -> None:
    response = client.get("/health")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"


def test_production_settings_fail_closed() -> None:
    insecure = Settings(environment="production")
    with pytest.raises(RuntimeError, match="insecure production configuration"):
        validate_production_settings(insecure)

    with pytest.raises(RuntimeError, match="ICM_ALLOWED_HOSTS"):
        validate_production_settings(
            Settings(
                environment="production",
                secret_key="x" * 48,
                allowed_hosts="*",
            )
        )

    # A correctly configured production environment boots.
    validate_production_settings(
        Settings(
            environment="production",
            secret_key="x" * 48,
            allowed_hosts="api.example.com",
        )
    )

    # Development defaults remain valid without any configuration.
    validate_production_settings(Settings())
