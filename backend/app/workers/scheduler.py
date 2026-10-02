import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore[import-untyped]
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import get_settings
from app.core.budget import get_daily_period, get_monthly_period
from app.db.base import utc_now
from app.db.models.request import RequestLog
from app.db.session import get_sessionmaker

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


async def reconcile_budget_counters(
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> None:
    """Reconcile Redis budget counters against database aggregates to prevent drift."""
    settings = get_settings()
    now = utc_now()
    day_start, _, day_str = get_daily_period(now)
    month_start, _, month_str = get_monthly_period(now)

    maker = session_factory or get_sessionmaker()

    try:
        async with maker() as session:
            # Aggregate daily spend per project
            daily_stmt = (
                select(
                    RequestLog.project_id,
                    func.coalesce(func.sum(RequestLog.cost_micro_usd), 0).label("spend"),
                )
                .where(
                    RequestLog.created_at >= day_start,
                    RequestLog.cost_micro_usd.is_not(None),
                )
                .group_by(RequestLog.project_id)
            )
            daily_res = await session.execute(daily_stmt)
            daily_spends = {row[0]: int(row[1]) for row in daily_res.all()}

            # Aggregate monthly spend per project
            monthly_stmt = (
                select(
                    RequestLog.project_id,
                    func.coalesce(func.sum(RequestLog.cost_micro_usd), 0).label("spend"),
                )
                .where(
                    RequestLog.created_at >= month_start,
                    RequestLog.cost_micro_usd.is_not(None),
                )
                .group_by(RequestLog.project_id)
            )
            monthly_res = await session.execute(monthly_stmt)
            monthly_spends = {row[0]: int(row[1]) for row in monthly_res.all()}

        if settings.ENV != "test":
            import redis.asyncio as aioredis

            try:
                r = aioredis.from_url(
                    settings.REDIS_URL,
                    decode_responses=True,
                    socket_connect_timeout=0.2,
                    socket_timeout=0.2,
                )
                for pid, spend in daily_spends.items():
                    key = f"budget:{pid}:daily:{day_str}"
                    await r.set(key, spend, ex=172800)

                for pid, spend in monthly_spends.items():
                    key = f"budget:{pid}:monthly:{month_str}"
                    await r.set(key, spend, ex=5356800)

                await r.close()
            except Exception as e:
                logger.warning("Failed to reconcile budget counters in Redis: %s", e)

        logger.info("Budget counters successfully reconciled for %d projects.", len(daily_spends))
    except Exception as e:
        logger.exception("Budget reconciliation error: %s", e)


def start_scheduler() -> AsyncIOScheduler:
    """Start APScheduler with background maintenance jobs."""
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        return _scheduler

    _scheduler = AsyncIOScheduler()
    # Reconcile budget counters every 15 minutes
    _scheduler.add_job(
        reconcile_budget_counters,
        "interval",
        minutes=15,
        id="budget_reconcile",
        replace_existing=True,
    )
    _scheduler.start()
    return _scheduler


def stop_scheduler() -> None:
    """Shut down scheduler gracefully."""
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
        _scheduler = None
