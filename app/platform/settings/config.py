from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Platform configuration, sourced from environment variables with the ICM_ prefix.

    Defaults are safe for local development only; production deployments must
    supply real values via the environment (never committed .env files).
    """

    model_config = SettingsConfigDict(env_prefix="ICM_", env_file=".env", extra="ignore")

    app_name: str = "icm-platform"
    app_version: str = "0.1.0"
    environment: str = "development"
    debug: bool = False

    database_url: str = "postgresql+psycopg://icm:icm@localhost:5432/icm"
    redis_url: str = "redis://localhost:6379/0"

    secret_key: str = "dev-only-change-me-never-use-in-production"
    access_token_expire_minutes: int = 60

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
