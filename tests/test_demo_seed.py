"""Demo-account seeding is opt-in and self-healing: without the env gate it
never creates accounts and deactivates any left over from an earlier seed."""

import uuid

from app.platform.auth.models import Role
from app.platform.auth.service import AuthService
from app.platform.seed.demo_users import DEMO_USERS, reconcile_demo_users


def test_seed_does_nothing_without_the_env_gate(db, monkeypatch) -> None:
    """With ICM_SEED_DEMO_USERS unset, no demo accounts are ever created."""
    monkeypatch.delenv("ICM_SEED_DEMO_USERS", raising=False)
    code, _ = reconcile_demo_users(db)
    assert code == 0
    service = AuthService(db)
    for email, _name, _role in DEMO_USERS:
        assert service.get_by_email(email) is None


def test_seed_refuses_without_a_password(db, monkeypatch) -> None:
    """The gate alone is not enough: seeding without a strong password from the
    environment fails instead of falling back to anything hardcoded."""
    monkeypatch.setenv("ICM_SEED_DEMO_USERS", "1")
    monkeypatch.delenv("ICM_DEMO_USERS_PASSWORD", raising=False)
    code, message = reconcile_demo_users(db)
    assert code == 1
    assert "refusing to seed" in message
    monkeypatch.setenv("ICM_DEMO_USERS_PASSWORD", "short")
    code, _ = reconcile_demo_users(db)
    assert code == 1


def test_seed_creates_all_roles_when_opted_in(db, monkeypatch) -> None:
    """With gate + password set, all six role accounts land in the first tenant."""
    tenant_id = uuid.uuid4()
    AuthService(db).create_user(
        tenant_id=tenant_id,
        email="bootstrap@example.com",
        full_name="Bootstrap Admin",
        password="bootstrap-Pass-1!",
        role=Role.admin,
    )
    db.commit()
    monkeypatch.setenv("ICM_SEED_DEMO_USERS", "1")
    monkeypatch.setenv("ICM_DEMO_USERS_PASSWORD", "demo-Password-1!")
    code, _ = reconcile_demo_users(db)
    assert code == 0
    service = AuthService(db)
    for email, _name, role in DEMO_USERS:
        user = service.get_by_email(email)
        assert user is not None
        assert user.role is role
        assert user.tenant_id == tenant_id
        assert user.is_active


def test_redeploy_without_gate_deactivates_seeded_accounts(db, monkeypatch) -> None:
    """A production redeploy with the gate off locks out previously seeded demo
    accounts — the entrypoint run self-heals an environment seeded by mistake."""
    AuthService(db).create_user(
        tenant_id=uuid.uuid4(),
        email="bootstrap@example.com",
        full_name="Bootstrap Admin",
        password="bootstrap-Pass-1!",
        role=Role.admin,
    )
    db.commit()
    monkeypatch.setenv("ICM_SEED_DEMO_USERS", "1")
    monkeypatch.setenv("ICM_DEMO_USERS_PASSWORD", "demo-Password-1!")
    assert reconcile_demo_users(db)[0] == 0

    monkeypatch.delenv("ICM_SEED_DEMO_USERS")
    code, message = reconcile_demo_users(db)
    assert code == 0
    assert "deactivated 6" in message
    service = AuthService(db)
    for email, _name, _role in DEMO_USERS:
        assert not service.get_by_email(email).is_active
        assert service.authenticate(email, "demo-Password-1!") is None
