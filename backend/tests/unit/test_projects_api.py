import base64
import os
import uuid
from collections.abc import AsyncGenerator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.admin.auth import reset_rate_limits
from app.core.crypto import decrypt
from app.db.base import Base
from app.db.models.project import ProjectConfig
from app.db.session import get_db_session
from app.deps import clear_gateway_key_memory_cache
from app.main import create_app


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
async def app_and_client() -> AsyncGenerator[
    tuple[AsyncClient, FastAPI, async_sessionmaker[AsyncSession]]
]:
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
        yield client, app, session_factory

    await engine.dispose()


async def _setup_owner_and_login(client: AsyncClient) -> str:
    res = await client.post(
        "/admin/setup",
        json={"email": "owner@example.com", "password": "CorrectHorseBatteryStaple123!"},
    )
    assert res.status_code == 200
    return str(res.json()["csrf_token"])


@pytest.mark.asyncio
async def test_project_crud_and_duplicate_handling(
    app_and_client: tuple[AsyncClient, FastAPI, async_sessionmaker[AsyncSession]],
) -> None:
    client, _, _ = app_and_client
    csrf_token = await _setup_owner_and_login(client)

    # 1. Create project
    create_res = await client.post(
        "/admin/projects",
        json={"name": "Test Project", "description": "For unit test"},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert create_res.status_code == 200
    pdata = create_res.json()
    assert pdata["name"] == "Test Project"
    assert pdata["slug"] == "test-project"
    pid = pdata["id"]

    # 2. Duplicate name rejection
    dup_res = await client.post(
        "/admin/projects",
        json={"name": "Test Project"},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert dup_res.status_code == 409

    # 3. Get project
    get_res = await client.get(f"/admin/projects/{pid}")
    assert get_res.status_code == 200
    assert get_res.json()["name"] == "Test Project"

    # 4. Update project
    patch_res = await client.patch(
        f"/admin/projects/{pid}",
        json={"name": "Renamed Project", "description": "New description"},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["name"] == "Renamed Project"

    # 5. List projects
    list_res = await client.get("/admin/projects")
    assert list_res.status_code == 200
    assert len(list_res.json()) == 1

    # 6. Archive project
    del_res = await client.delete(
        f"/admin/projects/{pid}",
        headers={"X-CSRF-Token": csrf_token},
    )
    assert del_res.status_code == 200

    # Listed without archived returns empty
    list_active = await client.get("/admin/projects")
    assert len(list_active.json()) == 0

    # Listed with include_archived returns it
    list_all = await client.get("/admin/projects?include_archived=true")
    assert len(list_all.json()) == 1
    assert list_all.json()[0]["archived_at"] is not None


@pytest.mark.asyncio
async def test_project_config_crud_and_ssrf_and_encryption(
    app_and_client: tuple[AsyncClient, FastAPI, async_sessionmaker[AsyncSession]],
) -> None:
    client, _, session_factory = app_and_client
    csrf_token = await _setup_owner_and_login(client)

    proj_res = await client.post(
        "/admin/projects",
        json={"name": "Config Project"},
        headers={"X-CSRF-Token": csrf_token},
    )
    pid = proj_res.json()["id"]

    # 1. Default config created automatically
    cfg_res = await client.get(f"/admin/projects/{pid}/config")
    assert cfg_res.status_code == 200
    cfg = cfg_res.json()
    assert cfg["rpm_limit"] == 60
    assert cfg["max_fallbacks"] == 2
    assert cfg["warn_thresholds"] == [50, 80, 100]
    assert cfg["has_webhook_secret"] is False

    # 2. Reject SSRF in webhook URL (e.g. 127.0.0.1 or 169.254.169.254)
    ssrf_res = await client.put(
        f"/admin/projects/{pid}/config",
        json={"webhook_url": "http://127.0.0.1:8080/hook"},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert ssrf_res.status_code == 400
    assert "Invalid webhook URL" in ssrf_res.json()["detail"]

    # 3. Valid update with external HTTPS webhook and secret
    update_res = await client.put(
        f"/admin/projects/{pid}/config",
        json={
            "webhook_url": "https://api.example.com/alerts/webhook",
            "webhook_secret": "my-very-secret-signing-key-1234",
            "daily_budget_micro_usd": 10_000_000,
            "warn_thresholds": [60, 85, 100],
            "rpm_limit": 120,
            "cache_enabled": True,
            "fallback_chain": [{"provider": "anthropic", "model": "claude-haiku-4-5"}],
        },
        headers={"X-CSRF-Token": csrf_token},
    )
    assert update_res.status_code == 200
    updated_cfg = update_res.json()
    assert updated_cfg["rpm_limit"] == 120
    assert updated_cfg["daily_budget_micro_usd"] == 10_000_000
    assert updated_cfg["warn_thresholds"] == [60, 85, 100]
    assert updated_cfg["has_webhook_secret"] is True
    assert updated_cfg["fallback_chain"][0]["provider"] == "anthropic"

    # 4. Verify in DB that webhook secret was encrypted with AES-GCM
    async with session_factory() as session:
        result = await session.execute(
            select(ProjectConfig).where(ProjectConfig.project_id == uuid.UUID(pid))
        )
        row = result.scalar_one()
        assert row.webhook_secret_encrypted is not None
        # Decrypt with row ID as associated data
        decrypted = decrypt(row.webhook_secret_encrypted, associated_data=str(pid))
        assert decrypted == "my-very-secret-signing-key-1234"
