import base64
import os
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
from app.services.request_logger import request_logger


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
async def cache_setup() -> AsyncGenerator[
    tuple[AsyncClient, FastAPI, async_sessionmaker[AsyncSession], Project, str, Project, str]
]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Project A with cache enabled
    raw_key_a = "lgw_cachetest_a_1234567890abcdef123456789"
    key_hash_a = hash_key(raw_key_a)
    proj_a_id = uuid7()
    proj_a = Project(id=proj_a_id, name="Cache Project A", slug="cache-project-a")
    cfg_a = ProjectConfig(
        project_id=proj_a_id,
        rpm_limit=100,
        cache_enabled=True,
        cache_ttl_s=3600,
        fallback_chain=[{"provider": "mock", "model": "mock-model"}],
    )
    key_a = GatewayKey(
        id=uuid7(),
        project_id=proj_a_id,
        name="Key A",
        prefix=raw_key_a[:8],
        key_hash=key_hash_a,
    )

    # Project B with cache enabled (to test Security Test 7 isolation)
    raw_key_b = "lgw_cachetest_b_1234567890abcdef123456789"
    key_hash_b = hash_key(raw_key_b)
    proj_b_id = uuid7()
    proj_b = Project(id=proj_b_id, name="Cache Project B", slug="cache-project-b")
    cfg_b = ProjectConfig(
        project_id=proj_b_id,
        rpm_limit=100,
        cache_enabled=True,
        cache_ttl_s=3600,
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
async def test_repeat_call_served_from_cache(
    cache_setup: tuple[
        AsyncClient, FastAPI, async_sessionmaker[AsyncSession], Project, str, Project, str
    ],
) -> None:
    """Test that second call returns from cache with hit header and saved_micro_usd."""
    client, _, session_factory, proj_a, raw_key_a, _, _ = cache_setup

    payload = {
        "model": "mock/mock-model",
        "messages": [{"role": "user", "content": "What is the capital of France?"}],
    }
    headers = {"Authorization": f"Bearer {raw_key_a}"}

    # 1. First call -> Cache MISS
    res1 = await client.post("/v1/chat/completions", json=payload, headers=headers)
    assert res1.status_code == 200
    assert res1.headers["x-gateway-cache"] == "miss"
    data1 = res1.json()

    # 2. Second call -> Cache HIT
    res2 = await client.post("/v1/chat/completions", json=payload, headers=headers)
    assert res2.status_code == 200
    assert res2.headers["x-gateway-cache"] == "hit"
    data2 = res2.json()

    # Both answers identical
    assert data1["choices"][0]["message"]["content"] == data2["choices"][0]["message"]["content"]

    await request_logger.flush()

    async with session_factory() as session:
        stmt = (
            select(RequestLog)
            .where(RequestLog.project_id == proj_a.id)
            .order_by(RequestLog.created_at.asc())
        )
        logs = (await session.execute(stmt)).scalars().all()
        assert len(logs) == 2

        # Log 1: Miss, cost recorded, saved=0
        log_miss = logs[0]
        assert log_miss.cache_hit is False
        assert log_miss.cost_micro_usd is not None and log_miss.cost_micro_usd > 0
        assert log_miss.saved_micro_usd == 0

        # Log 2: Hit, cost=0, saved_micro_usd > 0, provider tokens=0
        log_hit = logs[1]
        assert log_hit.cache_hit is True
        assert log_hit.cost_micro_usd == 0
        assert log_hit.saved_micro_usd == log_miss.cost_micro_usd
        assert log_hit.input_tokens == 0
        assert log_hit.output_tokens == 0


@pytest.mark.asyncio
async def test_cache_bypass_header(
    cache_setup: tuple[
        AsyncClient, FastAPI, async_sessionmaker[AsyncSession], Project, str, Project, str
    ],
) -> None:
    """Test that X-Gateway-Cache: bypass header forces cache bypass."""
    client, _, _, _, raw_key_a, _, _ = cache_setup

    payload = {
        "model": "mock/mock-model",
        "messages": [{"role": "user", "content": "Bypass test prompt"}],
    }

    # 1. Warm cache
    res1 = await client.post(
        "/v1/chat/completions",
        json=payload,
        headers={"Authorization": f"Bearer {raw_key_a}"},
    )
    assert res1.headers["x-gateway-cache"] == "miss"

    # 2. Call with bypass
    res2 = await client.post(
        "/v1/chat/completions",
        json=payload,
        headers={"Authorization": f"Bearer {raw_key_a}", "X-Gateway-Cache": "bypass"},
    )
    assert res2.headers["x-gateway-cache"] == "bypass"

    # 3. Call without bypass -> should hit cache
    res3 = await client.post(
        "/v1/chat/completions",
        json=payload,
        headers={"Authorization": f"Bearer {raw_key_a}"},
    )
    assert res3.headers["x-gateway-cache"] == "hit"


@pytest.mark.asyncio
async def test_streaming_cache_replay(
    cache_setup: tuple[
        AsyncClient, FastAPI, async_sessionmaker[AsyncSession], Project, str, Project, str
    ],
) -> None:
    """Test streaming call is cached and replayed as an SSE stream on subsequent request."""
    client, _, session_factory, proj_a, raw_key_a, _, _ = cache_setup

    payload = {
        "model": "mock/mock-model",
        "messages": [{"role": "user", "content": "Stream replay test"}],
        "stream": True,
    }
    headers = {"Authorization": f"Bearer {raw_key_a}"}

    # 1. First streaming call -> MISS
    res1 = await client.post("/v1/chat/completions", json=payload, headers=headers)
    assert res1.status_code == 200
    assert res1.headers["x-gateway-cache"] == "miss"

    # Wait for logger flush
    await request_logger.flush()

    # 2. Second streaming call -> HIT (replayed stream)
    res2 = await client.post("/v1/chat/completions", json=payload, headers=headers)
    assert res2.status_code == 200
    assert res2.headers["x-gateway-cache"] == "hit"

    lines = res2.text.strip().split("\n\n")
    events = [ev for ev in lines if ev.startswith("data: ") and ev != "data: [DONE]"]
    assert len(events) >= 2  # Role chunk + content chunk + finish chunk
    assert "data: [DONE]" in res2.text

    await request_logger.flush()

    async with session_factory() as session:
        stmt = (
            select(RequestLog)
            .where(RequestLog.project_id == proj_a.id)
            .order_by(RequestLog.created_at.asc())
        )
        logs = (await session.execute(stmt)).scalars().all()
        assert len(logs) == 2
        assert logs[1].cache_hit is True
        assert logs[1].streamed is True
        assert logs[1].saved_micro_usd > 0


@pytest.mark.asyncio
async def test_embeddings_caching(
    cache_setup: tuple[
        AsyncClient, FastAPI, async_sessionmaker[AsyncSession], Project, str, Project, str
    ],
) -> None:
    """Test embeddings endpoint caching and savings recording."""
    client, _, session_factory, proj_a, raw_key_a, _, _ = cache_setup

    payload = {
        "model": "mock/mock-model",
        "input": "Embedding cache test string",
    }
    headers = {"Authorization": f"Bearer {raw_key_a}"}

    # 1. First call -> MISS
    res1 = await client.post("/v1/embeddings", json=payload, headers=headers)
    assert res1.status_code == 200
    assert res1.headers["x-gateway-cache"] == "miss"

    # 2. Second call -> HIT
    res2 = await client.post("/v1/embeddings", json=payload, headers=headers)
    assert res2.status_code == 200
    assert res2.headers["x-gateway-cache"] == "hit"

    data1 = res1.json()
    data2 = res2.json()
    assert data1["data"][0]["embedding"] == data2["data"][0]["embedding"]

    await request_logger.flush()

    async with session_factory() as session:
        stmt = (
            select(RequestLog)
            .where(RequestLog.project_id == proj_a.id, RequestLog.endpoint == "embeddings")
            .order_by(RequestLog.created_at.asc())
        )
        logs = (await session.execute(stmt)).scalars().all()
        assert len(logs) == 2
        assert logs[0].cache_hit is False
        assert logs[1].cache_hit is True
        assert logs[1].saved_micro_usd > 0


@pytest.mark.asyncio
async def test_security_7_cache_isolation_between_projects(
    cache_setup: tuple[
        AsyncClient, FastAPI, async_sessionmaker[AsyncSession], Project, str, Project, str
    ],
) -> None:
    """Security Test 7: Cache isolation - same request in two projects never shares an entry."""
    client, _, _, proj_a, raw_key_a, proj_b, raw_key_b = cache_setup

    identical_payload = {
        "model": "mock/mock-model",
        "messages": [{"role": "user", "content": "Security Test 7 isolation payload"}],
    }

    # 1. Project A calls and warms its cache
    res_a1 = await client.post(
        "/v1/chat/completions",
        json=identical_payload,
        headers={"Authorization": f"Bearer {raw_key_a}"},
    )
    assert res_a1.status_code == 200
    assert res_a1.headers["x-gateway-cache"] == "miss"

    # 2. Project A calls again -> HIT
    res_a2 = await client.post(
        "/v1/chat/completions",
        json=identical_payload,
        headers={"Authorization": f"Bearer {raw_key_a}"},
    )
    assert res_a2.status_code == 200
    assert res_a2.headers["x-gateway-cache"] == "hit"

    # 3. Project B sends THE EXACT SAME REQUEST!
    # MUST BE A MISS! MUST NOT access Project A's cached entry!
    res_b = await client.post(
        "/v1/chat/completions",
        json=identical_payload,
        headers={"Authorization": f"Bearer {raw_key_b}"},
    )
    assert res_b.status_code == 200
    assert res_b.headers["x-gateway-cache"] == "miss"
