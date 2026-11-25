"""Production AI agent for the Day 14 lab."""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
import json
import logging
from time import perf_counter

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from redis import RedisError

from app.auth import verify_api_key
from app.config import settings
from app.cost_guard import check_budget, record_cost
from app.rate_limiter import check_rate_limit
from app.redis_client import r, redis_healthy
from utils.mock_llm import ask as llm_ask


logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def log_event(event: str, **fields) -> None:
    logger.info(json.dumps({
        "ts": datetime.now(timezone.utc).isoformat(),
        "level": "INFO",
        "environment": settings.environment,
        "event": event,
        **fields,
    }))


@asynccontextmanager
async def lifespan(app: FastAPI):
    log_event("startup")
    try:
        yield
    finally:
        r.close()
        log_event("shutdown")


app = FastAPI(title="Production AI Agent", lifespan=lifespan)


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)


@app.middleware("http")
async def log_request(request: Request, call_next):
    start = perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        log_event(
            "request", method=request.method, path=request.url.path,
            status=status, ms=round((perf_counter() - start) * 1000, 1),
        )


@app.exception_handler(RedisError)
async def handle_redis_error(request: Request, exc: RedisError):
    log_event("redis_unavailable", path=request.url.path)
    return JSONResponse(status_code=503, content={"detail": "Redis unavailable"})


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ready")
def ready():
    if not redis_healthy():
        raise HTTPException(status_code=503, detail="Redis unavailable")
    return {"ready": True}


@app.post("/ask")
def ask(body: AskRequest, key: str = Depends(verify_api_key)):
    check_rate_limit(key)
    check_budget()
    answer = llm_ask(body.question)
    # The mock LLM does not report usage. Estimate tokens from whitespace-separated words.
    record_cost(max(1, len(body.question.split())), max(1, len(answer.split())))
    return {"question": body.question, "answer": answer}
