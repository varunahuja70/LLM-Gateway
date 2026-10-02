import json
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urlparse

import redis.asyncio as aioredis
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.core.errors import GatewayAuthException
from app.core.security import (
    constant_time_compare,
    hash_key,
    hash_token,
    is_valid_gateway_key_format,
)
from app.db.base import ensure_utc, utc_now
from app.db.models.owner import OwnerUser, Session
from app.db.models.project import GatewayKey, Project
from app.db.session import get_db_session

# Timeouts as specified in 03-security.md
IDLE_TIMEOUT = timedelta(hours=8)
ABSOLUTE_TIMEOUT = timedelta(days=7)


def get_session_token(request: Request) -> str | None:
    """Extract session token from cookie (__Host-session or fallback session in dev)."""
    return request.cookies.get("__Host-session") or request.cookies.get("session")


async def require_owner(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
) -> tuple[OwnerUser, Session]:
    """Authenticate owner via session cookie.

    Rejects requests using gateway keys (Security Test 10).
    Enforces idle timeout (8h) and absolute timeout (7d).
    """
    # Security Rule: Gateway keys NEVER work on /admin/* endpoints
    auth_header = request.headers.get("Authorization", "")
    if auth_header.strip().startswith("Bearer lgw_"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Gateway keys are not permitted on admin endpoints.",
        )

    token = get_session_token(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. No valid session cookie found.",
        )

    token_hash = hash_token(token)
    stmt = select(Session).where(Session.id == token_hash)
    result = await db.execute(stmt)
    user_session = result.scalar_one_or_none()

    if not user_session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session not found or expired.",
        )

    now = utc_now()

    # Enforce absolute timeout (7 days)
    if now - ensure_utc(user_session.created_at) > ABSOLUTE_TIMEOUT:
        await db.delete(user_session)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has reached absolute timeout (7 days). Please log in again.",
        )

    # Enforce idle timeout (8 hours)
    if now - ensure_utc(user_session.last_seen_at) > IDLE_TIMEOUT:
        await db.delete(user_session)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has timed out due to inactivity (8 hours). Please log in again.",
        )

    # Enforce expires_at timestamp
    if now > ensure_utc(user_session.expires_at):
        await db.delete(user_session)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired.",
        )

    # Touch last_seen_at
    user_session.last_seen_at = now
    return user_session.owner, user_session


async def require_csrf(
    request: Request,
    auth: tuple[OwnerUser, Session] = Depends(require_owner),
) -> None:
    """Enforce CSRF token and Origin header check on state-changing requests."""
    settings = get_settings()
    _owner, user_session = auth

    # Origin verification
    origin = request.headers.get("Origin")
    if origin:
        parsed_origin = urlparse(origin)
        parsed_public = urlparse(settings.PUBLIC_URL)

        # In dev, also permit localhost / 127.0.0.1
        is_dev = settings.ENV in ("development", "test")
        allowed_hosts = {parsed_public.hostname, "localhost", "127.0.0.1", "testserver"}

        if parsed_origin.hostname not in allowed_hosts and not is_dev:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Origin '{origin}' does not match configured PUBLIC_URL.",
            )

    # X-CSRF-Token verification
    csrf_token = request.headers.get("X-CSRF-Token")
    if not csrf_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing required X-CSRF-Token header.",
        )

    token_hash = hash_token(csrf_token)
    if not constant_time_compare(token_hash, user_session.csrf_token_hash):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid CSRF token.",
        )


# In-memory gateway key auth cache (TTL 60s fallback when Redis is absent)
_gateway_key_in_memory_cache: dict[str, tuple[dict[str, Any], datetime]] = {}


def clear_gateway_key_memory_cache() -> None:
    """Clear in-memory key cache for tests."""
    _gateway_key_in_memory_cache.clear()


async def invalidate_gateway_key_cache(key_hash: str) -> None:
    """Invalidate cached key lookup immediately on revocation or rotation."""
    _gateway_key_in_memory_cache.pop(key_hash, None)
    settings = get_settings()
    if settings.ENV != "test":
        try:
            r = aioredis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=0.1,
                socket_timeout=0.1,
            )
            await r.delete(f"auth:key:{key_hash}")
            await r.close()
        except Exception:
            pass


async def require_gateway_key(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
) -> tuple[Project, GatewayKey]:
    """Authenticate incoming gateway request via Authorization: Bearer lgw_...

    Validates key format, checks Redis 60s cache, loads key and project,
    enforces active project, unrevoked key, and unexpired key.
    Updates last_used_at at most once per minute.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header or not auth_header.strip().startswith("Bearer "):
        raise GatewayAuthException(
            "You didn't provide an API key. You need to provide your API key in an "
            "Authorization header using Bearer auth."
        )

    raw_key = auth_header[7:].strip()
    if not is_valid_gateway_key_format(raw_key):
        raise GatewayAuthException("Incorrect API key provided.")

    key_hash = hash_key(raw_key)
    now = utc_now()

    # 1. Check Redis cache
    settings = get_settings()
    cached_data: dict[str, Any] | None = None
    if settings.ENV != "test":
        try:
            r = aioredis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=0.1,
                socket_timeout=0.1,
            )
            cached_str = await r.get(f"auth:key:{key_hash}")
            await r.close()
            if cached_str:
                cached_data = json.loads(cached_str)
        except Exception:
            pass

    if cached_data is None and key_hash in _gateway_key_in_memory_cache:
        # Fall back to in-memory cache
        entry, expire_time = _gateway_key_in_memory_cache[key_hash]
        if now < expire_time:
            cached_data = entry
        else:
            _gateway_key_in_memory_cache.pop(key_hash, None)

    if cached_data and cached_data.get("revoked", False):
        raise GatewayAuthException("API key has been revoked.")

    # 2. Look up key and project in DB
    stmt = (
        select(GatewayKey)
        .options(selectinload(GatewayKey.project).selectinload(Project.config))
        .where(GatewayKey.key_hash == key_hash)
    )
    result = await db.execute(stmt)
    key_record = result.scalar_one_or_none()

    if not key_record:
        raise GatewayAuthException("Incorrect API key provided.")

    if key_record.revoked_at is not None:
        raise GatewayAuthException("API key has been revoked.")

    if key_record.expires_at is not None and ensure_utc(key_record.expires_at) < now:
        raise GatewayAuthException("API key has expired.")

    project = key_record.project
    if not project or project.archived_at is not None:
        raise GatewayAuthException("Project is archived or not found.")

    # 3. Cache valid key lookup in Redis (60s TTL)
    cache_payload = {
        "key_id": str(key_record.id),
        "project_id": str(project.id),
        "project_slug": project.slug,
        "revoked": False,
    }
    if settings.ENV != "test":
        try:
            r = aioredis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=0.1,
                socket_timeout=0.1,
            )
            await r.set(f"auth:key:{key_hash}", json.dumps(cache_payload), ex=60)
            await r.close()
        except Exception:
            _gateway_key_in_memory_cache[key_hash] = (cache_payload, now + timedelta(seconds=60))
    else:
        _gateway_key_in_memory_cache[key_hash] = (cache_payload, now + timedelta(seconds=60))

    # 4. Update last_used_at at most once per minute
    if (
        key_record.last_used_at is None
        or (now - ensure_utc(key_record.last_used_at)).total_seconds() > 60
    ):
        key_record.last_used_at = now

    return project, key_record
