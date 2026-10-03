import asyncio
import logging
import random
import uuid
from datetime import timedelta
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pricing import calculate_cost, get_price_for_model
from app.core.security import hash_key
from app.db.base import utc_now
from app.db.models.alert import BudgetAlert
from app.db.models.owner import OwnerUser
from app.db.models.project import GatewayKey, Project, ProjectConfig
from app.db.models.provider import ModelPrice
from app.db.models.request import RequestContent, RequestLog
from app.db.models.setting import AppSetting
from app.db.session import get_sessionmaker
from scripts.seed_prices import seed_prices

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("seed_demo")

# Deterministic UUIDs for demo projects so repeated runs are consistent
PROJECT_1_ID = uuid.UUID("11111111-1111-4111-8111-111111111111")
PROJECT_2_ID = uuid.UUID("22222222-2222-4222-8222-222222222222")

SAMPLE_PROMPTS = [
    (
        "Summarize our Q3 customer churn report in three bullet points.",
        "Here is the summary of your Q3 churn report:\n1. Churn decreased by 1.2%.\n2. Primary reason: pricing.\n3. Retention team interventions improved renewal rate by 8%.",
    ),
    (
        "Write a SQL query to find top 5 spending users this month.",
        "```sql\nSELECT user_id, SUM(amount) AS total_spent\nFROM transactions\nWHERE date >= DATE_TRUNC('month', CURRENT_DATE)\nGROUP BY user_id\nORDER BY total_spent DESC\nLIMIT 5;\n```",
    ),
    (
        "How do I configure Redis connection pool in Python?",
        "You can use redis.asyncio ConnectionPool:\n```python\npool = ConnectionPool.from_url('redis://localhost', max_connections=20)\nr = Redis(connection_pool=pool)\n```",
    ),
    (
        "Explain the difference between optimistic and pessimistic locking.",
        "Optimistic locking assumes conflicts are rare and checks version numbers on write. Pessimistic locking locks records on read until the transaction finishes.",
    ),
]


