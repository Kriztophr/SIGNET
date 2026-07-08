import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

# Import every module that defines tables so they register on Base.metadata.
import app.environment.models.entities  # noqa: F401,E402
import app.evals.models.entities  # noqa: F401,E402
import app.governance.models.entities  # noqa: F401,E402
import app.platform.auth.models  # noqa: F401,E402
import app.platform.llm.models  # noqa: F401,E402
import app.resilience.models.entities  # noqa: F401,E402
import app.workflow.models.entities  # noqa: F401,E402
from app.platform.db.base import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def _database_url() -> str:
    configured = config.get_main_option("sqlalchemy.url")
    if configured:
        return configured
    env_url = os.environ.get("ICM_DATABASE_URL")
    if env_url:
        return env_url
    from app.platform.settings.config import get_settings

    return get_settings().database_url


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(_database_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
