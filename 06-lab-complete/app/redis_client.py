"""Redis connection pool shared by the endpoints within each worker."""

from redis import Redis, RedisError

from app.config import settings


r = Redis.from_url(
    settings.redis_url, decode_responses=True, socket_connect_timeout=1, socket_timeout=2,
)


def redis_healthy() -> bool:
    try:
        return bool(r.ping())
    except RedisError:
        return False
