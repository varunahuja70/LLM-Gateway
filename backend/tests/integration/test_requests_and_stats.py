import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.security import generate_session_token, hash_token
from app.db.base import Base, utc_now
from app.db.models.owner import OwnerUser, Session
from app.db.models.project import Project, ProjectConfig
from app.db.models.request import RequestContent, RequestLog
from app.db.session import get_db_session
from app.main import app
from app.services.retention import enforce_retention
from app.services.stats import (
    compute_percentile_cont,
    get_models_stats,
    get_overview_stats,
)


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
async def setup_data(test_db: AsyncSession) -> dict[str, Any]:
    # 1. Create owner
    owner_id = uuid.uuid4()
    owner = OwnerUser(
        id=owner_id,
        email="owner@example.com",
        password_hash="test_hash",
        created_at=utc_now(),
    )
    test_db.add(owner)

    # 2. Session
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

    # 3. Two projects
    p1 = Project(id=uuid.uuid4(), name="Project Alpha", slug="project-alpha")
    p2 = Project(id=uuid.uuid4(), name="Project Beta", slug="project-beta")
    test_db.add_all([p1, p2])
    await test_db.flush()

    c1 = ProjectConfig(project_id=p1.id, daily_budget_micro_usd=10_000_000)
    c2 = ProjectConfig(project_id=p2.id, daily_budget_micro_usd=20_000_000)
    test_db.add_all([c1, c2])

    now = datetime(2026, 10, 3, 12, 0, 0, tzinfo=UTC)

    # 4. Hand-computed fixtures:
    # R1: Project 1, openai/gpt-5-mini, ok, inp 100, out 50, cached 20, cost 500, saved 100, lat 200, ttft 50, streamed, fb 1
    r1 = RequestLog(
        id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        project_id=p1.id,
        created_at=now - timedelta(minutes=45),
        endpoint="chat",
        provider="openai",
        model_requested="openai/gpt-5-mini",
        model_used="openai/gpt-5-mini",
        status="ok",
        http_status=200,
        input_tokens=100,
        output_tokens=50,
        cached_input_tokens=20,
        cost_micro_usd=500,
        saved_micro_usd=100,
        latency_ms=200,
        ttft_ms=50,
        streamed=True,
        cache_hit=False,
        fallback_used=False,
        empty_or_truncated=False,
        user_tag="user-alpha",
        feedback_score=1,
    )
    # R2: Project 1, openai/gpt-5-mini, ok, cache hit, inp 0, out 0, cost 0, saved 300, lat 20, ttft None, not streamed
    r2 = RequestLog(
        id=uuid.UUID("00000000-0000-0000-0000-000000000002"),
        project_id=p1.id,
        created_at=now - timedelta(minutes=30),
        endpoint="chat",
        provider="openai",
        model_requested="openai/gpt-5-mini",
        model_used="openai/gpt-5-mini",
        status="ok",
        http_status=200,
        input_tokens=0,
        output_tokens=0,
        cached_input_tokens=0,
        cost_micro_usd=0,
        saved_micro_usd=300,
        latency_ms=20,
        ttft_ms=None,
        streamed=False,
        cache_hit=True,
        fallback_used=False,
        empty_or_truncated=False,
        user_tag="user-alpha",
        feedback_score=None,
    )
    # R3: Project 1, anthropic/claude-sonnet-5, error, inp 50, out 0, cost 100, saved 0, lat 500, fallback used, empty_or_truncated True, fb -1
    r3 = RequestLog(
        id=uuid.UUID("00000000-0000-0000-0000-000000000003"),
        project_id=p1.id,
        created_at=now - timedelta(minutes=15),
        endpoint="chat",
        provider="anthropic",
        model_requested="openai/gpt-5",
        model_used="anthropic/claude-sonnet-5",
        status="error",
        http_status=500,
        error_type="upstream_error",
        error_message_safe="Upstream failure",
        input_tokens=50,
        output_tokens=0,
        cached_input_tokens=0,
        cost_micro_usd=100,
        saved_micro_usd=0,
        latency_ms=500,
        ttft_ms=None,
        streamed=False,
        cache_hit=False,
        fallback_used=True,
        fallback_from="openai/gpt-5",
        fallback_reason="500 Internal Error",
        empty_or_truncated=True,
        user_tag="user-beta",
        feedback_score=-1,
    )
    # R4: Project 2, openai/gpt-5-mini, ok, inp 200, out 100, cost 1000, saved 0, lat 300, ttft 80, streamed
    r4 = RequestLog(
        id=uuid.UUID("00000000-0000-0000-0000-000000000004"),
        project_id=p2.id,
        created_at=now - timedelta(minutes=5),
        endpoint="chat",
        provider="openai",
        model_requested="openai/gpt-5-mini",
        model_used="openai/gpt-5-mini",
        status="ok",
        http_status=200,
        input_tokens=200,
        output_tokens=100,
        cached_input_tokens=0,
        cost_micro_usd=1000,
        saved_micro_usd=0,
        latency_ms=300,
        ttft_ms=80,
        streamed=True,
        cache_hit=False,
        fallback_used=False,
        empty_or_truncated=False,
        user_tag=None,
        feedback_score=None,
    )

    test_db.add_all([r1, r2, r3, r4])
    await test_db.flush()

    # Content for R1
    c_r1 = RequestContent(
        request_id=r1.id,
        request_json={"messages": [{"role": "user", "content": "Hi"}]},
        response_json={"choices": [{"message": {"role": "assistant", "content": "Hello"}}]},
    )
    test_db.add(c_r1)
    await test_db.commit()

    return {
        "owner": owner,
        "token": raw_token,
        "p1": p1,
        "p2": p2,
        "r1": r1,
        "r2": r2,
        "r3": r3,
        "r4": r4,
        "now": now,
    }


