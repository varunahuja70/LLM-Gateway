import base64
import json
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
    clear_gateway_key_memory_cache()


@pytest.fixture
async def fallback_setup() -> AsyncGenerator[
    tuple[AsyncClient, FastAPI, async_sessionmaker[AsyncSession], Project, str]
]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    raw_key = "lgw_fallbacktest1234567890abcdef1234567890abc"
    key_hash = hash_key(raw_key)

    project_id = uuid7()
    project = Project(
        id=project_id,
        name="Fallback Test Project",
        slug="fallback-test-project",
    )

    config = ProjectConfig(
        project_id=project_id,
        rpm_limit=100,
        max_fallbacks=2,
        fallback_chain=[
            {"provider": "mock", "model": "mock-primary"},
            {"provider": "mock", "model": "mock-backup"},
            {"provider": "mock", "model": "mock-tertiary"},
        ],
    )
    key = GatewayKey(
        id=uuid7(),
        project_id=project_id,
        name="Fallback Key",
        prefix=raw_key[:8],
        key_hash=key_hash,
    )
    price_primary = ModelPrice(
        id=uuid7(),
        provider="mock",
        model="mock-primary",
        input_micro_usd_per_mtok=1_000_000,
        output_micro_usd_per_mtok=2_000_000,
        source_url="https://example.com/pricing",
        verified_on=datetime.now(UTC).date(),
        is_seed=True,
    )
    price_backup = ModelPrice(
        id=uuid7(),
        provider="mock",
        model="mock-backup",
        input_micro_usd_per_mtok=1_500_000,
        output_micro_usd_per_mtok=3_000_000,
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
        session.add(price_primary)
        session.add(price_backup)
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
        yield client, app, session_factory, project, raw_key

    await engine.dispose()


@pytest.mark.asyncio
async def test_fallback_on_500_error(
    fallback_setup: tuple[AsyncClient, FastAPI, async_sessionmaker[AsyncSession], Project, str],
) -> None:
    """Test that 500 error triggers fallback to next model and logs properly."""
    client, _, session_factory, project, raw_key = fallback_setup

    headers = {
        "Authorization": f"Bearer {raw_key}",
        "X-Mock-Fail": "500",
        "X-Mock-Fail-Model": "mock-primary",
    }
    payload = {
        "model": "mock/mock-primary",
        "messages": [{"role": "user", "content": "Hello fallback"}],
    }

    res = await client.post("/v1/chat/completions", json=payload, headers=headers)
    assert res.status_code == 200
    assert res.headers["x-gateway-fallback"] == "mock/mock-primary"
    assert res.headers["x-gateway-model-used"] == "mock/mock-backup"

    data = res.json()
    assert "choices" in data
    assert len(data["choices"]) > 0

    # Wait for logger flush
    await request_logger.flush()

    async with session_factory() as session:
        log_stmt = select(RequestLog).where(RequestLog.project_id == project.id)
        logs = (await session.execute(log_stmt)).scalars().all()
        assert len(logs) == 1
        log = logs[0]
        assert log.status == "ok"
        assert log.fallback_used is True
        assert log.fallback_from == "mock/mock-primary"
        assert log.model_used == "mock/mock-backup"
        assert log.fallback_reason is not None


@pytest.mark.asyncio
async def test_fallback_on_429_and_timeout(
    fallback_setup: tuple[AsyncClient, FastAPI, async_sessionmaker[AsyncSession], Project, str],
) -> None:
    """Test that 429 and timeout errors trigger fallback."""
    client, _, _, _, raw_key = fallback_setup

    # Test 429 rate limit fallback
    res_429 = await client.post(
        "/v1/chat/completions",
        json={
            "model": "mock/mock-primary",
            "messages": [{"role": "user", "content": "Rate limit test"}],
        },
        headers={
            "Authorization": f"Bearer {raw_key}",
            "X-Mock-Fail": "429",
            "X-Mock-Fail-Model": "mock-primary",
        },
    )
    assert res_429.status_code == 200
    assert res_429.headers["x-gateway-fallback"] == "mock/mock-primary"
    assert res_429.headers["x-gateway-model-used"] == "mock/mock-backup"

    # Test Timeout fallback
    res_timeout = await client.post(
        "/v1/chat/completions",
        json={
            "model": "mock/mock-primary",
            "messages": [{"role": "user", "content": "Timeout test"}],
        },
        headers={
            "Authorization": f"Bearer {raw_key}",
            "X-Mock-Fail": "timeout",
            "X-Mock-Fail-Model": "mock-primary",
        },
    )
    assert res_timeout.status_code == 200
    assert res_timeout.headers["x-gateway-fallback"] == "mock/mock-primary"
    assert res_timeout.headers["x-gateway-model-used"] == "mock/mock-backup"


@pytest.mark.asyncio
async def test_400_bad_request_does_not_fallback(
    fallback_setup: tuple[AsyncClient, FastAPI, async_sessionmaker[AsyncSession], Project, str],
) -> None:
    """Test that 400 Bad Request error does NOT trigger fallback."""
    client, _, session_factory, project, raw_key = fallback_setup

    headers = {
        "Authorization": f"Bearer {raw_key}",
        "X-Mock-Fail": "400",
        "X-Mock-Fail-Model": "mock-primary",
    }
    payload = {
        "model": "mock/mock-primary",
        "messages": [{"role": "user", "content": "Bad request test"}],
    }

    res = await client.post("/v1/chat/completions", json=payload, headers=headers)
    assert res.status_code == 400
    assert res.headers["x-gateway-fallback"] == "none"

    data = res.json()
    assert "error" in data
    assert data["error"]["message"] == "Mock provider simulated 400 bad request."

    await request_logger.flush()
    async with session_factory() as session:
        log_stmt = select(RequestLog).where(
            RequestLog.project_id == project.id, RequestLog.status == "error"
        )
        logs = (await session.execute(log_stmt)).scalars().all()
        assert len(logs) >= 1
        assert logs[-1].fallback_used is False


@pytest.mark.asyncio
async def test_streaming_fallback_before_first_byte(
    fallback_setup: tuple[AsyncClient, FastAPI, async_sessionmaker[AsyncSession], Project, str],
) -> None:
    """Test streaming fallback works when primary fails before first byte."""
    client, _, _, _, raw_key = fallback_setup

    headers = {
        "Authorization": f"Bearer {raw_key}",
        "X-Mock-Fail": "500",
        "X-Mock-Fail-Model": "mock-primary",
    }
    payload = {
        "model": "mock/mock-primary",
        "messages": [{"role": "user", "content": "Stream fallback test"}],
        "stream": True,
    }

    res = await client.post("/v1/chat/completions", json=payload, headers=headers)
    assert res.status_code == 200
    assert res.headers["x-gateway-fallback"] == "mock/mock-primary"
    assert res.headers["x-gateway-model-used"] == "mock/mock-backup"

    lines = res.text.strip().split("\n\n")
    events = [ev for ev in lines if ev.startswith("data: ") and ev != "data: [DONE]"]
    assert len(events) > 0
    first_data = json.loads(events[0][6:])
    assert first_data["model"] == "mock-backup"


@pytest.mark.asyncio
async def test_streaming_no_fallback_after_first_byte(
    fallback_setup: tuple[AsyncClient, FastAPI, async_sessionmaker[AsyncSession], Project, str],
) -> None:
    """Test that once first byte is sent, no fallback occurs on mid-stream failure."""
    client, _, session_factory, project, raw_key = fallback_setup

    headers = {
        "Authorization": f"Bearer {raw_key}",
        "x-mock-fail-after-chunks": "1",
    }
    payload = {
        "model": "mock/mock-primary",
        "messages": [{"role": "user", "content": "Mid stream failure"}],
        "stream": True,
    }

    res = await client.post("/v1/chat/completions", json=payload, headers=headers)
    assert res.status_code == 200
    # Before stream error, primary was chosen, so fallback is none
    assert res.headers["x-gateway-fallback"] == "none"

    text = res.text
    # Stream interrupted: ends with error payload, no fallback
    assert "error" in text
    assert "[DONE]" in text

    await request_logger.flush()
    async with session_factory() as session:
        log_stmt = select(RequestLog).where(
            RequestLog.project_id == project.id, RequestLog.status == "error"
        )
        logs = (await session.execute(log_stmt)).scalars().all()
        assert len(logs) >= 1
        assert logs[-1].fallback_used is False


@pytest.mark.asyncio
async def test_embeddings_fallback_same_provider_only(
    fallback_setup: tuple[AsyncClient, FastAPI, async_sessionmaker[AsyncSession], Project, str],
) -> None:
    """Test embeddings fallback works within same provider and excludes cross-provider models."""
    client, _, session_factory, project, raw_key = fallback_setup

    # Configure fallback chain with cross-provider and same-provider models
    async with session_factory() as session:
        cfg = (
            await session.execute(
                select(ProjectConfig).where(ProjectConfig.project_id == project.id)
            )
        ).scalar_one()
        cfg.fallback_chain = [
            {"provider": "mock", "model": "mock-primary"},
            {"provider": "openai", "model": "text-embedding-3-small"},  # Different provider!
            {"provider": "mock", "model": "mock-backup"},  # Same provider!
        ]
        await session.commit()

    headers = {
        "Authorization": f"Bearer {raw_key}",
        "X-Mock-Fail": "500",
        "X-Mock-Fail-Model": "mock-primary",
    }
    payload = {
        "model": "mock/mock-primary",
        "input": "Embedding fallback test string",
    }

    res = await client.post("/v1/embeddings", json=payload, headers=headers)
    assert res.status_code == 200
    assert res.headers["x-gateway-fallback"] == "mock/mock-primary"
    # Succeeded on mock-backup, completely skipped openai/text-embedding-3-small!
    assert res.headers["x-gateway-model-used"] == "mock/mock-backup"

    data = res.json()
    assert data["object"] == "list"
    assert len(data["data"]) == 1
    assert data["model"] == "mock-backup"
