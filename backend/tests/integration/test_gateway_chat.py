import base64
import os
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any, cast

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.admin.auth import reset_rate_limits
from app.core.security import hash_key
from app.db.base import Base, uuid7
from app.db.models.project import GatewayKey, Project, ProjectConfig
from app.db.models.provider import ModelPrice
from app.db.models.request import RequestContent, RequestLog
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
    clear_gateway_key_memory_cache()


@pytest.fixture
async def gateway_setup() -> AsyncGenerator[
    tuple[AsyncClient, FastAPI, async_sessionmaker[AsyncSession], Project, str]
]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Seed Project, ProjectConfig, GatewayKey, and ModelPrice
    raw_key = "lgw_testkey1234567890abcdef1234567890abcdef1"
    key_hash = hash_key(raw_key)

    project_id = uuid7()
    project = Project(
        id=project_id,
        name="Gateway Test Project",
        slug="gateway-test-project",
        description="Testing gateway completions",
    )
    config = ProjectConfig(
        project_id=project_id,
        log_content=True,
        fallback_chain=[{"provider": "mock", "model": "mock-model"}],
    )
    key = GatewayKey(
        id=uuid7(),
        project_id=project_id,
        name="Test Gateway Key",
        prefix=raw_key[:8],
        key_hash=key_hash,
    )
    # Seed price for mock/mock-model ($1.00 input, $2.00 output per Mtok)
    price = ModelPrice(
        id=uuid7(),
        provider="mock",
        model="mock-model",
        input_micro_usd_per_mtok=1_000_000,
        output_micro_usd_per_mtok=2_000_000,
        cached_input_micro_usd_per_mtok=100_000,
        source_url="https://example.com/pricing",
        verified_on=datetime.now(UTC).date(),
        is_seed=True,
    )

    async with session_factory() as session:
        session.add(project)
        session.add(config)
        session.add(key)
        session.add(price)
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
    # Point request_logger session factory to test in-memory DB
    request_logger._sessionmaker = session_factory

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        yield client, app, session_factory, project, raw_key

    await engine.dispose()


@pytest.mark.asyncio
async def test_gateway_chat_non_streaming_success(
    gateway_setup: tuple[AsyncClient, FastAPI, async_sessionmaker[AsyncSession], Project, str],
) -> None:
    client, _, session_factory, project, raw_key = gateway_setup

    payload = {
        "model": "mock/mock-model",
        "messages": [{"role": "user", "content": "Hello, gateway!"}],
        "temperature": 0.7,
        "max_tokens": 100,
    }
    headers = {
        "Authorization": f"Bearer {raw_key}",
        "X-Gateway-User": "test-user-123",
    }

    res = await client.post("/v1/chat/completions", json=payload, headers=headers)
    assert res.status_code == 200

    # 1. Verify standard OpenAI response format
    data = res.json()
    assert data["object"] == "chat.completion"
    assert "id" in data
    assert len(data["choices"]) == 1
    assert data["choices"][0]["message"]["role"] == "assistant"
    assert len(data["choices"][0]["message"]["content"]) > 0
    assert data["usage"]["prompt_tokens"] > 0
    assert data["usage"]["completion_tokens"] > 0

    # 2. Verify response headers
    req_id = res.headers.get("X-Gateway-Request-Id")
    assert req_id is not None
    assert res.headers.get("X-Gateway-Cache") == "miss"
    assert res.headers.get("X-Gateway-Model-Used") == "mock/mock-model"
    assert res.headers.get("X-Gateway-Fallback") == "none"

    # 3. Flush logger and verify request_log record in DB
    await request_logger.flush()

    async with session_factory() as session:
        log_stmt = select(RequestLog).where(RequestLog.project_id == project.id)
        log_res = await session.execute(log_stmt)
        req_log = log_res.scalar_one_or_none()
        assert req_log is not None

        assert str(req_log.id) == req_id
        assert req_log.status == "ok"
        assert req_log.http_status == 200
        assert req_log.endpoint == "chat"
        assert req_log.provider == "mock"
        assert req_log.model_used == "mock/mock-model"
        assert req_log.streamed is False
        assert req_log.user_tag == "test-user-123"
        assert req_log.input_tokens > 0
        assert req_log.output_tokens > 0
        assert req_log.cost_micro_usd is not None
        assert req_log.cost_micro_usd > 0

        # Verify content logged because log_content=True
        content_stmt = select(RequestContent).where(RequestContent.request_id == req_log.id)
        c_res = await session.execute(content_stmt)
        content_row = c_res.scalar_one_or_none()
        assert content_row is not None
        assert content_row.request_json["model"] == "mock/mock-model"
        assert content_row.response_json["id"] == data["id"]


@pytest.mark.asyncio
async def test_gateway_chat_streaming_success(
    gateway_setup: tuple[AsyncClient, FastAPI, async_sessionmaker[AsyncSession], Project, str],
) -> None:
    client, _, session_factory, project, raw_key = gateway_setup

    payload = {
        "model": "mock/mock-model",
        "messages": [{"role": "user", "content": "Stream me a message!"}],
        "stream": True,
    }
    headers = {
        "Authorization": f"Bearer {raw_key}",
    }

    res = await client.post("/v1/chat/completions", json=payload, headers=headers)
    assert res.status_code == 200
    assert "text/event-stream" in res.headers["content-type"]
    assert res.headers.get("X-Gateway-Request-Id") is not None
    assert res.headers.get("X-Gateway-Model-Used") == "mock/mock-model"

    body = res.text
    lines = [line.strip() for line in body.split("\n") if line.strip()]

    # Chunks are prefixed with 'data: '
    assert any(line.startswith("data: {") for line in lines)
    assert lines[-1] == "data: [DONE]"

    # Flush logger and verify streaming record
    await request_logger.flush()

    async with session_factory() as session:
        log_stmt = (
            select(RequestLog)
            .where(RequestLog.project_id == project.id, RequestLog.streamed.is_(True))
            .order_by(RequestLog.created_at.desc())
        )
        log_res = await session.execute(log_stmt)
        req_log = log_res.scalar_one_or_none()
        assert req_log is not None
        assert req_log.streamed is True
        assert req_log.status == "ok"
        assert req_log.ttft_ms is not None
        assert req_log.ttft_ms >= 0
        assert req_log.latency_ms >= req_log.ttft_ms
        assert req_log.cost_micro_usd is not None


