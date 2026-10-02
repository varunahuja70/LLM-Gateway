from datetime import timedelta
from urllib.parse import urlparse

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.security import constant_time_compare, hash_token
from app.db.base import ensure_utc, utc_now
from app.db.models.owner import OwnerUser, Session
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
