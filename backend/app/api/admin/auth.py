import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.security import (
    generate_csrf_token,
    generate_session_token,
    hash_password,
    verify_password,
)
from app.db.base import utc_now
from app.db.models.owner import OwnerUser, Session
from app.db.session import get_db_session
from app.deps import require_csrf, require_owner
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    LoginResponse,
    MeResponse,
    MessageResponse,
    SetupRequest,
    SetupStatusResponse,
)
from app.services.audit import log_audit_event

router = APIRouter(prefix="/admin", tags=["auth"])

# In-memory fallback for rate limiting when Redis is not active
_in_memory_rate_limit: dict[str, list[datetime]] = {}


def reset_rate_limits() -> None:
    """Clear in-memory rate limit records (primarily for testing)."""
    _in_memory_rate_limit.clear()


async def _check_and_increment_rate_limit(
    key: str, max_attempts: int = 5, window_seconds: int = 900
) -> bool:
    """Check if key has exceeded max_attempts within window_seconds.

    Returns True if allowed, False if blocked.
    """
    settings = get_settings()
    if settings.ENV != "test":
        try:
            r = aioredis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=0.1,
                socket_timeout=0.1,
            )
            count = await r.incr(key)
            if count == 1:
                await r.expire(key, window_seconds)
            await r.close()
            return bool(count <= max_attempts)
        except Exception:
            pass

    # Fallback to local memory
    now = datetime.now(UTC)
    timestamps = _in_memory_rate_limit.get(key, [])
    cutoff = now - timedelta(seconds=window_seconds)
    valid_timestamps = [t for t in timestamps if t > cutoff]
    valid_timestamps.append(now)
    _in_memory_rate_limit[key] = valid_timestamps
    return len(valid_timestamps) <= max_attempts


async def _reset_rate_limit(key: str) -> None:
    settings = get_settings()
    try:
        r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        await r.delete(key)
        await r.close()
    except Exception:
        _in_memory_rate_limit.pop(key, None)


def _set_session_cookies(response: Response, session_token: str, csrf_token: str) -> None:
    settings = get_settings()
    is_prod = settings.ENV == "production"

    # In production, use __Host-session cookie which enforces Secure, Path=/, and Host-only
    cookie_name = "__Host-session" if is_prod else "session"

    response.set_cookie(
        key=cookie_name,
        value=session_token,
        httponly=True,
        secure=is_prod,
        samesite="lax",
        path="/",
        max_age=7 * 24 * 3600,  # 7 days
    )

    # Non-HttpOnly companion cookie for frontend CSRF token
    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=False,
        secure=is_prod,
        samesite="lax",
        path="/",
        max_age=7 * 24 * 3600,
    )


@router.get("/setup/status", response_model=SetupStatusResponse)
async def setup_status(db: AsyncSession = Depends(get_db_session)) -> Any:
    stmt = select(OwnerUser).limit(1)
    result = await db.execute(stmt)
    owner = result.scalar_one_or_none()
    return {"is_setup": owner is not None}


@router.post("/setup", response_model=LoginResponse)
async def setup_owner(
    req: SetupRequest,
    response: Response,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
) -> Any:
    # Security Test 5: Setup endpoint returns 404 after the first owner exists
    stmt = select(OwnerUser).limit(1)
    result = await db.execute(stmt)
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Setup is already complete.",
        )

    try:
        pw_hash = hash_password(req.password)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    owner = OwnerUser(
        email=req.email,
        password_hash=pw_hash,
    )
    db.add(owner)
    await db.flush()

    session_token, session_hash = generate_session_token()
    csrf_token, csrf_hash = generate_csrf_token()

    now = utc_now()
    user_session = Session(
        id=session_hash,
        owner_id=owner.id,
        csrf_token_hash=csrf_hash,
        created_at=now,
        last_seen_at=now,
        expires_at=now + timedelta(days=7),
        user_agent=request.headers.get("User-Agent"),
        ip=request.client.host if request.client else None,
    )
    db.add(user_session)

    await log_audit_event(
        db,
        action="owner_setup",
        actor_type="owner",
        actor_id=owner.id,
        details={"email": owner.email},
    )
    await db.commit()

    _set_session_cookies(response, session_token, csrf_token)

    return {
        "id": str(owner.id),
        "email": owner.email,
        "csrf_token": csrf_token,
    }


