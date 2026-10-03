import asyncio
import math
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Any, cast

import redis.asyncio as aioredis

from app.config import get_settings


# types-redis does not annotate parameters of Redis.eval. We define a typed wrapper.
async def _eval_lua_script(
    client: aioredis.Redis[str],
    script: str,
    numkeys: int,
    *args: Any,
) -> Any:
    eval_call = cast(Callable[..., Awaitable[Any]], client.eval)
    return await eval_call(script, numkeys, *args)


# Redis Lua script for atomic sliding window rate limiting
SLIDING_WINDOW_LUA = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local clear_before = now - window

redis.call('ZREMRANGEBYSCORE', key, 0, clear_before)
local current_requests = redis.call('ZCARD', key)

if current_requests < limit then
    local seq = redis.call('INCR', key .. ':seq')
    redis.call('ZADD', key, now, now .. '-' .. seq)
    redis.call('EXPIRE', key, window + 1)
    return {1, 0}
else
    local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
    local retry_after = 1
    if oldest and #oldest >= 2 then
        local oldest_time = tonumber(oldest[2])
        retry_after = math.ceil(oldest_time + window - now)
        if retry_after < 1 then retry_after = 1 end
    end
    return {0, retry_after}
end
"""

# In-memory sliding window fallback
_in_memory_windows: dict[str, list[float]] = {}
_rate_limit_lock = asyncio.Lock()


def reset_rate_limiter() -> None:
    """Reset in-memory rate limiter records for tests."""
    _in_memory_windows.clear()


async def check_rate_limit(
    project_id: uuid.UUID,
    limit_rpm: int = 60,
    window_seconds: int = 60,
) -> tuple[bool, int]:
    """Check if project has exceeded its requests-per-minute limit.

    Returns (is_allowed, retry_after_seconds).
    """
    if limit_rpm <= 0:
        return True, 0

    now = time.time()
    key = f"rate:{project_id}:rpm"
    settings = get_settings()

    if settings.ENV != "test":
        r: aioredis.Redis[str] | None = None
        try:
            r = aioredis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=0.1,
                socket_timeout=0.1,
            )
            res: Any = await _eval_lua_script(
                r, SLIDING_WINDOW_LUA, 1, key, now, window_seconds, limit_rpm
            )
            if isinstance(res, list) and len(res) >= 2:
                allowed = bool(res[0] == 1)
                retry_after = int(res[1])
                return allowed, retry_after
        except Exception:
            pass
        finally:
            if r is not None:
                await r.close()

    # In-memory sliding window with concurrency lock
    async with _rate_limit_lock:
        cutoff = now - window_seconds
        timestamps = _in_memory_windows.get(key, [])
        valid_timestamps = [t for t in timestamps if t > cutoff]

        if len(valid_timestamps) < limit_rpm:
            valid_timestamps.append(now)
            _in_memory_windows[key] = valid_timestamps
            return True, 0

        oldest_ts = valid_timestamps[0]
        retry_after = max(1, math.ceil(oldest_ts + window_seconds - now))
        _in_memory_windows[key] = valid_timestamps
        return False, retry_after