async def seed_demo(session: AsyncSession) -> dict[str, Any]:
    """Seed demo database with 2 realistic projects and 7 days of historical logs."""
    rng = random.Random(42)

    # 1. Ensure price seed exists
    price_check = await session.execute(select(ModelPrice).limit(1))
    if price_check.scalar_one_or_none() is None:
        await seed_prices(session)

    # 2. Ensure owner exists
    owner_check = await session.execute(select(OwnerUser).limit(1))
    owner = owner_check.scalar_one_or_none()
    if owner is None:
        from argon2 import PasswordHasher

        ph = PasswordHasher()
        owner = OwnerUser(
            id=uuid.uuid4(),
            email="owner@example.com",
            password_hash=ph.hash("OwnerPassword123!"),
            created_at=utc_now(),
        )
        session.add(owner)
        await session.flush()

    # 3. Clean up existing demo data for deterministic re-runs
    await session.execute(
        delete(RequestContent).where(
            RequestContent.request_id.in_(
                select(RequestLog.id).where(RequestLog.project_id.in_([PROJECT_1_ID, PROJECT_2_ID]))
            )
        )
    )
    await session.execute(
        delete(RequestLog).where(RequestLog.project_id.in_([PROJECT_1_ID, PROJECT_2_ID]))
    )
    await session.execute(
        delete(BudgetAlert).where(BudgetAlert.project_id.in_([PROJECT_1_ID, PROJECT_2_ID]))
    )
    await session.execute(
        delete(GatewayKey).where(GatewayKey.project_id.in_([PROJECT_1_ID, PROJECT_2_ID]))
    )
    await session.execute(
        delete(ProjectConfig).where(ProjectConfig.project_id.in_([PROJECT_1_ID, PROJECT_2_ID]))
    )
    await session.execute(delete(Project).where(Project.id.in_([PROJECT_1_ID, PROJECT_2_ID])))
    await session.commit()

    # 4. Create Project 1 (Production AI Assistant)
    p1 = Project(
        id=PROJECT_1_ID,
        name="Production Assistant",
        slug="production-assistant",
        description="Public AI customer support assistant and helpdesk workflow",
        created_at=utc_now() - timedelta(days=8),
    )
    session.add(p1)

    c1 = ProjectConfig(
        project_id=p1.id,
        daily_budget_micro_usd=100_000_000,  # $100/day
        monthly_budget_micro_usd=2_500_000_000,  # $2500/month
        warn_thresholds=[50, 80, 100],
        block_at_limit=True,
        fallback_chain=[
            {"provider": "anthropic", "model": "claude-haiku-4-5"},
            {"provider": "google", "model": "gemini-2.5-flash"},
        ],
        max_fallbacks=2,
        request_timeout_s=30,
        cache_enabled=True,
        cache_ttl_s=3600,
        rpm_limit=120,
        log_content=True,
    )
    session.add(c1)

    k1_raw = "lgw_demo_prod_assist_key_778899"
    k1 = GatewayKey(
        id=uuid.uuid4(),
        project_id=p1.id,
        name="Prod Web Client",
        prefix=k1_raw[:8],
        key_hash=hash_key(k1_raw),
        created_at=utc_now() - timedelta(days=8),
    )
    session.add(k1)

    # 5. Create Project 2 (Internal Analytics & Copilot)
    p2 = Project(
        id=PROJECT_2_ID,
        name="Internal Copilot",
        slug="internal-copilot",
        description="Engineering automation, internal summarization, and query assistant",
        created_at=utc_now() - timedelta(days=8),
    )
    session.add(p2)

    c2 = ProjectConfig(
        project_id=p2.id,
        daily_budget_micro_usd=50_000_000,  # $50/day
        monthly_budget_micro_usd=1_000_000_000,  # $1000/month
        warn_thresholds=[70, 90, 100],
        block_at_limit=False,
        fallback_chain=[{"provider": "openai", "model": "gpt-5-mini"}],
        max_fallbacks=1,
        request_timeout_s=60,
        cache_enabled=False,
        cache_ttl_s=3600,
        rpm_limit=60,
        log_content=False,
    )
    session.add(c2)

    k2_raw = "lgw_demo_internal_copilot_key_334455"
    k2 = GatewayKey(
        id=uuid.uuid4(),
        project_id=p2.id,
        name="Internal CLI Key",
        prefix=k2_raw[:8],
        key_hash=hash_key(k2_raw),
        created_at=utc_now() - timedelta(days=8),
    )
    session.add(k2)
    await session.flush()

    # 6. Generate 7 days of realistic history
    now = utc_now()
    generated_logs: list[RequestLog] = []
    generated_contents: list[RequestContent] = []

    # Pre-cache price lookup for accurate cost calculation
    price_cache: dict[tuple[str, str], ModelPrice | None] = {}

    async def get_price(prov: str, mod: str) -> ModelPrice | None:
        key = (prov, mod)
        if key not in price_cache:
            price_cache[key] = await get_price_for_model(session, prov, mod)
        return price_cache[key]

    # Loop through past 7 days
    for day_offset in range(7, 0, -1):
        day_date = now - timedelta(days=day_offset)

        # Distribute calls across waking business hours
        for hour in range(8, 22):
            # Number of requests this hour
            num_p1 = rng.randint(2, 6)
            num_p2 = rng.randint(1, 3)

            # Project 1 calls
            for _ in range(num_p1):
                minute = rng.randint(0, 59)
                second = rng.randint(0, 59)
                req_time = day_date.replace(hour=hour, minute=minute, second=second, microsecond=0)

                # Pick model based on weights
                roll = rng.random()
                if roll < 0.70:
                    prov, mod = "openai", "gpt-5-mini"
                elif roll < 0.90:
                    prov, mod = "anthropic", "claude-haiku-4-5"
                else:
                    prov, mod = "google", "gemini-2.5-flash"

                # Check if cache hit (approx 15% rate)
                is_cache_hit = rng.random() < 0.15
                # Check if fallback (approx 5% rate)
                is_fallback = not is_cache_hit and (rng.random() < 0.05)
                # Check if error (approx 3% rate)
                is_error = not is_cache_hit and not is_fallback and (rng.random() < 0.03)

                inp_tokens = rng.randint(80, 500)
                out_tokens = rng.randint(30, 250)
                cached_inp = rng.randint(10, 40) if not is_cache_hit else 0

                price_row = await get_price(prov, mod)

                if is_cache_hit:
                    # Cache hit: 0 provider spend, compute saved
                    cost_usd: int | None = 0
                    saved_usd = (
                        calculate_cost(prov, mod, inp_tokens, out_tokens, 0, price=price_row) or 0
                    )
                    lat_ms = rng.randint(15, 45)
                    status_str = "ok"
                    http_code = 200
                    inp_tokens, out_tokens, cached_inp = 0, 0, 0
                elif is_error:
                    cost_usd = None
                    saved_usd = 0
                    lat_ms = rng.randint(400, 1500)
                    status_str = "error"
                    http_code = 502
                else:
                    cost_usd = calculate_cost(
                        prov, mod, inp_tokens, out_tokens, cached_inp, price=price_row
                    )
                    saved_usd = 0
                    lat_ms = rng.randint(120, 650)
                    status_str = "ok"
                    http_code = 200

                log_id = uuid.uuid4()
                log_entry = RequestLog(
                    id=log_id,
                    project_id=p1.id,
                    gateway_key_id=k1.id,
                    created_at=req_time,
                    endpoint="chat",
                    provider=prov,
                    model_requested="openai/gpt-5-mini" if is_fallback else f"{prov}/{mod}",
                    model_used=f"{prov}/{mod}",
                    status=status_str,
                    http_status=http_code,
                    error_type="upstream_unavailable" if is_error else None,
                    error_message_safe="Upstream service returned 502" if is_error else None,
                    input_tokens=inp_tokens,
                    output_tokens=out_tokens,
                    cached_input_tokens=cached_inp,
                    cost_micro_usd=cost_usd,
                    saved_micro_usd=saved_usd,
                    latency_ms=lat_ms,
                    ttft_ms=int(lat_ms * 0.4) if http_code == 200 and not is_cache_hit else None,
                    streamed=rng.random() < 0.60,
                    cache_hit=is_cache_hit,
                    fallback_used=is_fallback,
                    fallback_from="openai/gpt-5-mini" if is_fallback else None,
                    fallback_reason="503 Overloaded" if is_fallback else None,
                    finish_reason="stop" if http_code == 200 else None,
                    empty_or_truncated=False,
                    user_tag=rng.choice(["web-chat-user", "mobile-app-client", "support-tier1"]),
                    feedback_score=rng.choice([1, 1, 1, -1, None, None]),
                )
                generated_logs.append(log_entry)

                # Store request content for a few samples
                if len(generated_contents) < 15 and http_code == 200 and not is_cache_hit:
                    prompt, reply = rng.choice(SAMPLE_PROMPTS)
                    generated_contents.append(
                        RequestContent(
                            request_id=log_id,
                            request_json={"messages": [{"role": "user", "content": prompt}]},
                            response_json={
                                "choices": [{"message": {"role": "assistant", "content": reply}}]
                            },
                        )
                    )

            # Project 2 calls
            for _ in range(num_p2):
                minute = rng.randint(0, 59)
                second = rng.randint(0, 59)
                req_time = day_date.replace(hour=hour, minute=minute, second=second, microsecond=0)

                prov, mod = (
                    ("anthropic", "claude-sonnet-5") if rng.random() < 0.70 else ("openai", "gpt-5")
                )
                price_row = await get_price(prov, mod)

                inp_tokens = rng.randint(200, 1200)
                out_tokens = rng.randint(80, 500)
                lat_ms = rng.randint(350, 1200)
                cost_usd = calculate_cost(prov, mod, inp_tokens, out_tokens, 0, price=price_row)

                log_id = uuid.uuid4()
                log_entry = RequestLog(
                    id=log_id,
                    project_id=p2.id,
                    gateway_key_id=k2.id,
                    created_at=req_time,
                    endpoint="chat",
                    provider=prov,
                    model_requested=f"{prov}/{mod}",
                    model_used=f"{prov}/{mod}",
                    status="ok",
                    http_status=200,
                    input_tokens=inp_tokens,
                    output_tokens=out_tokens,
                    cost_micro_usd=cost_usd,
                    saved_micro_usd=0,
                    latency_ms=lat_ms,
                    ttft_ms=int(lat_ms * 0.35),
                    streamed=True,
                    cache_hit=False,
                    fallback_used=False,
                    finish_reason="stop",
                    empty_or_truncated=False,
                    user_tag=rng.choice(["engineer-dev", "ci-pipeline", "data-analytics"]),
                    feedback_score=rng.choice([1, 1, -1, None]),
                )
                generated_logs.append(log_entry)

    session.add_all(generated_logs)
    session.add_all(generated_contents)

    # 7. Add demo BudgetAlert rows
    alert1 = BudgetAlert(
        id=uuid.uuid4(),
        project_id=p1.id,
        period="daily",
        period_start=(now - timedelta(days=2)).replace(hour=0, minute=0, second=0, microsecond=0),
        threshold_percent=50,
        spend_micro_usd=52_000_000,
        budget_micro_usd=100_000_000,
        created_at=now - timedelta(days=2, hours=4),
        webhook_status="sent",
        webhook_attempts=1,
    )
    alert2 = BudgetAlert(
        id=uuid.uuid4(),
        project_id=p1.id,
        period="daily",
        period_start=(now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0),
        threshold_percent=80,
        spend_micro_usd=81_500_000,
        budget_micro_usd=100_000_000,
        created_at=now - timedelta(days=1, hours=2),
        webhook_status="sent",
        webhook_attempts=1,
    )
    session.add_all([alert1, alert2])

    # 8. Set demo mode settings in app_setting table
    await _upsert_setting(session, "demo_mode", True)
    await _upsert_setting(session, "retention_days", 30)

    await session.commit()
    logger.info(
        "Demo seed complete: 2 projects, %d request logs, %d content traces, 2 budget alerts.",
        len(generated_logs),
        len(generated_contents),
    )
    return {
        "projects_count": 2,
        "logs_count": len(generated_logs),
        "content_count": len(generated_contents),
    }


