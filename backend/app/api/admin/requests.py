import base64
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.base import ensure_utc
from app.db.models.owner import OwnerUser, Session
from app.db.models.request import RequestLog
from app.db.session import get_db_session
from app.deps import require_owner
from app.schemas.requests import (
    RequestContentDetail,
    RequestDetailResponse,
    RequestListResponse,
    RequestLogSummary,
)

router = APIRouter(prefix="/admin/requests", tags=["requests"])


def _encode_cursor(created_at: datetime, req_id: uuid.UUID) -> str:
    iso = created_at.isoformat()
    raw = f"{iso}|{req_id}".encode()
    return base64.urlsafe_b64encode(raw).decode("ascii")


def _decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("ascii")).decode("utf-8")
        iso, req_id_str = raw.split("|", 1)
        dt = ensure_utc(datetime.fromisoformat(iso))
        req_id = uuid.UUID(req_id_str)
        return dt, req_id
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid pagination cursor format.",
        ) from e


@router.get("", response_model=RequestListResponse)
async def list_requests(
    project_id: uuid.UUID | None = None,
    model: str | None = None,
    provider: str | None = None,
    status_filter: str | None = Query(None, alias="status"),
    from_date: datetime | None = Query(None, alias="from"),
    to_date: datetime | None = Query(None, alias="to"),
    cache_hit: bool | None = None,
    fallback_used: bool | None = None,
    user_tag: str | None = None,
    search: str | None = None,
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db_session),
    _owner_auth: tuple[OwnerUser, Session] = Depends(require_owner),
) -> Any:
    """List requests with filters and keyset cursor pagination."""
    stmt = select(RequestLog)

    if project_id is not None:
        stmt = stmt.where(RequestLog.project_id == project_id)
    if model is not None:
        stmt = stmt.where(or_(RequestLog.model_used == model, RequestLog.model_requested == model))
    if provider is not None:
        stmt = stmt.where(RequestLog.provider == provider)
    if status_filter is not None:
        stmt = stmt.where(RequestLog.status == status_filter)
    if from_date is not None:
        stmt = stmt.where(RequestLog.created_at >= ensure_utc(from_date))
    if to_date is not None:
        stmt = stmt.where(RequestLog.created_at <= ensure_utc(to_date))
    if cache_hit is not None:
        stmt = stmt.where(RequestLog.cache_hit == cache_hit)
    if fallback_used is not None:
        stmt = stmt.where(RequestLog.fallback_used == fallback_used)
    if user_tag is not None:
        stmt = stmt.where(RequestLog.user_tag == user_tag)

    if search is not None and search.strip():
        s = search.strip()
        search_clauses = []
        try:
            search_uuid = uuid.UUID(s)
            search_clauses.append(RequestLog.id == search_uuid)
        except ValueError:
            pass
        search_clauses.append(RequestLog.user_tag.ilike(f"%{s}%"))
        search_clauses.append(RequestLog.model_used.ilike(f"%{s}%"))
        stmt = stmt.where(or_(*search_clauses))

    if cursor is not None:
        cursor_dt, cursor_id = _decode_cursor(cursor)
        stmt = stmt.where(
            or_(
                RequestLog.created_at < cursor_dt,
                and_(RequestLog.created_at == cursor_dt, RequestLog.id < cursor_id),
            )
        )

    stmt = stmt.order_by(desc(RequestLog.created_at), desc(RequestLog.id)).limit(limit + 1)
    res = await db.execute(stmt)
    rows = list(res.scalars().all())

    has_more = len(rows) > limit
    items = rows[:limit]
    next_cursor = (
        _encode_cursor(items[-1].created_at, items[-1].id) if (has_more and items) else None
    )

    return RequestListResponse(
        items=[RequestLogSummary.model_validate(r) for r in items],
        next_cursor=next_cursor,
        has_more=has_more,
    )


@router.get("/{request_id}", response_model=RequestDetailResponse)
async def get_request_detail(
    request_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    _owner_auth: tuple[OwnerUser, Session] = Depends(require_owner),
) -> Any:
    """Retrieve full request detail including content if logged."""
    stmt = (
        select(RequestLog)
        .options(selectinload(RequestLog.content))
        .where(RequestLog.id == request_id)
    )
    res = await db.execute(stmt)
    log_entry = res.scalar_one_or_none()
    if not log_entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Request not found.",
        )

    content_detail = None
    if log_entry.content:
        content_detail = RequestContentDetail(
            request_id=log_entry.content.request_id,
            request_json=log_entry.content.request_json,
            response_json=log_entry.content.response_json,
        )

    data = RequestLogSummary.model_validate(log_entry).model_dump()
    return RequestDetailResponse(**data, content=content_detail)
