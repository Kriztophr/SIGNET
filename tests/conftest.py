from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.evals.models.entities  # noqa: F401 — register tables on Base.metadata
import app.platform.auth.models  # noqa: F401 — register tables on Base.metadata
import app.workflow.models.entities  # noqa: F401 — register tables on Base.metadata
from app.main import create_app
from app.platform.auth.models import Role
from app.platform.auth.service import AuthService
from app.platform.db.base import Base
from app.platform.db.session import get_db
from app.platform.ids.generator import new_uuid
from app.platform.storage.service import StorageService, get_storage


@pytest.fixture
def engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db(engine) -> Session:
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with factory() as session:
        yield session


@pytest.fixture
def storage(tmp_path: Path) -> StorageService:
    return StorageService(tmp_path / "storage")


@pytest.fixture
def client(db, storage) -> TestClient:
    application = create_app()
    application.dependency_overrides[get_db] = lambda: db
    application.dependency_overrides[get_storage] = lambda: storage
    return TestClient(application)


PASSWORD = "test-Password-1!"


def login_headers(client: TestClient, db: Session, role: Role, email: str, tenant_id=None) -> dict:
    """Create a user with the given role and return Authorization headers."""
    AuthService(db).create_user(
        tenant_id=tenant_id or new_uuid(),
        email=email,
        full_name=f"Test {role.value}",
        password=PASSWORD,
        role=role,
    )
    db.commit()
    response = client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def operator_headers(client, db) -> dict:
    return login_headers(client, db, Role.operator, "operator@example.com")


@pytest.fixture
def tenant_id(client, operator_headers):
    import uuid

    me = client.get("/users/me", headers=operator_headers).json()
    return uuid.UUID(me["tenant_id"])


@pytest.fixture
def evaluator_headers(client, db, tenant_id) -> dict:
    return login_headers(client, db, Role.evaluator, "evaluator@example.com", tenant_id=tenant_id)


@pytest.fixture
def reviewer_headers(client, db, tenant_id) -> dict:
    return login_headers(client, db, Role.reviewer, "reviewer@example.com", tenant_id=tenant_id)


@pytest.fixture
def admin_headers(client, db, tenant_id) -> dict:
    return login_headers(client, db, Role.admin, "admin@example.com", tenant_id=tenant_id)
