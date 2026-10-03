import json
import uuid
from typing import Any

import httpx
import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.crypto import decrypt
from app.core.ssrf import SSRFError, validate_url
from app.db.base import utc_now
from app.db.models.alert import BudgetAlert
from app.db.models.owner import OwnerUser, Session
from app.db.models.project import Project
from app.db.session import get_db_session
from app.deps import require_csrf, require_owner
from app.services.webhook import compute_webhook_signature

router = APIRouter(prefix="/admin", tags=["alerts"])
logger = structlog.get_logger(__name__)


class AlertResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    period: str
    period_start: str
    threshold_percent: int
    spend_micro_usd: int
    budget_micro_usd: int
    created_at: str
    webhook_status: str
    webhook_attempts: int
    last_error: str | None


class WebhookTestResponse(BaseModel):
    success: bool
    status_code: int | None = None
    detail: str


@router.get("/alerts", response_model=list[AlertResponse])
async def list_alerts(
    project_id: uuid.UUID | None = Query(None),
    period: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _auth: tuple[OwnerUser, Session] = Depends(require_owner),
    db: AsyncSession = Depends(get_db_session),
) -> list[AlertResponse]:
    """List budget alerts with optional filters."""
    query = select(BudgetAlert).order_by(desc(BudgetAlert.created_at)).offset(offset).limit(limit)

    if project_id is not None:
        query = query.where(BudgetAlert.project_id == project_id)
    if period is not None:
        query = query.where(BudgetAlert.period == period)
    if status_filter is not None:
        query = query.where(BudgetAlert.webhook_status == status_filter)

    res = await db.execute(query)
    alerts = res.scalars().all()

    return [
        AlertResponse(
            id=a.id,
            project_id=a.project_id,
            period=a.period,
            period_start=a.period_start.isoformat(),
            threshold_percent=a.threshold_percent,
            spend_micro_usd=a.spend_micro_usd,
            budget_micro_usd=a.budget_micro_usd,
            created_at=a.created_at.isoformat(),
            webhook_status=a.webhook_status,
            webhook_attempts=a.webhook_attempts,
            last_error=a.last_error,
        )
        for a in alerts
    ]


@router.post("/projects/{id}/webhook/test", response_model=WebhookTestResponse)
async def test_project_webhook(
    id: uuid.UUID,
    _auth: tuple[OwnerUser, Session] = Depends(require_owner),
    _csrf: None = Depends(require_csrf),
    db: AsyncSession = Depends(get_db_session),
) -> WebhookTestResponse:
    """Send a signed test ping to the project's configured webhook URL."""
    stmt = (
        select(Project)
        .options(selectinload(Project.config))
        .where(Project.id == id, Project.archived_at.is_(None))
    )
    res = await db.execute(stmt)
    project = res.scalar_one_or_none()

    if not project or not project.config or not project.config.webhook_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No webhook URL is configured for this project.",
        )

    webhook_url = project.config.webhook_url

    # SSRF verification
    try:
        validate_url(webhook_url)
    except SSRFError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Webhook URL failed SSRF validation: {e}",
        ) from e

    payload: dict[str, Any] = {
        "event": "webhook_test",
        "project_id": str(project.id),
        "timestamp": utc_now().isoformat(),
    }
    payload_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
    headers = {"Content-Type": "application/json"}

    if project.config.webhook_secret_encrypted:
        try:
            secret = decrypt(
                project.config.webhook_secret_encrypted,
                associated_data=str(project.id).encode(),
            )
            headers["X-Gateway-Signature"] = compute_webhook_signature(payload_bytes, secret)
        except Exception as exc:
            logger.warning(
                "webhook_secret_decryption_failed",
                project_id=str(project.id),
                error=str(exc),
            )

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(webhook_url, content=payload_bytes, headers=headers)
            success = 200 <= resp.status_code < 300
            return WebhookTestResponse(
                success=success,
                status_code=resp.status_code,
                detail=f"Webhook target returned HTTP {resp.status_code}",
            )
    except Exception as e:
        return WebhookTestResponse(
            success=False,
            status_code=None,
            detail=f"Webhook connection error: {e}",
        )
