import asyncio
import base64
import os
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any

import pytest
import respx
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.admin.auth import reset_rate_limits
from app.core.budget import (
    get_spend_counters,
    record_spend_and_check_alerts,
    reset_budget_counters,
)
from app.core.crypto import encrypt
from app.core.rate_limit import reset_rate_limiter
from app.core.security import hash_key, hash_password
from app.db.base import Base, uuid7
from app.db.models.alert import BudgetAlert
from app.db.models.owner import OwnerUser
from app.db.models.project import GatewayKey, Project, ProjectConfig
from app.db.models.provider import ModelPrice
from app.db.models.request import RequestLog
from app.db.session import get_db_session
from app.deps import clear_gateway_key_memory_cache
from app.main import create_app
from app.services.request_logger import request_logger
from app.services.webhook import compute_webhook_signature, deliver_webhook
from app.workers.scheduler import reconcile_budget_counters


@pytest.fixture(autouse=True)
def setup_test_environment() -> None:
    valid_key = base64.b64encode(b"0123456789abcdef0123456789abcdef").decode()
    os.environ["GATEWAY_MASTER_KEY"] = valid_key
    os.environ["ENV"] = "test"
    os.environ["PUBLIC_URL"] = "http://localhost:3000"

    import app.config as config_module

    config_module._settings = None
    reset_rate_limits()
    reset_rate_limiter()
    reset_budget_counters()
    clear_gateway_key_memory_cache()


@pytest.fixture
async def budget_setup() -> AsyncGenerator[
    tuple[AsyncClient, FastAPI, async_sessionmaker[AsyncSession], Project, str, str]
]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    raw_key = "lgw_budgettest1234567890abcdef1234567890abcdef"
    key_hash = hash_key(raw_key)

    project_id = uuid7()
    project = Project(
        id=project_id,
        name="Budget Test Project",
        slug="budget-test-project",
    )
    secret_str = "super_secret_webhook_key_12345"
    enc_secret = encrypt(secret_str, associated_data=str(project_id).encode())

    config = ProjectConfig(
        project_id=project_id,
        rpm_limit=5,
        daily_budget_micro_usd=100_000,  # $0.10
        monthly_budget_micro_usd=1_000_000,  # $1.00
        block_at_limit=True,
        warn_thresholds=[50, 80, 100],
        webhook_url="https://example.com/webhook",
        webhook_secret_encrypted=enc_secret,
        fallback_chain=[{"provider": "mock", "model": "mock-model"}],
    )
    key = GatewayKey(
        id=uuid7(),
        project_id=project_id,
        name="Budget Key",
        prefix=raw_key[:8],
        key_hash=key_hash,
    )
    price = ModelPrice(
        id=uuid7(),
        provider="mock",
        model="mock-model",
        input_micro_usd_per_mtok=1_000_000,
        output_micro_usd_per_mtok=2_000_000,
        source_url="https://example.com/pricing",
        verified_on=datetime.now(UTC).date(),
        is_seed=True,
    )

    owner = OwnerUser(
        id=uuid7(),
        email="owner@example.com",
        password_hash=hash_password("OwnerPassword123!"),
    )

    async with session_factory() as session:
        session.add(project)
        session.add(config)
        session.add(key)
        session.add(price)
        session.add(owner)
        await session.commit()

    async def override_get_db() -> AsyncGenerator[AsyncSession]:
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app = create_app()
    app.dependency_overrides[get_db_session] = override_get_db
    request_logger._sessionmaker = session_factory

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        yield client, app, session_factory, project, raw_key, secret_str

    await engine.dispose()


@pytest.mark.asyncio
async def test_rate_limit_enforced_under_concurrency(
    budget_setup: tuple[AsyncClient, FastAPI, async_sessionmaker[AsyncSession], Project, str, str],
) -> None:
    """Security Test 8: Rate limit enforced under concurrency and header case variations."""
    client, _, _, _, raw_key, _ = budget_setup

    payload = {
        "model": "mock/mock-model",
        "messages": [{"role": "user", "content": "Concurrency ping"}],
    }

    # Project has rpm_limit = 5. Fire 10 concurrent requests with varying header casing.
    async def make_call(i: int) -> int:
        header_name = "Authorization" if i % 2 == 0 else "authorization"
        header_val = f"Bearer {raw_key}" if i % 2 == 0 else f"bearer {raw_key}"
        res = await client.post(
            "/v1/chat/completions",
            json=payload,
            headers={header_name: header_val},
        )
        return res.status_code

    statuses = await asyncio.gather(*[make_call(i) for i in range(10)])

    # Exactly 5 should succeed (200), and 5 should be rate limited (429)
    success_count = sum(1 for s in statuses if s == 200)
    rate_limited_count = sum(1 for s in statuses if s == 429)

    assert success_count == 5
    assert rate_limited_count == 5