async def clear_demo(session: AsyncSession) -> dict[str, Any]:
    """Remove all demo projects, keys, configs, requests, traces, and alerts."""
    await session.execute(
        delete(RequestContent).where(
            RequestContent.request_id.in_(
                select(RequestLog.id).where(RequestLog.project_id.in_([PROJECT_1_ID, PROJECT_2_ID]))
            )
        )
    )
    r_logs = await session.execute(
        delete(RequestLog).where(RequestLog.project_id.in_([PROJECT_1_ID, PROJECT_2_ID]))
    )
    r_alerts = await session.execute(
        delete(BudgetAlert).where(BudgetAlert.project_id.in_([PROJECT_1_ID, PROJECT_2_ID]))
    )
    r_keys = await session.execute(
        delete(GatewayKey).where(GatewayKey.project_id.in_([PROJECT_1_ID, PROJECT_2_ID]))
    )
    r_configs = await session.execute(
        delete(ProjectConfig).where(ProjectConfig.project_id.in_([PROJECT_1_ID, PROJECT_2_ID]))
    )
    r_projects = await session.execute(
        delete(Project).where(Project.id.in_([PROJECT_1_ID, PROJECT_2_ID]))
    )

    await _upsert_setting(session, "demo_mode", False)
    await session.commit()
    logger.info("Demo data cleared: %d projects, %d logs", r_projects.rowcount, r_logs.rowcount)
    return {
        "projects_deleted": r_projects.rowcount,
        "logs_deleted": r_logs.rowcount,
        "alerts_deleted": r_alerts.rowcount,
        "keys_deleted": r_keys.rowcount,
        "configs_deleted": r_configs.rowcount,
    }


async def _upsert_setting(session: AsyncSession, key: str, value: Any) -> None:
    stmt = select(AppSetting).where(AppSetting.key == key)
    res = await session.execute(stmt)
    setting = res.scalar_one_or_none()
    if setting is not None:
        setting.value = value
    else:
        session.add(AppSetting(key=key, value=value))


async def main() -> None:
    session_factory = get_sessionmaker()
    async with session_factory() as session:
        await seed_demo(session)


if __name__ == "__main__":
    asyncio.run(main())
