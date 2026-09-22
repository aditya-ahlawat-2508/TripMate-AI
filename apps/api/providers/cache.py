import json
import logging
import os

import redis.asyncio as redis

logger = logging.getLogger("tripmate.cache")

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

_client: redis.Redis | None = None


def get_redis() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.from_url(REDIS_URL, decode_responses=True)
    return _client


async def cache_get(key: str):
    """Never lets a Redis outage break the request — a cache miss (real or
    because Redis is down) just means the provider gets called live."""

    try:
        value = await get_redis().get(key)
    except Exception as exc:
        logger.warning("Redis get failed for %s: %s", key, exc)
        return None
    return json.loads(value) if value else None


async def cache_set(key: str, value, ttl_seconds: int) -> None:
    try:
        await get_redis().set(key, json.dumps(value, default=str), ex=ttl_seconds)
    except Exception as exc:
        logger.warning("Redis set failed for %s: %s", key, exc)
