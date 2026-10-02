import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import generate_gateway_key
from app.db.base import utc_now
from app.db.models.owner import OwnerUser, Session
from app.db.models.project import GatewayKey, Project
from app.db.session import get_db_session
from app.deps import invalidate_gateway_key_cache, require_csrf, require_owner
from app.schemas.auth import MessageResponse
from app.schemas.key import (
    GatewayKeyCreate,
    GatewayKeyCreatedResponse,
    GatewayKeyResponse,
)
from app.services.audit import log_audit_event

router = APIRouter(prefix="/admin", tags=["keys"])


@router.get("/projects/{project_id}/keys", response_model=list[GatewayKeyResponse])
async def list_project_keys(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    _owner_auth: tuple[OwnerUser, Session] = Depends(require_owner),
) -> Any:
    """List all gateway keys for a project. Full keys are never returned."""
    stmt_p = select(Project).where(Project.id == project_id)
    result_p = await db.execute(stmt_p)
    if not result_p.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    stmt = (
        select(GatewayKey)
        .where(GatewayKey.project_id == project_id)
        .order_by(GatewayKey.created_at.desc())
    )
    result = await db.execute(stmt)
    keys = result.scalars().all()
    return [GatewayKeyResponse.model_validate(k) for k in keys]


@router.post(
    "/projects/{project_id}/keys",
    response_model=GatewayKeyCreatedResponse,
    dependencies=[Depends(require_csrf)],
)
async def create_project_key(
    project_id: uuid.UUID,
    req: GatewayKeyCreate,
    db: AsyncSession = Depends(get_db_session),
    owner_auth: tuple[OwnerUser, Session] = Depends(require_owner),
) -> Any:
    """Create a new gateway key for a project.

    The raw_key is returned ONLY ONCE in this response and cannot be retrieved again.
    """
    owner, _ = owner_auth
    stmt_p = select(Project).where(Project.id == project_id)
    result_p = await db.execute(stmt_p)
    project = result_p.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    full_key, prefix, key_hash = generate_gateway_key()

    key_record = GatewayKey(
        project_id=project_id,
        name=req.name,
        prefix=prefix,
        key_hash=key_hash,
        expires_at=req.expires_at,
    )
    db.add(key_record)
    await db.flush()

    await log_audit_event(
        db,
        action="gateway_key_created",
        actor_type="owner",
        actor_id=owner.id,
        details={
            "project_id": str(project_id),
            "key_id": str(key_record.id),
            "name": key_record.name,
            "prefix": key_record.prefix,
        },
    )

    return GatewayKeyCreatedResponse(
        id=key_record.id,
        project_id=project_id,
        name=key_record.name,
        prefix=key_record.prefix,
        created_at=key_record.created_at,
        expires_at=key_record.expires_at,
        raw_key=full_key,
    )


@router.post(
    "/keys/{key_id}/revoke",
    response_model=MessageResponse,
    dependencies=[Depends(require_csrf)],
)
async def revoke_key(
    key_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    owner_auth: tuple[OwnerUser, Session] = Depends(require_owner),
) -> Any:
    """Revoke a gateway key immediately. Invalidation in Redis auth cache is instant."""
    owner, _ = owner_auth
    stmt = select(GatewayKey).where(GatewayKey.id == key_id)
    result = await db.execute(stmt)
    key_record = result.scalar_one_or_none()
    if not key_record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gateway key not found.")

    if key_record.revoked_at is None:
        key_record.revoked_at = utc_now()
        await invalidate_gateway_key_cache(key_record.key_hash)

        await log_audit_event(
            db,
            action="gateway_key_revoked",
            actor_type="owner",
            actor_id=owner.id,
            details={"key_id": str(key_record.id), "project_id": str(key_record.project_id)},
        )

    return MessageResponse(message="Gateway key revoked successfully.")


@router.post(
    "/keys/{key_id}/rotate",
    response_model=GatewayKeyCreatedResponse,
    dependencies=[Depends(require_csrf)],
)
async def rotate_key(
    key_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    owner_auth: tuple[OwnerUser, Session] = Depends(require_owner),
) -> Any:
    """Rotate a gateway key: revokes old key and issues a new key for the same project.

    The old key is immediately invalidated in the auth cache.
    The new raw_key is returned ONLY ONCE in this response.
    """
    owner, _ = owner_auth
    stmt = select(GatewayKey).where(GatewayKey.id == key_id)
    result = await db.execute(stmt)
    old_key = result.scalar_one_or_none()
    if not old_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gateway key not found.")

    # 1. Revoke old key and invalidate cache immediately
    if old_key.revoked_at is None:
        old_key.revoked_at = utc_now()
        await invalidate_gateway_key_cache(old_key.key_hash)

    # 2. Issue new key
    full_key, prefix, key_hash = generate_gateway_key()
    new_key = GatewayKey(
        project_id=old_key.project_id,
        name=old_key.name,
        prefix=prefix,
        key_hash=key_hash,
        expires_at=old_key.expires_at,
    )
    db.add(new_key)
    await db.flush()

    await log_audit_event(
        db,
        action="gateway_key_rotated",
        actor_type="owner",
        actor_id=owner.id,
        details={
            "old_key_id": str(old_key.id),
            "new_key_id": str(new_key.id),
            "project_id": str(old_key.project_id),
            "prefix": new_key.prefix,
        },
    )

    return GatewayKeyCreatedResponse(
        id=new_key.id,
        project_id=new_key.project_id,
        name=new_key.name,
        prefix=new_key.prefix,
        created_at=new_key.created_at,
        expires_at=new_key.expires_at,
        raw_key=full_key,
    )
