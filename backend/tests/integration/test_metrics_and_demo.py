import uuid
from collections.abc import AsyncGenerator
from datetime import timedelta
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.security import generate_session_token, hash_token
from app.db.base import Base, utc_now
from app.db.models.alert import BudgetAlert
from app.db.models.owner import OwnerUser, Session
from app.db.models.project import Project
from app.db.models.request import RequestContent, RequestLog
from app.db.session import get_db_session
from app.main import app
from scripts.seed_demo import PROJECT_1_ID, PROJECT_2_ID, seed_demo


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest_asyncio.fixture
async def test_db() -> AsyncGenerator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with session_maker() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def setup_owner(test_db: AsyncSession) -> dict[str, Any]:
    owner_id = uuid.uuid4()
    owner = OwnerUser(
        id=owner_id,
        email="owner@example.com",
        password_hash="test_hash",
        created_at=utc_now(),
    )
    test_db.add(owner)

    raw_token, session_id = generate_session_token()
    session = Session(
        id=session_id,
        owner_id=owner_id,
        csrf_token_hash=hash_token("test-csrf"),
        created_at=utc_now(),
        last_seen_at=utc_now(),
        expires_at=utc_now() + timedelta(days=7),
    )
    test_db.add(session)
    await test_db.commit()

    return {"token": raw_token, "csrf": "test-csrf", "owner": owner}


@pytest.mark.anyio
async def test_metrics_endpoint() -> None:
    """Verify /metrics exposes Prometheus metrics snapshot in expected text format."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/metrics")
        assert res.status_code == 200
        content = res.text
        assert "gateway_requests_total" in content
        assert "gateway_request_duration_seconds" in content
        assert "gateway_log_queue_depth" in content
        assert "gateway_cache_hits_total" in content
        assert "gateway_budget_blocks_total" in content


@pytest.mark.anyio
async def test_settings_api_and_demo_banner(
    test_db: AsyncSession, setup_owner: dict[str, Any]
) -> None:
    """Verify GET and PUT /admin/settings."""
    cookies = {"__Host-session": setup_owner["token"]}
    headers = {"X-CSRF-Token": setup_owner["csrf"]}

    async def override_get_db() -> AsyncGenerator[AsyncSession]:
        yield test_db

    app.dependency_overrides[get_db_session] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", cookies=cookies) as client:
        # 1. GET settings defaults
        r1 = await client.get("/admin/settings")
        assert r1.status_code == 200
        data1 = r1.json()
        assert data1["retention_days"] == 30
        assert "demo_banner" in data1
        assert "is_demo" in data1["demo_banner"]

        # 2. PUT settings update
        r2 = await client.put(
            "/admin/settings",
            json={"retention_days": 60, "demo_mode": True},
            headers=headers,
        )
        assert r2.status_code == 200
        data2 = r2.json()
        assert data2["retention_days"] == 60
        assert data2["demo_mode"] is True
        assert data2["demo_banner"]["is_demo"] is True

    app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_seed_demo_script(test_db: AsyncSession) -> None:
    """Verify scripts/seed_demo.py fills the database with projects, logs, and alerts."""
    result = await seed_demo(test_db)
    assert result["projects_count"] == 2
    assert result["logs_count"] > 100
    assert result["content_count"] > 0

    # Verify Project 1 & Project 2 exist
    p1 = await test_db.scalar(select(Project).where(Project.id == PROJECT_1_ID))
    p2 = await test_db.scalar(select(Project).where(Project.id == PROJECT_2_ID))
    assert p1 is not None
    assert p2 is not None

    # Verify logs exist across both projects
    p1_logs = await test_db.scalar(
        select(func.count(RequestLog.id)).where(RequestLog.project_id == PROJECT_1_ID)
    )
    p2_logs = await test_db.scalar(
        select(func.count(RequestLog.id)).where(RequestLog.project_id == PROJECT_2_ID)
    )
    assert p1_logs is not None and p1_logs > 50
    assert p2_logs is not None and p2_logs > 20

    # Verify cache hits, fallbacks, and errors exist
    cache_hits = await test_db.scalar(
        select(func.count(RequestLog.id)).where(RequestLog.cache_hit.is_(True))
    )
    fallbacks = await test_db.scalar(
        select(func.count(RequestLog.id)).where(RequestLog.fallback_used.is_(True))
    )
    errors = await test_db.scalar(
        select(func.count(RequestLog.id)).where(RequestLog.status == "error")
    )
    assert cache_hits is not None and cache_hits > 0
    assert fallbacks is not None and fallbacks > 0
    assert errors is not None and errors > 0

    # Verify BudgetAlert rows exist
    alerts_count = await test_db.scalar(select(func.count(BudgetAlert.id)))
    assert alerts_count == 2

    # Verify RequestContent rows exist
    content_count = await test_db.scalar(select(func.count(RequestContent.request_id)))
    assert content_count is not None and content_count > 0

    # Verify idempotency by running seed_demo again
    result2 = await seed_demo(test_db)
    assert result2["projects_count"] == 2
    assert result2["logs_count"] == result["logs_count"]
