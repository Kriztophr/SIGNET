import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.platform.auth.models  # noqa: F401 — register tables on Base.metadata
from app.main import create_app
from app.platform.db.base import Base
from app.platform.db.session import get_db


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
def client(db) -> TestClient:
    application = create_app()
    application.dependency_overrides[get_db] = lambda: db
    return TestClient(application)