@pytest.mark.anyio
async def test_compute_percentile_cont_math() -> None:
    """Verify linear interpolation matches exact mathematical expectations."""
    assert compute_percentile_cont([], 0.5) is None
    assert compute_percentile_cont([42], 0.5) == 42.0

    # 2 items: [10, 20] -> p50 is 15.0
    assert compute_percentile_cont([10, 20], 0.50) == 15.0

    # 3 items: [20, 200, 300]
    # rank for p50: 0.5 * 2 = 1.0 -> 200.0
    assert compute_percentile_cont([20, 200, 300], 0.50) == 200.0
    # rank for p95: 0.95 * 2 = 1.9 -> index 1 + 0.9 * (300 - 200) = 290.0
    assert compute_percentile_cont([20, 200, 300], 0.95) == 290.0
    # rank for p99: 0.99 * 2 = 1.98 -> 200 + 0.98 * 100 = 298.0
    assert compute_percentile_cont([20, 200, 300], 0.99) == 298.0


@pytest.mark.anyio
async def test_stats_match_fixture_dataset(
    test_db: AsyncSession, setup_data: dict[str, Any]
) -> None:
    """Verify stats match hand-computed fixtures exactly."""
    p1 = setup_data["p1"]

    # 1. Project 1 Overview
    p1_overview = await get_overview_stats(test_db, project_id=p1.id)
    assert p1_overview.total_requests == 3
    assert p1_overview.input_tokens == 150
    assert p1_overview.output_tokens == 50
    assert p1_overview.total_tokens == 200
    assert p1_overview.cached_input_tokens == 20
    assert p1_overview.total_cost_micro_usd == 600
    assert p1_overview.saved_micro_usd == 400
    assert p1_overview.error_rate == pytest.approx(0.3333, abs=1e-4)
    assert p1_overview.fallback_rate == pytest.approx(0.3333, abs=1e-4)
    assert p1_overview.cache_hit_rate == pytest.approx(0.3333, abs=1e-4)
    assert p1_overview.avg_latency_ms == pytest.approx(240.0, abs=1e-2)

    # 2. Global Overview (both projects)
    global_overview = await get_overview_stats(test_db)
    assert global_overview.total_requests == 4
    assert global_overview.total_tokens == 500
    assert global_overview.input_tokens == 350
    assert global_overview.output_tokens == 150
    assert global_overview.total_cost_micro_usd == 1600
    assert global_overview.saved_micro_usd == 400
    assert global_overview.error_rate == 0.25
    assert global_overview.fallback_rate == 0.25
    assert global_overview.cache_hit_rate == 0.25
    assert global_overview.avg_latency_ms == pytest.approx(255.0, abs=1e-2)

    # 3. Model Quality breakdown
    models = await get_models_stats(test_db)
    assert len(models) == 2

    # Find gpt-5-mini
    m_mini = next(m for m in models if m.model == "openai/gpt-5-mini")
    assert m_mini.total_requests == 3
    assert m_mini.total_tokens == 450
    assert m_mini.total_cost_micro_usd == 1500
    assert m_mini.error_rate == 0.0
    assert m_mini.fallback_rate == 0.0
    assert m_mini.p50_latency_ms == 200.0
    assert m_mini.p95_latency_ms == 290.0
    assert m_mini.p99_latency_ms == 298.0
    assert m_mini.avg_ttft_ms == 65.0
    assert m_mini.empty_or_truncated_rate == 0.0
    assert m_mini.avg_feedback_score == 1.0

    # Find claude-sonnet-5
    m_sonnet = next(m for m in models if m.model == "anthropic/claude-sonnet-5")
    assert m_sonnet.total_requests == 1
    assert m_sonnet.error_rate == 1.0
    assert m_sonnet.fallback_rate == 1.0
    assert m_sonnet.empty_or_truncated_rate == 1.0
    assert m_sonnet.avg_feedback_score == -1.0