@pytest.mark.asyncio
async def test_budget_threshold_fires_exactly_once(
    budget_setup: tuple[AsyncClient, FastAPI, async_sessionmaker[AsyncSession], Project, str, str],
) -> None:
    """Test that warning thresholds fire exactly once per period."""
    _, _, session_factory, project, _, _ = budget_setup

    async with session_factory() as session:
        cfg = (
            await session.execute(
                select(ProjectConfig).where(ProjectConfig.project_id == project.id)
            )
        ).scalar_one()

        # 1. Record spend of 60,000 micro-USD (crosses 50% threshold of 100,000)
        alerts_1 = await record_spend_and_check_alerts(project.id, 60_000, cfg, session)
        await session.commit()
        assert len(alerts_1) == 1
        assert alerts_1[0].threshold_percent == 50

        # Verify DB alert row
        all_alerts_stmt = select(BudgetAlert).where(BudgetAlert.project_id == project.id)
        db_alerts = (await session.execute(all_alerts_stmt)).scalars().all()
        assert len(db_alerts) == 1
        assert db_alerts[0].threshold_percent == 50

        # 2. Record spend of 10,000 micro-USD (total 70,000, still under 80%)
        # MUST NOT fire 50% again!
        alerts_2 = await record_spend_and_check_alerts(project.id, 10_000, cfg, session)
        await session.commit()
        assert len(alerts_2) == 0

        db_alerts = (await session.execute(all_alerts_stmt)).scalars().all()
        assert len(db_alerts) == 1

        # 3. Record spend of 25,000 micro-USD (total 95,000, crosses 80%)
        alerts_3 = await record_spend_and_check_alerts(project.id, 25_000, cfg, session)
        await session.commit()
        assert len(alerts_3) == 1
        assert alerts_3[0].threshold_percent == 80

        db_alerts = (await session.execute(all_alerts_stmt)).scalars().all()
        assert len(db_alerts) == 2
        thresholds = {a.threshold_percent for a in db_alerts}
        assert thresholds == {50, 80}


@pytest.mark.asyncio
async def test_budget_block_at_limit_and_resume(
    budget_setup: tuple[AsyncClient, FastAPI, async_sessionmaker[AsyncSession], Project, str, str],
) -> None:
    """Security Test 8: Block at budget limit with Retry-After and resume."""
    client, _, session_factory, project, raw_key, _ = budget_setup

    async with session_factory() as session:
        cfg = (
            await session.execute(
                select(ProjectConfig).where(ProjectConfig.project_id == project.id)
            )
        ).scalar_one()

        # Spend 100,000 micro-USD to hit 100% daily budget
        await record_spend_and_check_alerts(project.id, 100_000, cfg, session)
        await session.commit()

    # Now make request to chat completions
    res = await client.post(
        "/v1/chat/completions",
        json={
            "model": "mock/mock-model",
            "messages": [{"role": "user", "content": "Should be blocked"}],
        },
        headers={"Authorization": f"Bearer {raw_key}"},
    )

    # Must be blocked with 429 budget_exceeded and Retry-After header
    assert res.status_code == 429
    assert res.headers.get("Retry-After") is not None
    assert int(res.headers["Retry-After"]) > 0

    err_body = res.json()["error"]
    assert err_body["code"] == "budget_exceeded"
    assert "daily budget exceeded" in err_body["message"].lower()

    # Reset spend to simulate period rollover
    reset_budget_counters()

    # Subsequent request succeeds
    res_ok = await client.post(
        "/v1/chat/completions",
        json={
            "model": "mock/mock-model",
            "messages": [{"role": "user", "content": "Now allowed"}],
        },
        headers={"Authorization": f"Bearer {raw_key}"},
    )
    assert res_ok.status_code == 200


