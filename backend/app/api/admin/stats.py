import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models.owner import OwnerUser, Session
from app.db.session import get_db_session
from app.deps import require_owner
from app.schemas.stats import (
    ModelsQualityResponse,
    OverviewStats,
    ProjectStatsResponse,
    TimeseriesResponse,
)
from app.services.stats import (
    get_models_stats,
    get_overview_stats,
    get_project_stats,
    get_timeseries_stats,
)

router = APIRouter(prefix="/admin/stats", tags=["stats"])


@router.get("/overview", response_model=OverviewStats)
async def stats_overview(
    project_id: uuid.UUID | None = None,
    from_date: datetime | None = Query(None, alias="from"),
    to_date: datetime | None = Query(None, alias="to"),
    db: AsyncSession = Depends(get_db_session),
    _owner_auth: tuple[OwnerUser, Session] = Depends(require_owner),
) -> Any:
    """Aggregate overview statistics (spend, requests, tokens, rates)."""
    return await get_overview_stats(
        session=db,
        project_id=project_id,
        from_time=from_date,
        to_time=to_date,
    )


@router.get("/timeseries", response_model=TimeseriesResponse)
async def stats_timeseries(
    project_id: uuid.UUID | None = None,
    from_date: datetime | None = Query(None, alias="from"),
    to_date: datetime | None = Query(None, alias="to"),
    bucket: str = Query("hour", pattern="^(hour|day)$"),
    db: AsyncSession = Depends(get_db_session),
    _owner_auth: tuple[OwnerUser, Session] = Depends(require_owner),
) -> Any:
    """Bucketed time series of requests, errors, tokens, spend, and latency percentiles."""
    buckets = await get_timeseries_stats(
        session=db,
        project_id=project_id,
        from_time=from_date,
        to_time=to_date,
        bucket=bucket,
    )
    return TimeseriesResponse(bucket=bucket, data=buckets)


@router.get("/models", response_model=ModelsQualityResponse)
async def stats_models(
    project_id: uuid.UUID | None = None,
    from_date: datetime | None = Query(None, alias="from"),
    to_date: datetime | None = Query(None, alias="to"),
    db: AsyncSession = Depends(get_db_session),
    _owner_auth: tuple[OwnerUser, Session] = Depends(require_owner),
) -> Any:
    """Quality signals per model (error rate, fallback rate, latency percentiles, TTFT, feedback)."""
    models = await get_models_stats(
        session=db,
        project_id=project_id,
        from_time=from_date,
        to_time=to_date,
    )
    return ModelsQualityResponse(data=models)


@router.get("/projects/{project_id}", response_model=ProjectStatsResponse)
async def stats_for_project(
    project_id: uuid.UUID,
    from_date: datetime | None = Query(None, alias="from"),
    to_date: datetime | None = Query(None, alias="to"),
    db: AsyncSession = Depends(get_db_session),
    _owner_auth: tuple[OwnerUser, Session] = Depends(require_owner),
) -> Any:
    """Detailed statistics and current budget status for a specific project."""
    settings = get_settings()
    redis_client = None
    if settings.ENV != "test":
        try:
            import redis.asyncio as aioredis

            redis_client = aioredis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=0.2,
                socket_timeout=0.2,
            )
        except Exception:
            redis_client = None

    try:
        stats = await get_project_stats(
            session=db,
            project_id=project_id,
            redis_client=redis_client,
            from_time=from_date,
            to_time=to_date,
        )
        return stats
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    finally:
        if redis_client is not None:
            await redis_client.close()