@router.post("/auth/login", response_model=LoginResponse)
async def login(
    req: LoginRequest,
    response: Response,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
) -> Any:
    client_ip = request.client.host if request.client else "unknown"
    ip_key = f"rate_limit:login:ip:{client_ip}"
    account_key = f"rate_limit:login:account:{req.email.lower()}"

    # Check IP and Account rate limit (5 attempts per 15 min)
    if not await _check_and_increment_rate_limit(ip_key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts from this IP. Please try again in 15 minutes.",
        )
    if not await _check_and_increment_rate_limit(account_key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                "Too many failed login attempts for this account. Please try again in 15 minutes."
            ),
        )

    stmt = select(OwnerUser).where(OwnerUser.email == req.email.lower())
    result = await db.execute(stmt)
    owner = result.scalar_one_or_none()

    # Constant-time verify password or dummy hash to prevent timing attacks
    dummy_hash = "$argon2id$v=19$m=65536,t=3,p=4$dummyhashdummyhash$dummyhashdummyhash"
    is_valid = False
    if owner:
        is_valid = verify_password(req.password, owner.password_hash)
    else:
        verify_password(req.password, dummy_hash)

    if not is_valid or not owner:
        await asyncio.sleep(0.1)  # Small artificial delay on failure
        # Same error message for unknown email and wrong password (Security Test 4)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    # Success: reset rate limit counters
    await _reset_rate_limit(ip_key)
    await _reset_rate_limit(account_key)

    # Create new session (prevents session fixation)
    session_token, session_hash = generate_session_token()
    csrf_token, csrf_hash = generate_csrf_token()

    now = utc_now()
    user_session = Session(
        id=session_hash,
        owner_id=owner.id,
        csrf_token_hash=csrf_hash,
        created_at=now,
        last_seen_at=now,
        expires_at=now + timedelta(days=7),
        user_agent=request.headers.get("User-Agent"),
        ip=client_ip,
    )
    db.add(user_session)

    await log_audit_event(
        db,
        action="login_success",
        actor_type="owner",
        actor_id=owner.id,
        details={"ip": client_ip},
    )
    await db.commit()

    _set_session_cookies(response, session_token, csrf_token)

    return {
        "id": str(owner.id),
        "email": owner.email,
        "csrf_token": csrf_token,
    }


@router.post("/auth/logout", response_model=MessageResponse)
async def logout(
    response: Response,
    auth: tuple[OwnerUser, Session] = Depends(require_owner),
    _csrf: None = Depends(require_csrf),
    db: AsyncSession = Depends(get_db_session),
) -> Any:
    owner, user_session = auth
    await db.delete(user_session)

    await log_audit_event(
        db,
        action="logout",
        actor_type="owner",
        actor_id=owner.id,
    )
    await db.commit()

    settings = get_settings()
    cookie_name = "__Host-session" if settings.ENV == "production" else "session"
    response.delete_cookie(cookie_name, path="/")
    response.delete_cookie("csrf_token", path="/")

    return {"message": "Logged out successfully."}


@router.get("/auth/me", response_model=MeResponse)
async def me(
    request: Request,
    auth: tuple[OwnerUser, Session] = Depends(require_owner),
) -> Any:
    owner, _session = auth
    csrf_token = request.cookies.get("csrf_token", "")
    return {
        "id": str(owner.id),
        "email": owner.email,
        "csrf_token": csrf_token,
    }


@router.post("/auth/change-password", response_model=MessageResponse)
async def change_password(
    req: ChangePasswordRequest,
    response: Response,
    auth: tuple[OwnerUser, Session] = Depends(require_owner),
    _csrf: None = Depends(require_csrf),
    db: AsyncSession = Depends(get_db_session),
) -> Any:
    owner, _ = auth

    if not verify_password(req.current_password, owner.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect current password.",
        )

    try:
        new_hash = hash_password(req.new_password)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    owner.password_hash = new_hash

    # Security requirement: Changing password revokes ALL active sessions
    await db.execute(delete(Session).where(Session.owner_id == owner.id))

    await log_audit_event(
        db,
        action="password_changed",
        actor_type="owner",
        actor_id=owner.id,
    )
    await db.commit()

    settings = get_settings()
    cookie_name = "__Host-session" if settings.ENV == "production" else "session"
    response.delete_cookie(cookie_name, path="/")
    response.delete_cookie("csrf_token", path="/")

    return {"message": "Password changed successfully. All sessions have been revoked."}
