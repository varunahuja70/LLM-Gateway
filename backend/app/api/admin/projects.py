import re
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.core.crypto import encrypt
from app.core.ssrf import SSRFError, validate_url
from app.db.base import ensure_utc, utc_now
from app.db.models.owner import OwnerUser, Session
from app.db.models.project import Project, ProjectConfig
from app.db.session import get_db_session
from app.deps import require_csrf, require_owner
from app.schemas.auth import MessageResponse
from app.schemas.project import (
    FallbackTarget,
    ProjectConfigResponse,
    ProjectConfigUpdate,
    ProjectCreate,
    ProjectResponse,
    ProjectUpdate,
)
from app.services.audit import log_audit_event

router = APIRouter(prefix="/admin/projects", tags=["projects"])


def _generate_slug(name: str) -> str:
    slug = re.sub(r"[^a-z0-9\-]+", "-", name.lower()).strip("-")
    return slug or "project"


def _format_project_response(project: Project, active_keys_count: int = 0) -> ProjectResponse:
    return ProjectResponse(
        id=project.id,
        name=project.name,
        slug=project.slug,
        description=project.description,
        created_at=project.created_at,
        archived_at=project.archived_at,
        active_keys_count=active_keys_count,
    )


def _format_config_response(config: ProjectConfig) -> ProjectConfigResponse:
    fallback_chain = [
        FallbackTarget(provider=item["provider"], model=item["model"])
        for item in (config.fallback_chain or [])
        if isinstance(item, dict) and "provider" in item and "model" in item
    ]
    return ProjectConfigResponse(
        project_id=config.project_id,
        daily_budget_micro_usd=config.daily_budget_micro_usd,
        monthly_budget_micro_usd=config.monthly_budget_micro_usd,
        warn_thresholds=config.warn_thresholds or [50, 80, 100],
        block_at_limit=config.block_at_limit,
        fallback_chain=fallback_chain,
        max_fallbacks=config.max_fallbacks,
        request_timeout_s=config.request_timeout_s,
        cache_enabled=config.cache_enabled,
        cache_ttl_s=config.cache_ttl_s,
        rpm_limit=config.rpm_limit,
        log_content=config.log_content,
        webhook_url=config.webhook_url,
        has_webhook_secret=config.webhook_secret_encrypted is not None,
        provider_credential_id=config.provider_credential_id or {},
    )


@router.get("", response_model=list[ProjectResponse])
async def list_projects(
    include_archived: bool = Query(default=False),
    db: AsyncSession = Depends(get_db_session),
    _owner_auth: tuple[OwnerUser, Session] = Depends(require_owner),
) -> Any:
    """List all projects with active key counts."""
    query = select(Project).options(selectinload(Project.keys))
    if not include_archived:
        query = query.where(Project.archived_at.is_(None))
    query = query.order_by(Project.created_at.desc())

    result = await db.execute(query)
    projects = result.scalars().all()
    now = utc_now()

    response_list: list[ProjectResponse] = []
    for p in projects:
        active_keys = sum(
            1
            for k in p.keys
            if k.revoked_at is None and (k.expires_at is None or ensure_utc(k.expires_at) > now)
        )
        response_list.append(_format_project_response(p, active_keys))

    return response_list


@router.post("", response_model=ProjectResponse, dependencies=[Depends(require_csrf)])
async def create_project(
    req: ProjectCreate,
    db: AsyncSession = Depends(get_db_session),
    owner_auth: tuple[OwnerUser, Session] = Depends(require_owner),
) -> Any:
    """Create a new project and initialize its default configuration."""
    owner, _ = owner_auth
    slug = req.slug or _generate_slug(req.name)

    # Check uniqueness of name and slug
    existing = await db.execute(
        select(Project).where((Project.name == req.name) | (Project.slug == slug))
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A project with this name or slug already exists.",
        )

    project = Project(
        name=req.name,
        slug=slug,
        description=req.description,
    )
    db.add(project)
    await db.flush()

    # Create default project config
    config = ProjectConfig(
        project_id=project.id,
        daily_budget_micro_usd=None,
        monthly_budget_micro_usd=None,
        warn_thresholds=[50, 80, 100],
        block_at_limit=False,
        fallback_chain=[],
        max_fallbacks=2,
        request_timeout_s=60,
        cache_enabled=False,
        cache_ttl_s=3600,
        rpm_limit=60,
        log_content=False,
        webhook_url=None,
        webhook_secret_encrypted=None,
        provider_credential_id={},
    )
    db.add(config)
    await db.flush()

    await log_audit_event(
        db,
        action="project_created",
        actor_type="owner",
        actor_id=owner.id,
        details={"project_id": str(project.id), "name": project.name, "slug": project.slug},
    )

    return _format_project_response(project, active_keys_count=0)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    _owner_auth: tuple[OwnerUser, Session] = Depends(require_owner),
) -> Any:
    """Get project details by ID."""
    stmt = select(Project).options(selectinload(Project.keys)).where(Project.id == project_id)
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    now = utc_now()
    active_keys = sum(
        1
        for k in project.keys
        if k.revoked_at is None and (k.expires_at is None or ensure_utc(k.expires_at) > now)
    )
    return _format_project_response(project, active_keys)


