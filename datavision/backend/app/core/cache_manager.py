"""
Redis Cache Manager — async caching layer backed by redis.asyncio.Redis.

All keys are prefixed with ``dv:`` (DataVision).  Values are automatically
serialised to / deserialised from JSON.  When Redis is unreachable every
method degrades gracefully (returns ``None`` / ``False`` as appropriate) so
that the application remains operational without a cache.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

import redis.asyncio as aioredis

logger = logging.getLogger("datavision.cache")

# ---------------------------------------------------------------------------
# Key-pattern constants
# ---------------------------------------------------------------------------
PREFIX: str = "dv"

# Key builders — kept as functions so callers never have to hard-code prefixes.
KEY_CHART = lambda chart_id: f"{PREFIX}:chart:{chart_id}"
KEY_DATASET = lambda dataset_id: f"{PREFIX}:dataset:{dataset_id}"
KEY_METADATA = lambda ds_id: f"{PREFIX}:metadata:{ds_id}"


# ---------------------------------------------------------------------------
class CacheManager:
    """Async cache manager that wraps a ``redis.asyncio.Redis`` connection.

    Typical usage::

        import redis.asyncio as aioredis

        redis = aioredis.from_url("redis://localhost:6379/0")
        cache = CacheManager(redis)

        await cache.set("dv:chart:42", {"type": "bar"}, ttl=300)
        value = await cache.get("dv:chart:42")   # {"type": "bar"}  (dict)
    """

    # ------------------------------------------------------------------
    def __init__(self, redis: aioredis.Redis) -> None:
        self._redis: aioredis.Redis = redis

    # ------------------------------------------------------------------
    # Low-level key/value operations
    # ------------------------------------------------------------------

    async def get(self, key: str) -> Optional[Any]:
        """Return the deserialised value stored at *key*, or ``None``.

        ``None`` is also returned when Redis is unreachable — the caller
        cannot distinguish a missing key from an infrastructure failure by
        design (both mean "no data available").
        """
        try:
            raw = await self._redis.get(key)
            if raw is None:
                return None
            return json.loads(raw)
        except (aioredis.ConnectionError, aioredis.TimeoutError) as exc:
            logger.warning("Redis GET failed for key %r: %s", key, exc)
            return None
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            logger.warning("Redis GET deserialization error for key %r: %s", key, exc)
            return None

    async def set(
        self, key: str, value: Any, ttl: Optional[int] = None
    ) -> bool:
        """Store *value* at *key*, optionally with a *ttl* in seconds.

        Returns ``True`` on success, ``False`` when Redis is unavailable.
        """
        try:
            payload = json.dumps(value, default=str)
            if ttl is not None and ttl > 0:
                await self._redis.setex(key, ttl, payload)
            else:
                await self._redis.set(key, payload)
            return True
        except (aioredis.ConnectionError, aioredis.TimeoutError) as exc:
            logger.warning("Redis SET failed for key %r: %s", key, exc)
            return False
        except (TypeError, ValueError) as exc:
            logger.warning("Redis SET serialization error for key %r: %s", key, exc)
            return False

    async def delete(self, key: str) -> bool:
        """Delete *key*.  Returns ``True`` if at least one key was removed,
        ``False`` otherwise (including when Redis is unreachable)."""
        try:
            deleted = await self._redis.delete(key)
            return deleted > 0
        except (aioredis.ConnectionError, aioredis.TimeoutError) as exc:
            logger.warning("Redis DELETE failed for key %r: %s", key, exc)
            return False

    async def exists(self, key: str) -> bool:
        """Return ``True`` when *key* exists in Redis, ``False`` otherwise
        (or when Redis cannot be reached)."""
        try:
            count = await self._redis.exists(key)
            return count > 0
        except (aioredis.ConnectionError, aioredis.TimeoutError) as exc:
            logger.warning("Redis EXISTS failed for key %r: %s", key, exc)
            return False

    # ------------------------------------------------------------------
    # Bulk / pattern operations
    # ------------------------------------------------------------------

    async def clear_pattern(self, pattern: str) -> int:
        """Delete every key matching *pattern* (e.g. ``"dv:chart:*"``).

        Returns the number of keys deleted, or 0 when Redis is unavailable.
        Uses SCAN under the hood so large key-spaces are handled safely.
        """
        deleted_count = 0
        try:
            cursor = 0
            while True:
                cursor, keys = await self._redis.scan(
                    cursor, match=pattern, count=100
                )
                if keys:
                    deleted_count += await self._redis.delete(*keys)
                if cursor == 0:
                    break
        except (aioredis.ConnectionError, aioredis.TimeoutError) as exc:
            logger.warning(
                "Redis SCAN/DELETE failed for pattern %r: %s", pattern, exc
            )
            return 0

        if deleted_count:
            logger.info("Cleared %d keys matching pattern %r", deleted_count, pattern)
        return deleted_count

    # ------------------------------------------------------------------
    # Domain-specific invalidation helpers
    # ------------------------------------------------------------------

    async def invalidate_chart_cache(self, chart_id: Optional[str] = None) -> int:
        """Invalidate cached chart data.

        Parameters
        ----------
        chart_id:
            When provided, only the single chart key ``dv:chart:{chart_id}`` is
            deleted.  When omitted, **all** chart-related keys (``dv:chart:*``)
            are purged.

        Returns the number of keys deleted.
        """
        if chart_id is not None:
            key = KEY_CHART(chart_id)
            deleted = await self.delete(key)
            return 1 if deleted else 0

        return await self.clear_pattern(f"{PREFIX}:chart:*")

    async def invalidate_dataset_cache(
        self, dataset_id: Optional[str] = None
    ) -> int:
        """Invalidate cached dataset data.

        Parameters
        ----------
        dataset_id:
            When provided, deletes ``dv:dataset:{dataset_id}`` **and** the
            associated metadata key ``dv:metadata:{dataset_id}``.  When
            omitted, **all** dataset & metadata keys are purged.

        Returns the number of keys deleted.
        """
        if dataset_id is not None:
            deleted = 0
            for key in (KEY_DATASET(dataset_id), KEY_METADATA(dataset_id)):
                if await self.delete(key):
                    deleted += 1
            return deleted

        deleted = 0
        deleted += await self.clear_pattern(f"{PREFIX}:dataset:*")
        deleted += await self.clear_pattern(f"{PREFIX}:metadata:*")
        return deleted
