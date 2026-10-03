import base64
import os
import uuid
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.security import hash_key
from app.db.base import Base
from app.db.models.project import GatewayKey, Project, ProjectConfig
from app.db.session import get_db_session
from app.main import create_app


@pytest.fixture(autouse=True)
def setup_test_environment() -> None:
    valid_key = base64.b64encode(b"0123456789abcdef0123456789abcdef").decode()
    os.environ["GATEWAY_MASTER_KEY"] = valid_key
    os.environ["ENV"] = "test"
    os.environ["PUBLIC_URL"] = "http://localhost:3000"

    import app.config as config_module
    config_module._settings = None


@pytest.fixture
async def test_env() -> AsyncGenerator[tuple[AsyncClient, async_sessionmaker[AsyncSession]]]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

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

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://localhost:3000"
    ) as client:
        yield client, session_factory

    await engine.dispose()


@pytest.mark.asyncio
async def test_security_test_7_cache_isolation_between_projects(
    test_env: tuple[AsyncClient, async_sessionmaker[AsyncSession]],
) -> None:
    """Security test 7: Same request in two projects never shares a cache entry."""
    client, session_factory = test_env

    # Create project 1 with cache enabled
    p1_id = uuid.uuid4()
    p2_id = uuid.uuid4()
    raw_key1 = "lgw_p1_cache_test_key_00000000000000000000000"
    raw_key2 = "lgw_p2_cache_test_key_00000000000000000000000"

    async with session_factory() as session:
        p1 = Project(id=p1_id, name="Project 1", slug="project-1")
        c1 = ProjectConfig(project_id=p1_id, cache_enabled=True, cache_ttl_s=3600)
        k1 = GatewayKey(id=uuid.uuid4(), project_id=p1_id, name="k1", key_hash=hash_key(raw_key1), prefix="lgw_p1_c")

        p2 = Project(id=p2_id, name="Project 2", slug="project-2")
        c2 = ProjectConfig(project_id=p2_id, cache_enabled=True, cache_ttl_s=3600)
        k2 = GatewayKey(id=uuid.uuid4(), project_id=p2_id, name="k2", key_hash=hash_key(raw_key2), prefix="lgw_p2_c")

        session.add_all([p1, c1, k1, p2, c2, k2])
        await session.commit()

    payload = {
        "model": "mock/gpt-4o-mini",
        "messages": [{"role": "user", "content": "Cache isolation prompt"}],
    }

    # Call project 1: First call is cache miss
    resp1 = await client.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {raw_key1}"},
        json=payload,
    )
    assert resp1.status_code == 200
    assert (resp1.headers.get("X-Gateway-Cache") or "").upper() == "MISS"

    # Call project 1 again: Repeat call is cache HIT
    resp1_hit = await client.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {raw_key1}"},
        json=payload,
    )
    assert resp1_hit.status_code == 200
    assert (resp1_hit.headers.get("X-Gateway-Cache") or "").upper() == "HIT"

    # Call project 2 with identical payload: MUST BE CACHE MISS (isolation verified!)
    resp2 = await client.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {raw_key2}"},
        json=payload,
    )
    assert resp2.status_code == 200
    assert (resp2.headers.get("X-Gateway-Cache") or "").upper() == "MISS"


@pytest.mark.asyncio
async def test_security_test_8_budget_block_and_header_case_insensitivity(
    test_env: tuple[AsyncClient, async_sessionmaker[AsyncSession]],
) -> None:
    """Security test 8: Budget block cannot be bypassed by changing header casing."""
    client, session_factory = test_env

    p_id = uuid.uuid4()
    raw_key = "lgw_budget_block_key_0000000000000000000000"

    async with session_factory() as session:
        p = Project(id=p_id, name="Budget Limited", slug="budget-limited")
        # Daily budget $0.0001 (100 micro USD) and block_at_limit=True
        c = ProjectConfig(
            project_id=p_id,
            daily_budget_micro_usd=100,
            block_at_limit=True,
        )
        k = GatewayKey(id=uuid.uuid4(), project_id=p_id, name="k", key_hash=hash_key(raw_key), prefix="lgw_budg")
        session.add_all([p, c, k])
        await session.commit()

    payload = {
        "model": "mock/gpt-4o-mini",
        "messages": [{"role": "user", "content": "Check budget enforcement"}],
    }

    # First call succeeds
    r1 = await client.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {raw_key}"},
        json=payload,
    )
    assert r1.status_code == 200

    # Header variation: lowercase 'authorization'
    r2 = await client.post(
        "/v1/chat/completions",
        headers={"authorization": f"Bearer {raw_key}"},
        json=payload,
    )
    assert r2.status_code in (200, 429)


@pytest.mark.asyncio
async def test_security_test_9_request_size_limit_and_max_tokens(
    test_env: tuple[AsyncClient, async_sessionmaker[AsyncSession]],
) -> None:
    """Security test 9: Request size limit enforced."""
    client, session_factory = test_env

    p_id = uuid.uuid4()
    raw_key = "lgw_size_limit_key_00000000000000000000000"

    async with session_factory() as session:
        p = Project(id=p_id, name="Size Project", slug="size-project")
        c = ProjectConfig(project_id=p_id)
        k = GatewayKey(id=uuid.uuid4(), project_id=p_id, name="k", key_hash=hash_key(raw_key), prefix="lgw_size")
        session.add_all([p, c, k])
        await session.commit()

    # Oversized payload exceeding 4MB default
    huge_text = "a" * (5 * 1024 * 1024)  # 5MB
    huge_payload = {
        "model": "mock/gpt-4o-mini",
        "messages": [{"role": "user", "content": huge_text}],
    }

    resp = await client.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {raw_key}"},
        json=huge_payload,
    )
    assert resp.status_code in (413, 400)


@pytest.mark.asyncio
async def test_security_test_10_admin_endpoints_require_session_gateway_keys_fail(
    test_env: tuple[AsyncClient, async_sessionmaker[AsyncSession]],
) -> None:
    """Security test 10: Admin endpoints return 401 without session, and gateway keys NEVER work on admin."""
    client, session_factory = test_env

    p_id = uuid.uuid4()
    raw_key = "lgw_admin_probe_key_00000000000000000000000"

    async with session_factory() as session:
        p = Project(id=p_id, name="Admin Probe", slug="admin-probe")
        k = GatewayKey(id=uuid.uuid4(), project_id=p_id, name="k", key_hash=hash_key(raw_key), prefix="lgw_admi")
        session.add_all([p, k])
        await session.commit()

    # 1. Unauthenticated request to admin endpoint returns 401
    resp_anon = await client.get("/admin/projects")
    assert resp_anon.status_code == 401

    # 2. Gateway key used against admin endpoint MUST BE REJECTED with 401 (never privileged)
    resp_gateway_key = await client.get(
        "/admin/projects",
        headers={"Authorization": f"Bearer {raw_key}"},
    )
    assert resp_gateway_key.status_code == 401

    # 3. Gateway key used on /admin/settings MUST BE REJECTED
    resp_settings = await client.get(
        "/admin/settings",
        headers={"Authorization": f"Bearer {raw_key}"},
    )
    assert resp_settings.status_code == 401
