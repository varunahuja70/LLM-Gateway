import logging
import uuid
from datetime import timedelta
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.base import utc_now
from app.db.models.alert import BudgetAlert
from app.db.models.request import RequestContent, RequestLog
from app.db.models.setting import AppSetting

logger = logging.getLogger(__name__)


async def get_retention_days(session: AsyncSession) -> int:
    """Fetch configured retention days from AppSetting or fall back to DEFAULT_RETENTION_DAYS."""
    settings = get_settings()
    stmt = select(AppSetting).where(AppSetting.key == "retention_days")
    res = await session.execute(stmt)
    setting = res.scalar_one_or_none()
    if setting is not None and setting.value is not None:
        try:
            if isinstance(setting.value, dict):
                return int(setting.value.get("days", settings.DEFAULT_RETENTION_DAYS))
            return int(setting.value)
        except (ValueError, TypeError):
            pass
    return settings.DEFAULT_RETENTION_DAYS


async def enforce_retention(session: AsyncSession, retention_days: int | None = None) -> int:
    """Delete RequestLog (and cascaded RequestContent) rows older than retention_days.

    Returns the number of deleted RequestLog rows.
    """
    if retention_days is None:
        retention_days = await get_retention_days(session)

    if retention_days <= 0:
        logger.warning("Retention days is <= 0; skipping cleanup to prevent accidental wipe.")
        return 0

    cutoff = utc_now() - timedelta(days=retention_days)

    # Clean up RequestContent explicitly to ensure cleanup across SQLite and Postgres
    content_subquery = select(RequestLog.id).where(RequestLog.created_at < cutoff)
    await session.execute(
        delete(RequestContent).where(RequestContent.request_id.in_(content_subquery))
    )

    # Delete RequestLog rows
    del_stmt = delete(RequestLog).where(RequestLog.created_at < cutoff)
    del_res = await session.execute(del_stmt)
    deleted_count: int = getattr(del_res, "rowcount", 0) or 0

    await session.commit()
    logger.info(
        "Enforced retention (%d days): removed %d old request logs.", retention_days, deleted_count
    )
    return deleted_count


async def delete_project_data(
    session: AsyncSession,
    project_id: uuid.UUID,
    redis_client: Any = None,
) -> int:
    """Delete all request logs, contents, and budget alerts for a specific project.

    Also flushes Redis budget counters if a Redis client is supplied.
    Returns the number of deleted RequestLog rows.
    """
    # 1. Delete RequestContent rows
    content_subquery = select(RequestLog.id).where(RequestLog.project_id == project_id)
    await session.execute(
        delete(RequestContent).where(RequestContent.request_id.in_(content_subquery))
    )

    # 2. Delete RequestLog rows
    del_req = await session.execute(delete(RequestLog).where(RequestLog.project_id == project_id))
    deleted_count: int = getattr(del_req, "rowcount", 0) or 0

    # 3. Delete BudgetAlert rows
    await session.execute(delete(BudgetAlert).where(BudgetAlert.project_id == project_id))

    await session.commit()

    # 4. Clean Redis budget counters if available
    if redis_client is not None:
        try:
            pattern = f"budget:{project_id}:*"
            cursor = 0
            while True:
                cursor, keys = await redis_client.scan(cursor=cursor, match=pattern, count=100)
                if keys:
                    await redis_client.delete(*keys)
                if cursor == 0:
                    break
        except Exception as e:
            logger.warning("Could not clear Redis budget keys for project %s: %s", project_id, e)

    logger.info("Deleted all data for project %s (%d logs removed).", project_id, deleted_count)
    return deleted_count
