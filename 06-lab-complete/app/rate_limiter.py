"""A Redis-backed sliding window shared across workers."""

from hashlib import sha256
from uuid import uuid4

from fastapi import HTTPException

from app.config import settings
from app.redis_client import r


consume = r.register_script("""
local time = redis.call('TIME')
local now = tonumber(time[1]) * 1000 + math.floor(tonumber(time[2]) / 1000)
local window = 60000
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', now - window)
if redis.call('ZCARD', KEYS[1]) >= tonumber(ARGV[1]) then
    local oldest = redis.call('ZRANGE', KEYS[1], 0, 0, 'WITHSCORES')
    if #oldest == 0 then
        return 60
    end
    return math.max(1, math.ceil((tonumber(oldest[2]) + window - now) / 1000))
end
redis.call('ZADD', KEYS[1], now, ARGV[2])
redis.call('PEXPIRE', KEYS[1], window)
return 0
""")


def check_rate_limit(key: str) -> None:
    key_digest = sha256(key.encode()).hexdigest()
    retry_after = consume(
        keys=[f"day14:rate:{key_digest}"],
        args=[settings.rate_limit_per_minute, uuid4().hex],
    )
    if retry_after:
        raise HTTPException(
            status_code=429, detail="Rate limit exceeded",
            headers={"Retry-After": str(retry_after)},
        )
