import logging
import uuid
from datetime import UTC, datetime, timedelta

import redis.asyncio as aioredis
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.base import utc_now, uuid7
from app.db.models.alert import BudgetAlert
from app.db.models.project import ProjectConfig

logger = logging.getLogger(__name__)

# In-memory budget counters fallback for tests
_in_memory_budgets: dict[str, int] = {}


def reset_budget_counters() -> None:
    """Reset in-memory budget counters for test isolation."""
    _in_memory_budgets.clear()


def get_daily_period(now: datetime | None = None) -> tuple[datetime, int, str]:
    """Returns (period_start_utc, seconds_until_tomorrow, date_str YYYY-MM-DD)."""
    current = now or utc_now()
    start = datetime(current.year, current.month, current.day, tzinfo=UTC)
    tomorrow = start + timedelta(days=1)
    retry_after = max(1, int((tomorrow - current).total_seconds()))
    return start, retry_after, current.strftime("%Y-%m-%d")


def get_monthly_period(now: datetime | None = None) -> tuple[datetime, int, str]:
    """Returns (period_start_utc, seconds_until_next_month, month_str YYYY-MM)."""
    current = now or utc_now()
    start = datetime(current.year, current.month, 1, tzinfo=UTC)
    # 28 days + 4 days always reaches next month
    next_month = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
    retry_after = max(1, int((next_month - current).total_seconds()))
    return start, retry_after, current.strftime("%Y-%m")


async def get_spend_counters(project_id: uuid.UUID) -> tuple[int, int]:
    """Get current (daily_spend, monthly_spend) in micro-USD."""
    _, _, day_str = get_daily_period()
    _, _, month_str = get_monthly_period()

    daily_key = f"budget:{project_id}:daily:{day_str}"
    monthly_key = f"budget:{project_id}:monthly:{month_str}"

    settings = get_settings()
    if settings.ENV != "test":
        try:
            r = aioredis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=0.1,
                socket_timeout=0.1,
            )
            daily_val = await r.get(daily_key)
            monthly_val = await r.get(monthly_key)
            await r.close()
            return int(daily_val or 0), int(monthly_val or 0)
        except Exception:
            pass

    return _in_memory_budgets.get(daily_key, 0), _in_memory_budgets.get(monthly_key, 0)


async def check_budget_block(
    project_id: uuid.UUID,
    config: ProjectConfig | None,
) -> tuple[bool, int, str]:
    """Check if requests should be blocked due to daily or monthly budget limits.

    Returns (is_blocked, retry_after_seconds, budget_period_name).
    """
    if not config or not config.block_at_limit:
        return False, 0, ""

    daily_spend, monthly_spend = await get_spend_counters(project_id)

    # Check daily budget limit
    if config.daily_budget_micro_usd is not None and daily_spend >= config.daily_budget_micro_usd:
        _, retry_after, _ = get_daily_period()
        return True, retry_after, "daily"

    # Check monthly budget limit
    if (
        config.monthly_budget_micro_usd is not None
        and monthly_spend >= config.monthly_budget_micro_usd
    ):
        _, retry_after, _ = get_monthly_period()
        return True, retry_after, "monthly"

    return False, 0, ""


async def record_spend_and_check_alerts(
    project_id: uuid.UUID,
    spend_micro_usd: int,
    config: ProjectConfig | None,
    db: AsyncSession,
) -> list[BudgetAlert]:
    """Record spend into budget counters and create alerts for crossed thresholds.

    Guarantees that each threshold fires exactly once per period.
    """
    if spend_micro_usd <= 0 or not config:
        return []

    now = utc_now()
    day_start, _, day_str = get_daily_period(now)
    month_start, _, month_str = get_monthly_period(now)

    daily_key = f"budget:{project_id}:daily:{day_str}"
    monthly_key = f"budget:{project_id}:monthly:{month_str}"

    settings = get_settings()
    new_daily_spend = spend_micro_usd
    new_monthly_spend = spend_micro_usd

    if settings.ENV != "test":
        try:
            r = aioredis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=0.1,
                socket_timeout=0.1,
            )
            new_daily_spend = await r.incrby(daily_key, spend_micro_usd)
            new_monthly_spend = await r.incrby(monthly_key, spend_micro_usd)
            # Expire keys after 48h and 62 days respectively
            await r.expire(daily_key, 172800)
            await r.expire(monthly_key, 5356800)
            await r.close()
        except Exception:
            _in_memory_budgets[daily_key] = _in_memory_budgets.get(daily_key, 0) + spend_micro_usd
            _in_memory_budgets[monthly_key] = (
                _in_memory_budgets.get(monthly_key, 0) + spend_micro_usd
            )
            new_daily_spend = _in_memory_budgets[daily_key]
            new_monthly_spend = _in_memory_budgets[monthly_key]
    else:
        _in_memory_budgets[daily_key] = _in_memory_budgets.get(daily_key, 0) + spend_micro_usd
        _in_memory_budgets[monthly_key] = _in_memory_budgets.get(monthly_key, 0) + spend_micro_usd
        new_daily_spend = _in_memory_budgets[daily_key]
        new_monthly_spend = _in_memory_budgets[monthly_key]

    old_daily_spend = new_daily_spend - spend_micro_usd
    old_monthly_spend = new_monthly_spend - spend_micro_usd

    alerts_created: list[BudgetAlert] = []
    warn_thresholds = sorted(config.warn_thresholds or [50, 80, 100])

    # Check daily thresholds
    if config.daily_budget_micro_usd:
        daily_limit = config.daily_budget_micro_usd
        for threshold in warn_thresholds:
            threshold_amount = (daily_limit * threshold) // 100
            if old_daily_spend < threshold_amount <= new_daily_spend:
                alert = BudgetAlert(
                    id=uuid7(),
                    project_id=project_id,
                    period="daily",
                    period_start=day_start,
                    threshold_percent=threshold,
                    spend_micro_usd=new_daily_spend,
                    budget_micro_usd=daily_limit,
                    created_at=now,
                    webhook_status="pending" if config.webhook_url else "skipped",
                )
                try:
                    db.add(alert)
                    await db.flush()
                    alerts_created.append(alert)
                except IntegrityError:
                    # Already fired for this period + threshold
                    await db.rollback()

    # Check monthly thresholds
    if config.monthly_budget_micro_usd:
        monthly_limit = config.monthly_budget_micro_usd
        for threshold in warn_thresholds:
            threshold_amount = (monthly_limit * threshold) // 100
            if old_monthly_spend < threshold_amount <= new_monthly_spend:
                alert = BudgetAlert(
                    id=uuid7(),
                    project_id=project_id,
                    period="monthly",
                    period_start=month_start,
                    threshold_percent=threshold,
                    spend_micro_usd=new_monthly_spend,
                    budget_micro_usd=monthly_limit,
                    created_at=now,
                    webhook_status="pending" if config.webhook_url else "skipped",
                )
                try:
                    db.add(alert)
                    await db.flush()
                    alerts_created.append(alert)
                except IntegrityError:
                    await db.rollback()

    return alerts_created