@router.patch("/{project_id}", response_model=ProjectResponse, dependencies=[Depends(require_csrf)])
async def update_project(
    project_id: uuid.UUID,
    req: ProjectUpdate,
    db: AsyncSession = Depends(get_db_session),
    owner_auth: tuple[OwnerUser, Session] = Depends(require_owner),
) -> Any:
    """Update project name or description."""
    owner, _ = owner_auth
    stmt = select(Project).options(selectinload(Project.keys)).where(Project.id == project_id)
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    if req.name is not None and req.name != project.name:
        existing = await db.execute(
            select(Project).where(Project.name == req.name, Project.id != project_id)
        )
        if existing.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A project with this name already exists.",
            )
        project.name = req.name

    if req.description is not None:
        project.description = req.description

    await log_audit_event(
        db,
        action="project_updated",
        actor_type="owner",
        actor_id=owner.id,
        details={"project_id": str(project.id)},
    )

    now = utc_now()
    active_keys = sum(
        1
        for k in project.keys
        if k.revoked_at is None and (k.expires_at is None or ensure_utc(k.expires_at) > now)
    )
    return _format_project_response(project, active_keys)


@router.delete(
    "/{project_id}", response_model=MessageResponse, dependencies=[Depends(require_csrf)]
)
async def archive_project(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    owner_auth: tuple[OwnerUser, Session] = Depends(require_owner),
) -> Any:
    """Archive a project (soft delete)."""
    owner, _ = owner_auth
    stmt = select(Project).where(Project.id == project_id)
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    project.archived_at = utc_now()
    await log_audit_event(
        db,
        action="project_archived",
        actor_type="owner",
        actor_id=owner.id,
        details={"project_id": str(project.id)},
    )
    return MessageResponse(message="Project archived successfully.")


@router.get("/{project_id}/config", response_model=ProjectConfigResponse)
async def get_project_config(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    _owner_auth: tuple[OwnerUser, Session] = Depends(require_owner),
) -> Any:
    """Get project configuration."""
    stmt = select(ProjectConfig).where(ProjectConfig.project_id == project_id)
    result = await db.execute(stmt)
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project config not found."
        )
    return _format_config_response(config)


@router.put(
    "/{project_id}/config",
    response_model=ProjectConfigResponse,
    dependencies=[Depends(require_csrf)],
)
async def update_project_config(
    project_id: uuid.UUID,
    req: ProjectConfigUpdate,
    db: AsyncSession = Depends(get_db_session),
    owner_auth: tuple[OwnerUser, Session] = Depends(require_owner),
) -> Any:
    """Update project configuration with security validation."""
    owner, _ = owner_auth
    settings = get_settings()

    stmt = select(ProjectConfig).where(ProjectConfig.project_id == project_id)
    result = await db.execute(stmt)
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project config not found."
        )

    # Validate webhook URL against SSRF
    if req.webhook_url is not None:
        if req.webhook_url.strip() == "":
            config.webhook_url = None
        else:
            try:
                validated_url = validate_url(
                    req.webhook_url, allow_private=settings.ALLOW_PRIVATE_PROVIDER_URLS
                )
                config.webhook_url = validated_url
            except SSRFError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid webhook URL: {e}",
                ) from e

    # Encrypt webhook secret if provided
    if req.webhook_secret is not None:
        if req.webhook_secret.strip() == "":
            config.webhook_secret_encrypted = None
        else:
            encrypted_secret = encrypt(req.webhook_secret, associated_data=str(project_id))
            config.webhook_secret_encrypted = encrypted_secret

    if req.daily_budget_micro_usd is not None or "daily_budget_micro_usd" in req.model_fields_set:
        config.daily_budget_micro_usd = req.daily_budget_micro_usd

    if (
        req.monthly_budget_micro_usd is not None
        or "monthly_budget_micro_usd" in req.model_fields_set
    ):
        config.monthly_budget_micro_usd = req.monthly_budget_micro_usd

    if req.warn_thresholds is not None:
        config.warn_thresholds = req.warn_thresholds

    if req.block_at_limit is not None:
        config.block_at_limit = req.block_at_limit

    if req.fallback_chain is not None:
        config.fallback_chain = [f.model_dump() for f in req.fallback_chain]

    if req.max_fallbacks is not None:
        config.max_fallbacks = req.max_fallbacks

    if req.request_timeout_s is not None:
        config.request_timeout_s = req.request_timeout_s

    if req.cache_enabled is not None:
        config.cache_enabled = req.cache_enabled

    if req.cache_ttl_s is not None:
        config.cache_ttl_s = req.cache_ttl_s

    if req.rpm_limit is not None:
        config.rpm_limit = req.rpm_limit

    if req.log_content is not None:
        config.log_content = req.log_content

    if req.provider_credential_id is not None:
        config.provider_credential_id = req.provider_credential_id

    await log_audit_event(
        db,
        action="project_config_updated",
        actor_type="owner",
        actor_id=owner.id,
        details={"project_id": str(project_id)},
    )

    return _format_config_response(config)