@pytest.mark.asyncio
async def test_gateway_models_endpoint(
    gateway_setup: tuple[AsyncClient, FastAPI, async_sessionmaker[AsyncSession], Project, str],
) -> None:
    client, _, _, _, raw_key = gateway_setup

    res = await client.get("/v1/models", headers={"Authorization": f"Bearer {raw_key}"})
    assert res.status_code == 200
    data = res.json()
    assert data["object"] == "list"
    assert len(data["data"]) >= 1

    model_ids = [m["id"] for m in data["data"]]
    assert "mock/mock-model" in model_ids


@pytest.mark.asyncio
async def test_security_test_9_request_size_and_max_tokens_cap(
    gateway_setup: tuple[AsyncClient, FastAPI, async_sessionmaker[AsyncSession], Project, str],
) -> None:
    client, _, _, _, raw_key = gateway_setup
    headers = {"Authorization": f"Bearer {raw_key}"}

    # 1. Content length exceeding 4 MB -> 413
    big_headers = {
        **headers,
        "Content-Length": str(5 * 1024 * 1024),  # 5 MB header
    }
    payload = {
        "model": "mock/mock-model",
        "messages": [{"role": "user", "content": "Hi"}],
    }
    res_large = await client.post("/v1/chat/completions", json=payload, headers=big_headers)
    assert res_large.status_code == 413
    err = res_large.json()["error"]
    assert err["code"] == "request_too_large"
    assert "4 MB" in err["message"]

    # 2. max_tokens exceeding 32768 cap -> 400
    res_cap = await client.post(
        "/v1/chat/completions",
        json={
            "model": "mock/mock-model",
            "messages": [{"role": "user", "content": "Hi"}],
            "max_tokens": 50000,
        },
        headers=headers,
    )
    assert res_cap.status_code == 400
    err_cap = res_cap.json()["error"]
    assert err_cap["code"] == "max_tokens_exceeded"
    assert "32768" in err_cap["message"]


@pytest.mark.asyncio
async def test_cost_calculation_unknown_model_price_is_null_never_zero(
    gateway_setup: tuple[AsyncClient, FastAPI, async_sessionmaker[AsyncSession], Project, str],
) -> None:
    client, _, session_factory, project, raw_key = gateway_setup

    # Call with a model that has no price row in model_price
    payload = {
        "model": "mock/unpriced-custom-model",
        "messages": [{"role": "user", "content": "Unpriced model call"}],
    }
    headers = {"Authorization": f"Bearer {raw_key}"}

    res = await client.post("/v1/chat/completions", json=payload, headers=headers)
    assert res.status_code == 200

    await request_logger.flush()

    async with session_factory() as session:
        log_stmt = (
            select(RequestLog)
            .where(
                RequestLog.project_id == project.id,
                RequestLog.model_used == "mock/unpriced-custom-model",
            )
            .order_by(RequestLog.created_at.desc())
        )
        req_log = (await session.execute(log_stmt)).scalar_one_or_none()
        assert req_log is not None
        # Strict requirement: unknown model price means cost is NULL, NEVER 0
        assert req_log.cost_micro_usd is None


@pytest.mark.asyncio
async def test_official_openai_python_sdk_compatibility(
    gateway_setup: tuple[AsyncClient, FastAPI, async_sessionmaker[AsyncSession], Project, str],
) -> None:
    """Verify that the official OpenAI Python SDK works seamlessly with our gateway."""
    client, _, _, _, raw_key = gateway_setup

    # Initialize official AsyncOpenAI SDK pointing to our gateway
    openai_client = AsyncOpenAI(
        api_key=raw_key,
        base_url="http://testserver/v1",
        http_client=cast(Any, client),
    )

    # 1. Non-streaming chat completion
    completion = await openai_client.chat.completions.create(
        model="mock/mock-model",
        messages=[{"role": "user", "content": "Testing via official SDK"}],
        temperature=0.5,
    )
    assert completion.id.startswith("chatcmpl-") or len(completion.id) > 0
    assert len(completion.choices) == 1
    assert completion.choices[0].message.content is not None
    assert len(completion.choices[0].message.content) > 0
    assert completion.usage is not None
    assert completion.usage.prompt_tokens > 0

    # 2. Streaming chat completion
    stream = await openai_client.chat.completions.create(
        model="mock/mock-model",
        messages=[{"role": "user", "content": "Streaming via official SDK"}],
        stream=True,
    )
    collected_chunks = []
    async for chunk in stream:
        collected_chunks.append(chunk)

    assert len(collected_chunks) > 0
    assert any(
        c.choices[0].delta.content for c in collected_chunks if c.choices and c.choices[0].delta
    )

    # 3. Model listing via SDK
    models = await openai_client.models.list()
    assert len(models.data) > 0
    assert any(m.id == "mock/mock-model" for m in models.data)