@pytest.mark.anyio
async def test_admin_requests_api_and_pagination(
    test_db: AsyncSession, setup_data: dict[str, Any]
) -> None:
    """Test /admin/requests filtering, detail, and cursor pagination."""
    token = setup_data["token"]
    cookies = {"__Host-session": token}

    async def override_get_db() -> AsyncGenerator[AsyncSession]:
        yield test_db

    app.dependency_overrides[get_db_session] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", cookies=cookies) as client:
        # 1. Fetch page with limit=2 (should have more)
        r = await client.get("/admin/requests?limit=2")
        assert r.status_code == 200
        data = r.json()
        assert len(data["items"]) == 2
        assert data["has_more"] is True
        assert data["next_cursor"] is not None

        # Newest first: R4 then R3
        assert data["items"][0]["id"] == str(setup_data["r4"].id)
        assert data["items"][1]["id"] == str(setup_data["r3"].id)

        # 2. Fetch page 2 using cursor
        cursor = data["next_cursor"]
        r2 = await client.get(f"/admin/requests?limit=2&cursor={cursor}")
        assert r2.status_code == 200
        data2 = r2.json()
        assert len(data2["items"]) == 2
        assert data2["has_more"] is False
        assert data2["items"][0]["id"] == str(setup_data["r2"].id)
        assert data2["items"][1]["id"] == str(setup_data["r1"].id)

        # 3. Filter by project
        p1 = setup_data["p1"]
        rf = await client.get(f"/admin/requests?project_id={p1.id}")
        assert rf.status_code == 200
        assert len(rf.json()["items"]) == 3

        # 4. Filter by status error
        re_err = await client.get("/admin/requests?status=error")
        assert re_err.status_code == 200
        assert len(re_err.json()["items"]) == 1
        assert re_err.json()["items"][0]["id"] == str(setup_data["r3"].id)

        # 5. Search by user tag
        rs = await client.get("/admin/requests?search=user-alpha")
        assert rs.status_code == 200
        assert len(rs.json()["items"]) == 2

        # 6. Request Detail with logged content
        rd = await client.get(f"/admin/requests/{setup_data['r1'].id}")
        assert rd.status_code == 200
        detail = rd.json()
        assert detail["id"] == str(setup_data["r1"].id)
        assert detail["content"] is not None
        assert detail["content"]["request_json"]["messages"][0]["content"] == "Hi"

        # 7. Request Detail without logged content
        rd2 = await client.get(f"/admin/requests/{setup_data['r2'].id}")
        assert rd2.status_code == 200
        assert rd2.json()["content"] is None

        # 8. Request Detail 404
        r404 = await client.get(f"/admin/requests/{uuid.uuid4()}")
        assert r404.status_code == 404

    app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_admin_stats_endpoints(test_db: AsyncSession, setup_data: dict[str, Any]) -> None:
    """Test /admin/stats/* endpoints through HTTP client."""
    token = setup_data["token"]
    cookies = {"__Host-session": token}
    p1 = setup_data["p1"]

    async def override_get_db() -> AsyncGenerator[AsyncSession]:
        yield test_db

    app.dependency_overrides[get_db_session] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", cookies=cookies) as client:
        # Overview
        ro = await client.get("/admin/stats/overview")
        assert ro.status_code == 200
        assert ro.json()["total_requests"] == 4

        # Timeseries
        rt = await client.get("/admin/stats/timeseries?bucket=hour")
        assert rt.status_code == 200
        ts_data = rt.json()
        assert ts_data["bucket"] == "hour"
        assert len(ts_data["data"]) >= 1

        # Models
        rm = await client.get("/admin/stats/models")
        assert rm.status_code == 200
        assert len(rm.json()["data"]) == 2

        # Project stats
        rp = await client.get(f"/admin/stats/projects/{p1.id}")
        assert rp.status_code == 200
        assert rp.json()["project_id"] == str(p1.id)
        assert rp.json()["overview"]["total_requests"] == 3

    app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_retention_service_and_cascade(
    test_db: AsyncSession, setup_data: dict[str, Any]
) -> None:
    """Verify retention removes only rows older than retention_days, including cascaded content."""
    p1 = setup_data["p1"]

    # Insert an old request log (40 days old) with content
    old_id = uuid.uuid4()
    old_req = RequestLog(
        id=old_id,
        project_id=p1.id,
        created_at=utc_now() - timedelta(days=40),
        endpoint="chat",
        provider="openai",
        model_requested="openai/gpt-5-mini",
        model_used="openai/gpt-5-mini",
        status="ok",
        http_status=200,
        latency_ms=100,
    )
    old_content = RequestContent(
        request_id=old_id,
        request_json={"test": "old"},
        response_json={"test": "old_resp"},
    )
    test_db.add(old_req)
    test_db.add(old_content)
    await test_db.commit()

    # Enforce 30 day retention
    deleted = await enforce_retention(test_db, retention_days=30)
    assert deleted == 1

    # Verify old log and content are deleted
    check_log = await test_db.scalar(select(RequestLog.id).where(RequestLog.id == old_id))
    assert check_log is None
    check_content = await test_db.scalar(
        select(RequestContent.request_id).where(RequestContent.request_id == old_id)
    )
    assert check_content is None

    # Verify recent logs and content are intact
    recent_r1 = await test_db.scalar(
        select(RequestLog.id).where(RequestLog.id == setup_data["r1"].id)
    )
    assert recent_r1 == setup_data["r1"].id
    recent_content = await test_db.scalar(
        select(RequestContent.request_id).where(RequestContent.request_id == setup_data["r1"].id)
    )
    assert recent_content == setup_data["r1"].id


@pytest.mark.anyio
async def test_delete_project_data_endpoint(
    test_db: AsyncSession, setup_data: dict[str, Any]
) -> None:
    """Verify DELETE /admin/projects/{id}/data removes all project records without affecting others."""
    token = setup_data["token"]
    cookies = {"__Host-session": token}
    headers = {"X-CSRF-Token": "test-csrf"}
    p1 = setup_data["p1"]
    p2 = setup_data["p2"]

    async def override_get_db() -> AsyncGenerator[AsyncSession]:
        yield test_db

    app.dependency_overrides[get_db_session] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", cookies=cookies) as client:
        res = await client.delete(f"/admin/projects/{p1.id}/data", headers=headers)
        assert res.status_code == 200
        assert "Successfully deleted 3 request records" in res.json()["message"]

    # Verify project 1 logs and content are gone
    p1_logs = (
        await test_db.scalars(select(RequestLog.id).where(RequestLog.project_id == p1.id))
    ).all()
    assert len(p1_logs) == 0

    # Verify project 2 logs remain intact
    p2_logs = (
        await test_db.scalars(select(RequestLog.id).where(RequestLog.project_id == p2.id))
    ).all()
    assert len(p2_logs) == 1

    app.dependency_overrides.clear()
