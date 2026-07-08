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
    storage_root: str = "./data/storage"

    secret_key: str = "dev-only-change-me-never-use-in-production"
    access_token_expire_minutes: int = 60

    # Comma-separated Host allowlist; "*" is acceptable only outside production.
    allowed_hosts: str = "*"

    login_max_failures: int = 5
    login_window_seconds: int = 900

    # LLM execution (spec §28.7). Empty api key disables agent execution —
    # automated stages degrade gracefully to manual completion (fail open to
    # humans, never to silence). Charter 2026-07-08: Opus drafts, Haiku judges,
    # $50/month hard cap enforced fail-closed by the usage ledger.
    anthropic_api_key: str = ""
    llm_executor_model: str = "claude-opus-4-8"
    llm_judge_model: str = "claude-haiku-4-5"
    llm_monthly_budget_usd: float = 50.0
    llm_max_output_tokens: int = 16000

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def allowed_hosts_list(self) -> list[str]:
        return [host.strip() for host in self.allowed_hosts.split(",") if host.strip()]


INSECURE_DEFAULT_SECRET = "dev-only-change-me-never-use-in-production"


def validate_production_settings(settings: Settings) -> None:
    """Fail closed: refuse to boot production with insecure configuration."""
    if not settings.is_production:
        return
    problems = []
    if settings.secret_key == INSECURE_DEFAULT_SECRET or len(settings.secret_key) < 32:
        problems.append("ICM_SECRET_KEY must be a strong random value of at least 32 characters")
    if settings.debug:
        problems.append("ICM_DEBUG must be false in production")
    if settings.allowed_hosts.strip() in ("", "*"):
        problems.append("ICM_ALLOWED_HOSTS must name the real hostname(s), not '*'")
    if problems:
        raise RuntimeError("insecure production configuration: " + "; ".join(problems))


@lru_cache
def get_settings() -> Settings:
    return Settings()
