import base64
import os
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.admin.auth import reset_rate_limits
from app.core.budget import reset_budget_counters
from app.core.cache import clear_cache_for_testing
from app.core.rate_limit import reset_rate_limiter
from app.core.security import hash_key, hash_password
from app.db.base import Base, uuid7
from app.db.models.owner import OwnerUser
from app.db.models.project import GatewayKey, Project, ProjectConfig
from app.db.models.provider import ModelPrice
from app.db.models.request import RequestLog
from app.db.session import get_db_session
from app.deps import clear_gateway_key_memory_cache
from app.main import create_app
from app.services.request_logger import RequestLogItem, request_logger


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
    clear_cache_for_testing()
    clear_gateway_key_memory_cache()


@pytest.fixture
async def feedback_setup() -> AsyncGenerator[
    tuple[AsyncClient, FastAPI, async_sessionmaker[AsyncSession], Project, str, Project, str]
]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Project A
    raw_key_a = "lgw_feedback_a_1234567890abcdef12345678"
    key_hash_a = hash_key(raw_key_a)
    proj_a_id = uuid7()
    proj_a = Project(id=proj_a_id, name="Feedback Project A", slug="feedback-project-a")
    cfg_a = ProjectConfig(
        project_id=proj_a_id,
        rpm_limit=100,
        fallback_chain=[{"provider": "mock", "model": "mock-model"}],
    )
    key_a = GatewayKey(
        id=uuid7(),
        project_id=proj_a_id,
        name="Key A",
        prefix=raw_key_a[:8],
        key_hash=key_hash_a,
    )

    # Project B
    raw_key_b = "lgw_feedback_b_1234567890abcdef12345678"
    key_hash_b = hash_key(raw_key_b)
    proj_b_id = uuid7()
    proj_b = Project(id=proj_b_id, name="Feedback Project B", slug="feedback-project-b")
    cfg_b = ProjectConfig(
        project_id=proj_b_id,
        rpm_limit=100,
        fallback_chain=[{"provider": "mock", "model": "mock-model"}],
    )
    key_b = GatewayKey(
        id=uuid7(),
        project_id=proj_b_id,
        name="Key B",
        prefix=raw_key_b[:8],
        key_hash=key_hash_b,
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
        session.add_all([proj_a, cfg_a, key_a, proj_b, cfg_b, key_b, price, owner])
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
        yield client, app, session_factory, proj_a, raw_key_a, proj_b, raw_key_b

    await engine.dispose()


@pytest.mark.asyncio
async def test_feedback_own_request_success(
    feedback_setup: tuple[
        AsyncClient, FastAPI, async_sessionmaker[AsyncSession], Project, str, Project, str
    ],
) -> None:
    """Test submitting thumbs up and thumbs down on caller's own request."""
    client, _, session_factory, proj_a, raw_key_a, _, _ = feedback_setup

    # 1. Make a request as Project A
    res = await client.post(
        "/v1/chat/completions",
        json={
            "model": "mock/mock-model",
            "messages": [{"role": "user", "content": "Feedback test"}],
        },
        headers={"Authorization": f"Bearer {raw_key_a}"},
    )
    assert res.status_code == 200
    req_id = res.headers["x-gateway-request-id"]

    await request_logger.flush()

    # 2. Submit positive feedback (score = 1)
    fb_res1 = await client.post(
        "/v1/feedback",
        json={"request_id": req_id, "score": 1},
        headers={"Authorization": f"Bearer {raw_key_a}"},
    )
    assert fb_res1.status_code == 200
    data1 = fb_res1.json()
    assert data1["status"] == "ok"
    assert data1["request_id"] == req_id
    assert data1["score"] == 1

    # Verify in DB
    async with session_factory() as session:
        log = (
            await session.execute(select(RequestLog).where(RequestLog.id == uuid.UUID(req_id)))
        ).scalar_one()
        assert log.feedback_score == 1

    # 3. Update with negative feedback (score = -1)
    fb_res2 = await client.post(
        "/v1/feedback",
        json={"request_id": req_id, "score": -1},
        headers={"Authorization": f"Bearer {raw_key_a}"},
    )
    assert fb_res2.status_code == 200
    data2 = fb_res2.json()
    assert data2["score"] == -1

    async with session_factory() as session:
        log = (
            await session.execute(select(RequestLog).where(RequestLog.id == uuid.UUID(req_id)))
        ).scalar_one()
        assert log.feedback_score == -1


@pytest.mark.asyncio
async def test_feedback_cross_project_rejected_with_404(
    feedback_setup: tuple[
        AsyncClient, FastAPI, async_sessionmaker[AsyncSession], Project, str, Project, str
    ],
) -> None:
    """Test that submitting feedback on another project's request returns 404."""
    client, _, session_factory, _, raw_key_a, _, raw_key_b = feedback_setup

    # 1. Project A makes request
    res = await client.post(
        "/v1/chat/completions",
        json={
            "model": "mock/mock-model",
            "messages": [{"role": "user", "content": "Project A prompt"}],
        },
        headers={"Authorization": f"Bearer {raw_key_a}"},
    )
    assert res.status_code == 200
    req_id = res.headers["x-gateway-request-id"]

    await request_logger.flush()

    # 2. Project B attempts to submit feedback on Project A's request
    res_b = await client.post(
        "/v1/feedback",
        json={"request_id": req_id, "score": 1},
        headers={"Authorization": f"Bearer {raw_key_b}"},
    )
    assert res_b.status_code == 404
    err = res_b.json()
    assert "error" in err
    assert err["error"]["code"] == "request_not_found"

    # Verify score was NOT altered
    async with session_factory() as session:
        log = (
            await session.execute(select(RequestLog).where(RequestLog.id == uuid.UUID(req_id)))
        ).scalar_one()
        assert log.feedback_score is None


@pytest.mark.asyncio
async def test_feedback_invalid_score_and_nonexistent_request(
    feedback_setup: tuple[
        AsyncClient, FastAPI, async_sessionmaker[AsyncSession], Project, str, Project, str
    ],
) -> None:
    """Test score validation and nonexistent request handling."""
    client, _, _, _, raw_key_a, _, _ = feedback_setup

    # Invalid score 0 or 5
    res_invalid = await client.post(
        "/v1/feedback",
        json={"request_id": str(uuid7()), "score": 0},
        headers={"Authorization": f"Bearer {raw_key_a}"},
    )
    assert res_invalid.status_code == 400 or res_invalid.status_code == 422

    # Non-existent request returns 404
    random_id = str(uuid7())
    res_404 = await client.post(
        "/v1/feedback",
        json={"request_id": random_id, "score": 1},
        headers={"Authorization": f"Bearer {raw_key_a}"},
    )
    assert res_404.status_code == 404


@pytest.mark.asyncio
async def test_user_tag_header_sanitization(
    feedback_setup: tuple[
        AsyncClient, FastAPI, async_sessionmaker[AsyncSession], Project, str, Project, str
    ],
) -> None:
    """Test X-Gateway-User header extraction and sanitization."""
    client, _, session_factory, proj_a, raw_key_a, _, _ = feedback_setup

    # Valid user tag
    res1 = await client.post(
        "/v1/chat/completions",
        json={
            "model": "mock/mock-model",
            "messages": [{"role": "user", "content": "User tag test"}],
        },
        headers={
            "Authorization": f"Bearer {raw_key_a}",
            "X-Gateway-User": "user_alice-123@work.org",
        },
    )
    assert res1.status_code == 200
    req_id1 = res1.headers["x-gateway-request-id"]

    # Tag with invalid characters to be sanitized
    res2 = await client.post(
        "/v1/chat/completions",
        json={
            "model": "mock/mock-model",
            "messages": [{"role": "user", "content": "Sanitize tag test"}],
        },
        headers={"Authorization": f"Bearer {raw_key_a}", "X-Gateway-User": "user<script>!#$bob"},
    )
    assert res2.status_code == 200
    req_id2 = res2.headers["x-gateway-request-id"]

    await request_logger.flush()

    async with session_factory() as session:
        log1 = (
            await session.execute(select(RequestLog).where(RequestLog.id == uuid.UUID(req_id1)))
        ).scalar_one()
        assert log1.user_tag == "user_alice-123@work.org"

        log2 = (
            await session.execute(select(RequestLog).where(RequestLog.id == uuid.UUID(req_id2)))
        ).scalar_one()
        assert log2.user_tag == "userscriptbob"


@pytest.mark.asyncio
async def test_empty_or_truncated_quality_signals(
    feedback_setup: tuple[
        AsyncClient, FastAPI, async_sessionmaker[AsyncSession], Project, str, Project, str
    ],
) -> None:
    """Test empty_or_truncated calculation in request_logger."""
    _, _, session_factory, proj_a, _, _, _ = feedback_setup

    now = datetime.now(UTC)

    # 1. Truncated item (finish_reason = "length")
    item_truncated = RequestLogItem(
        id=uuid7(),
        project_id=proj_a.id,
        gateway_key_id=None,
        created_at=now,
        endpoint="chat",
        provider="mock",
        model_requested="mock/mock-model",
        model_used="mock/mock-model",
        status="ok",
        http_status=200,
        input_tokens=10,
        output_tokens=100,
        finish_reason="length",
        output_content="Partial response...",
    )
    request_logger.log(item_truncated)

    # 2. Empty item (output_content empty or None)
    item_empty = RequestLogItem(
        id=uuid7(),
        project_id=proj_a.id,
        gateway_key_id=None,
        created_at=now,
        endpoint="chat",
        provider="mock",
        model_requested="mock/mock-model",
        model_used="mock/mock-model",
        status="ok",
        http_status=200,
        input_tokens=10,
        output_tokens=0,
        finish_reason="stop",
        output_content="",
    )
    request_logger.log(item_empty)

    # 3. Normal complete item
    item_normal = RequestLogItem(
        id=uuid7(),
        project_id=proj_a.id,
        gateway_key_id=None,
        created_at=now,
        endpoint="chat",
        provider="mock",
        model_requested="mock/mock-model",
        model_used="mock/mock-model",
        status="ok",
        http_status=200,
        input_tokens=10,
        output_tokens=50,
        finish_reason="stop",
        output_content="Full complete response.",
    )
    request_logger.log(item_normal)

    await request_logger.flush()

    async with session_factory() as session:
        log_trunc = (
            await session.execute(select(RequestLog).where(RequestLog.id == item_truncated.id))
        ).scalar_one()
        assert log_trunc.empty_or_truncated is True

        log_empty = (
            await session.execute(select(RequestLog).where(RequestLog.id == item_empty.id))
        ).scalar_one()
        assert log_empty.empty_or_truncated is True

        log_normal = (
            await session.execute(select(RequestLog).where(RequestLog.id == item_normal.id))
        ).scalar_one()
        assert log_normal.empty_or_truncated is False
