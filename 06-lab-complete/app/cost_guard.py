"""Track mock LLM spend against UTC daily and monthly budgets."""

from datetime import datetime, timezone

from fastapi import HTTPException

from app.config import settings
from app.redis_client import r


PRICE_INPUT_PER_1K = 0.00015
PRICE_OUTPUT_PER_1K = 0.0006


def _periods() -> list[tuple[str, float | None, int]]:
    now = datetime.now(timezone.utc)
    return [
        (f"day14:cost:daily:{now:%Y-%m-%d}", settings.daily_budget_usd, 86400),
        (f"day14:cost:monthly:{now:%Y-%m}", settings.monthly_budget_usd, 32 * 86400),
    ]


def check_budget() -> None:
    budgets = [(key, limit) for key, limit, _ in _periods() if limit is not None]
    if budgets:
        spends = r.mget([key for key, _ in budgets])
        if any(float(spend or 0) >= limit for (_, limit), spend in zip(budgets, spends)):
            raise HTTPException(status_code=402, detail="LLM budget exhausted")


def record_cost(input_tokens: int, output_tokens: int) -> float:
    cost = (input_tokens * PRICE_INPUT_PER_1K + output_tokens * PRICE_OUTPUT_PER_1K) / 1000
    with r.pipeline() as pipeline:
        for key, _, ttl in _periods():
            pipeline.incrbyfloat(key, cost)
            pipeline.expire(key, ttl)
        pipeline.execute()
    return cost
