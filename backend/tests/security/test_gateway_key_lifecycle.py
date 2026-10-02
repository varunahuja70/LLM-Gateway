import base64
import os
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.admin.auth import reset_rate_limits
from app.db.base import Base
from app.db.models.project import GatewayKey, Project
from app.db.session import get_db_session
from app.deps import clear_gateway_key_memory_cache, require_gateway_key
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

    # Add a mock gateway endpoint to test require_gateway_key dependency
    @app.get("/v1/test-auth")
    async def mock_gateway_call(
        auth_data: tuple[Project, GatewayKey] = Depends(require_gateway_key),
    ) -> dict[str, str]:
        project, key = auth_data
        return {"project_id": str(project.id), "key_id": str(key.id)}

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://localhost:3000"
    ) as client:
        yield client, app, session_factory

    await engine.dispose()


async def _setup_owner_and_login(client: AsyncClient) -> str:
    """Helper to bootstrap owner and return CSRF token."""
    res = await client.post(
        "/admin/setup",
        json={"email": "owner@example.com", "password": "CorrectHorseBatteryStaple123!"},
    )
    assert res.status_code == 200
    return str(res.json()["csrf_token"])


@pytest.mark.asyncio
async def test_key_lifecycle_create_show_once_and_list(
    app_and_client: tuple[AsyncClient, FastAPI, async_sessionmaker[AsyncSession]],
) -> None:
    client, _, _ = app_and_client
    csrf_token = await _setup_owner_and_login(client)

    # 1. Create project
    proj_res = await client.post(
        "/admin/projects",
        json={"name": "Production App", "description": "Main API"},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert proj_res.status_code == 200
    project_id = proj_res.json()["id"]

    # 2. Create gateway key
    key_res = await client.post(
        f"/admin/projects/{project_id}/keys",
        json={"name": "Backend Service Key"},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert key_res.status_code == 200
    key_data = key_res.json()
    assert "raw_key" in key_data
    raw_key = key_data["raw_key"]
    assert raw_key.startswith("lgw_")
    assert len(raw_key) >= 40
    assert key_data["prefix"] == raw_key[:8]

    # 3. List keys - raw_key and key_hash MUST NEVER be present
    list_res = await client.get(f"/admin/projects/{project_id}/keys")
    assert list_res.status_code == 200
    keys_list = list_res.json()
    assert len(keys_list) == 1
    item = keys_list[0]
    assert item["prefix"] == key_data["prefix"]
    assert item["name"] == "Backend Service Key"
    assert "raw_key" not in item
    assert "key_hash" not in item


@pytest.mark.asyncio
async def test_security_test_1_gateway_key_auth_verification(
    app_and_client: tuple[AsyncClient, FastAPI, async_sessionmaker[AsyncSession]],
) -> None:
    """Security Test 1: missing key, malformed key, revoked key, expired key,

    key of another project all fail correctly.
    """
    client, _, _ = app_and_client
    csrf_token = await _setup_owner_and_login(client)

    # Setup project 1 and key
    p1_res = await client.post(
        "/admin/projects",
        json={"name": "Project Alpha"},
        headers={"X-CSRF-Token": csrf_token},
    )
    p1_id = p1_res.json()["id"]

    k1_res = await client.post(
        f"/admin/projects/{p1_id}/keys",
        json={"name": "Alpha Key"},
        headers={"X-CSRF-Token": csrf_token},
    )
    raw_k1 = k1_res.json()["raw_key"]
    k1_id = k1_res.json()["id"]

    # 1. Missing Authorization header -> 401
    missing_res = await client.get("/v1/test-auth")
    assert missing_res.status_code == 401
    assert missing_res.json()["error"]["code"] == "invalid_api_key"

    # 2. Malformed key format (not lgw_) -> 401
    malformed_res = await client.get(
        "/v1/test-auth", headers={"Authorization": "Bearer sk-someopenaiheader123"}
    )
    assert malformed_res.status_code == 401

    # 3. Valid key works
    valid_res = await client.get("/v1/test-auth", headers={"Authorization": f"Bearer {raw_k1}"})
    assert valid_res.status_code == 200
    assert valid_res.json()["project_id"] == p1_id
    assert valid_res.json()["key_id"] == k1_id

    # 4. Immediate revocation: revoked key MUST fail immediately
    revoke_res = await client.post(
        f"/admin/keys/{k1_id}/revoke", headers={"X-CSRF-Token": csrf_token}
    )
    assert revoke_res.status_code == 200

    revoked_call = await client.get("/v1/test-auth", headers={"Authorization": f"Bearer {raw_k1}"})
    assert revoked_call.status_code == 401
    assert "revoked" in revoked_call.json()["error"]["message"]


@pytest.mark.asyncio
async def test_key_rotation_immediately_invalidates_old_and_activates_new(
    app_and_client: tuple[AsyncClient, FastAPI, async_sessionmaker[AsyncSession]],
) -> None:
    client, _, _ = app_and_client
    csrf_token = await _setup_owner_and_login(client)

    p_res = await client.post(
        "/admin/projects",
        json={"name": "Rotation App"},
        headers={"X-CSRF-Token": csrf_token},
    )
    pid = p_res.json()["id"]

    k_res = await client.post(
        f"/admin/projects/{pid}/keys",
        json={"name": "Rotating Key"},
        headers={"X-CSRF-Token": csrf_token},
    )
    old_raw = k_res.json()["raw_key"]
    old_id = k_res.json()["id"]

    # Verify old key works
    ok1 = await client.get("/v1/test-auth", headers={"Authorization": f"Bearer {old_raw}"})
    assert ok1.status_code == 200

    # Rotate key
    rotate_res = await client.post(
        f"/admin/keys/{old_id}/rotate", headers={"X-CSRF-Token": csrf_token}
    )
    assert rotate_res.status_code == 200
    new_raw = rotate_res.json()["raw_key"]
    assert new_raw != old_raw

    # Old key fails immediately
    old_fail = await client.get("/v1/test-auth", headers={"Authorization": f"Bearer {old_raw}"})
    assert old_fail.status_code == 401

    # New key works immediately
    new_ok = await client.get("/v1/test-auth", headers={"Authorization": f"Bearer {new_raw}"})
    assert new_ok.status_code == 200


@pytest.mark.asyncio
async def test_expired_key_and_archived_project_rejected(
    app_and_client: tuple[AsyncClient, FastAPI, async_sessionmaker[AsyncSession]],
) -> None:
    client, _, _ = app_and_client
    csrf_token = await _setup_owner_and_login(client)

    # Project with expired key
    p_res = await client.post(
        "/admin/projects",
        json={"name": "Expired Key App"},
        headers={"X-CSRF-Token": csrf_token},
    )
    pid = p_res.json()["id"]

    # Key expired 1 hour ago
    past_time = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    exp_key_res = await client.post(
        f"/admin/projects/{pid}/keys",
        json={"name": "Past Key", "expires_at": past_time},
        headers={"X-CSRF-Token": csrf_token},
    )
    exp_raw = exp_key_res.json()["raw_key"]

    exp_call = await client.get("/v1/test-auth", headers={"Authorization": f"Bearer {exp_raw}"})
    assert exp_call.status_code == 401
    assert "expired" in exp_call.json()["error"]["message"]

    # Create a fresh valid key
    valid_key_res = await client.post(
        f"/admin/projects/{pid}/keys",
        json={"name": "Fresh Key"},
        headers={"X-CSRF-Token": csrf_token},
    )
    fresh_raw = valid_key_res.json()["raw_key"]
    fresh_call = await client.get("/v1/test-auth", headers={"Authorization": f"Bearer {fresh_raw}"})
    assert fresh_call.status_code == 200

    # Archive project -> fresh key MUST now be rejected
    arch_res = await client.delete(f"/admin/projects/{pid}", headers={"X-CSRF-Token": csrf_token})
    assert arch_res.status_code == 200

    arch_call = await client.get("/v1/test-auth", headers={"Authorization": f"Bearer {fresh_raw}"})
    assert arch_call.status_code == 401
