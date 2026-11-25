"""Runtime configuration for the agent."""

from dataclasses import dataclass, field
import os


def _daily_budget() -> float | None:
    default = "" if os.getenv("MONTHLY_BUDGET_USD") else "1.0"
    return _optional_float("DAILY_BUDGET_USD", default)


def _optional_float(name: str, default: str = "") -> float | None:
    value = os.getenv(name, default)
    return float(value) if value else None


@dataclass
class Settings:
    port: int = field(default_factory=lambda: int(os.getenv("PORT", "8000")))
    environment: str = field(default_factory=lambda: os.getenv("ENVIRONMENT", "development"))
    agent_api_key: str = field(default_factory=lambda: os.getenv("AGENT_API_KEY", ""))
    redis_url: str = field(default_factory=lambda: os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0"))
    rate_limit_per_minute: int = field(default_factory=lambda: int(os.getenv("RATE_LIMIT_PER_MINUTE", "10")))
    daily_budget_usd: float | None = field(default_factory=_daily_budget)
    monthly_budget_usd: float | None = field(default_factory=lambda: _optional_float("MONTHLY_BUDGET_USD"))


settings = Settings()