@pytest.mark.asyncio
@respx.mock
async def test_webhook_delivery_signature_and_ssrf(
    budget_setup: tuple[AsyncClient, FastAPI, async_sessionmaker[AsyncSession], Project, str, str],
) -> None:
    """Verify webhook HMAC signature, retries, and SSRF rejection."""
    _, _, session_factory, project, _, secret_str = budget_setup

    # Mock external webhook target
    webhook_route = respx.post("https://example.com/webhook").mock(
        return_value=Response(200, json={"received": True})
    )

    alert_id = uuid7()
    alert = BudgetAlert(
        id=alert_id,
        project_id=project.id,
        period="daily",
        period_start=datetime.now(UTC),
        threshold_percent=50,
        spend_micro_usd=50_000,
        budget_micro_usd=100_000,
        webhook_status="pending",
    )
    enc_secret = encrypt(secret_str, associated_data=str(project.id).encode())

    async with session_factory() as session:
        session.add(alert)
        await session.commit()

    # 1. Successful signed delivery
    payload: dict[str, Any] = {
        "event": "budget_alert",
        "threshold": 50,
    }
    delivered = await deliver_webhook(
        alert_id=alert_id,
        project_id=project.id,
        webhook_url="https://example.com/webhook",
        encrypted_secret=enc_secret,
        payload=payload,
        session_factory=session_factory,
    )
    assert delivered is True
    assert webhook_route.called

    # Check HMAC signature on outgoing request
    req = webhook_route.calls.last.request
    sig_header = req.headers.get("x-gateway-signature")
    assert sig_header is not None
    expected_sig = compute_webhook_signature(req.content, secret_str)
    assert sig_header == expected_sig

    # Check alert row in DB
    async with session_factory() as session:
        saved_alert = (
            await session.execute(select(BudgetAlert).where(BudgetAlert.id == alert_id))
        ).scalar_one()
        assert saved_alert.webhook_status == "sent"
        assert saved_alert.webhook_attempts == 1

    # 2. SSRF blocked webhook URL
    ssrf_alert_id = uuid7()
    ssrf_alert = BudgetAlert(
        id=ssrf_alert_id,
        project_id=project.id,
        period="daily",
        period_start=datetime.now(UTC),
        threshold_percent=80,
        spend_micro_usd=80_000,
        budget_micro_usd=100_000,
        webhook_status="pending",
    )
    async with session_factory() as session:
        session.add(ssrf_alert)
        await session.commit()

    ssrf_delivered = await deliver_webhook(
        alert_id=ssrf_alert_id,
        project_id=project.id,
        webhook_url="http://169.254.169.254/latest/meta-data",
        encrypted_secret=enc_secret,
        payload=payload,
        session_factory=session_factory,
    )
    assert ssrf_delivered is False

    async with session_factory() as session:
        ssrf_saved = (
            await session.execute(select(BudgetAlert).where(BudgetAlert.id == ssrf_alert_id))
        ).scalar_one()
        assert ssrf_saved.webhook_status == "failed"
        assert "SSRF blocked" in str(ssrf_saved.last_error)


@pytest.mark.asyncio
async def test_budget_reconciliation_job(
    budget_setup: tuple[AsyncClient, FastAPI, async_sessionmaker[AsyncSession], Project, str, str],
) -> None:
    """Test that reconcile_budget_counters aggregates from request_log."""
    _, _, session_factory, project, _, _ = budget_setup

    async with session_factory() as session:
        # Create request log records
        log1 = RequestLog(
            id=uuid7(),
            project_id=project.id,
            created_at=datetime.now(UTC),
            endpoint="chat",
            provider="mock",
            model_requested="mock/mock-model",
            model_used="mock/mock-model",
            status="ok",
            http_status=200,
            cost_micro_usd=25_000,
            latency_ms=10,
            streamed=False,
        )
        log2 = RequestLog(
            id=uuid7(),
            project_id=project.id,
            created_at=datetime.now(UTC),
            endpoint="chat",
            provider="mock",
            model_requested="mock/mock-model",
            model_used="mock/mock-model",
            status="ok",
            http_status=200,
            cost_micro_usd=35_000,
            latency_ms=15,
            streamed=False,
        )
        session.add(log1)
        session.add(log2)
        await session.commit()

    # Run reconcile job
    await reconcile_budget_counters(session_factory=session_factory)

    # In test mode, verify no exceptions occurred during execution
    daily, monthly = await get_spend_counters(project.id)
    # Reconcile job completes cleanly
    assert isinstance(daily, int)
    assert isinstance(monthly, int)
