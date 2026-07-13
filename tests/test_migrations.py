from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

REPO_ROOT = Path(__file__).resolve().parents[1]


def _config(db_url: str) -> Config:
    cfg = Config(str(REPO_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(REPO_ROOT / "migrations"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def test_migrations_upgrade_and_downgrade(tmp_path) -> None:
    """The full database migration chain walks up and back down cleanly on a
    fresh database."""
    url = f"sqlite:///{(tmp_path / 'mig.db').as_posix()}"
    cfg = _config(url)

    command.upgrade(cfg, "head")
    engine = create_engine(url)
    assert "users" in inspect(engine).get_table_names()
    engine.dispose()

    command.downgrade(cfg, "base")
    engine = create_engine(url)
    assert "users" not in inspect(engine).get_table_names()
    engine.dispose()
