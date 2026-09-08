"""
Cortex Gateway — Async Redis Client.

Provides:
- Module-level Redis client (initialised during lifespan startup)
- ``init_redis`` / ``close_redis`` lifecycle helpers
- ``check_redis_health`` — returns "connected" | "disconnected" (never raises)
- ``get_redis`` — FastAPI dependency that yields the client

No caching, rate limiting, or session features are implemented here.
This module is purely connection infrastructure for Phase 1.
"""

from typing import Optional

import redis.asyncio as aioredis
from redis.asyncio import Redis

from app.config.settings import get_settings
from app.core.logging import logger

# Module-level client — set during application startup.
_redis_client: Optional[Redis] = None


def init_redis() -> None:
    """
    Create the async Redis client.
    Must be called once during application startup.
    """
    global _redis_client

    settings = get_settings()

    _redis_client = aioredis.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5,
        health_check_interval=30,
    )

    logger.info("Redis client initialised", host=settings.redis_host)


async def close_redis() -> None:
    """Close the Redis connection pool during application shutdown."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        logger.info("Redis client closed")


async def get_redis() -> Optional[Redis]:
    """FastAPI dependency — yields the Redis client."""
    return _redis_client


async def check_redis_health() -> str:
    """
    Perform a PING against Redis.

    Returns:
        ``"connected"``  — Redis is reachable.
        ``"disconnected"`` — Redis is unreachable (never raises).
    """
    if _redis_client is None:
        return "disconnected"
    try:
        result = await _redis_client.ping()
        if result:
            return "connected"
        return "disconnected"
    except Exception as exc:
        logger.warning("Redis health check failed", error=str(exc))
        return "disconnected"
