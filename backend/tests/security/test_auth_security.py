import base64
import os
from collections.abc import AsyncGenerator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.session import get_db_session
from app.main import create_app


@pytest.fixture(autouse=True)
def setup_test_environment() -> None:
    valid_key = base64.b64encode(b"0123456789abcdef0123456789abcdef").decode()
    os.environ["GATEWAY_MASTER_KEY"] = valid_key
    os.environ["ENV"] = "test"
    os.environ["PUBLIC_URL"] = "http://localhost:3000"

    import app.config as config_module
    from app.api.admin.auth import reset_rate_limits

    config_module._settings = None
    reset_rate_limits()


@pytest.fixture
async def test_app_and_client() -> AsyncGenerator[tuple[AsyncClient, FastAPI]]:
    # In-memory test SQLite DB
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
        yield client, app

    await engine.dispose()


@pytest.mark.asyncio
async def test_security_test_5_setup_endpoint_returns_404_after_first_owner(
    test_app_and_client: tuple[AsyncClient, FastAPI],
) -> None:
    client, _ = test_app_and_client

    # 1. Check initial setup status
    status_res = await client.get("/admin/setup/status")
    assert status_res.status_code == 200
    assert status_res.json() == {"is_setup": False}

    # 2. First setup creates owner
    setup_payload = {
        "email": "owner@example.com",
        "password": "CorrectHorseBatteryStaple123!",
    }
    create_res = await client.post("/admin/setup", json=setup_payload)
    assert create_res.status_code == 200
    data = create_res.json()
    assert data["email"] == "owner@example.com"
    assert "csrf_token" in data

    # 3. Security Test 5: Setup endpoint MUST return 404 after first owner exists
    second_res = await client.post("/admin/setup", json=setup_payload)
    assert second_res.status_code == 404
    assert "already complete" in second_res.json()["detail"]


@pytest.mark.asyncio
async def test_security_test_4_login_rate_limit_and_error_uniformity(
    test_app_and_client: tuple[AsyncClient, FastAPI],
) -> None:
    client, _ = test_app_and_client

    # Setup owner
    await client.post(
        "/admin/setup",
        json={"email": "owner@example.com", "password": "CorrectHorseBatteryStaple123!"},
    )

    # Failed login with wrong password
    bad_res_1 = await client.post(
        "/admin/auth/login",
        json={"email": "owner@example.com", "password": "WrongPassword123!"},
    )
    assert bad_res_1.status_code == 401
    assert bad_res_1.json()["detail"] == "Invalid email or password."

    # Failed login with non-existent user returns IDENTICAL error message
    bad_res_2 = await client.post(
        "/admin/auth/login",
        json={"email": "nonexistent@example.com", "password": "WrongPassword123!"},
    )
    assert bad_res_2.status_code == 401
    assert bad_res_2.json()["detail"] == "Invalid email or password."

    # Exceed rate limit (5 attempts max)
    for _ in range(4):
        await client.post(
            "/admin/auth/login",
            json={"email": "owner@example.com", "password": "WrongPassword123!"},
        )

    # 6th attempt must be blocked by rate limit with HTTP 429
    rate_limited_res = await client.post(
        "/admin/auth/login",
        json={"email": "owner@example.com", "password": "WrongPassword123!"},
    )
    assert rate_limited_res.status_code == 429
    assert "Too many failed login attempts" in rate_limited_res.json()["detail"]


@pytest.mark.asyncio
async def test_security_test_4_csrf_and_origin_checks(
    test_app_and_client: tuple[AsyncClient, FastAPI],
) -> None:
    client, _ = test_app_and_client

    # Setup owner
    setup_res = await client.post(
        "/admin/setup",
        json={"email": "owner@example.com", "password": "CorrectHorseBatteryStaple123!"},
    )
    csrf_token = setup_res.json()["csrf_token"]

    # 1. State-changing request missing CSRF header -> 403 Forbidden
    res_no_csrf = await client.post("/admin/auth/logout")
    assert res_no_csrf.status_code == 403
    assert "Missing required X-CSRF-Token" in res_no_csrf.json()["detail"]

    # 2. State-changing request with invalid CSRF token -> 403 Forbidden
    res_bad_csrf = await client.post(
        "/admin/auth/logout",
        headers={"X-CSRF-Token": "invalid_csrf_token_value"},
    )
    assert res_bad_csrf.status_code == 403
    assert "Invalid CSRF token" in res_bad_csrf.json()["detail"]

    # 3. State-changing request with valid CSRF token -> 200 OK
    res_ok = await client.post(
        "/admin/auth/logout",
        headers={"X-CSRF-Token": csrf_token},
    )
    assert res_ok.status_code == 200


@pytest.mark.asyncio
async def test_security_test_10_admin_rejects_gateway_key_and_missing_session(
    test_app_and_client: tuple[AsyncClient, FastAPI],
) -> None:
    client, _ = test_app_and_client

    # 1. Calling /admin/auth/me without session -> 401
    res_no_session = await client.get("/admin/auth/me")
    assert res_no_session.status_code == 401

    # 2. Security Test 10: Calling /admin/auth/me with gateway key -> MUST return 401
    res_gw_key = await client.get(
        "/admin/auth/me",
        headers={"Authorization": "Bearer lgw_1234567890abcdef1234567890abcdef"},
    )
    assert res_gw_key.status_code == 401
    assert "Gateway keys are not permitted" in res_gw_key.json()["detail"]


@pytest.mark.asyncio
async def test_change_password_revokes_all_sessions(
    test_app_and_client: tuple[AsyncClient, FastAPI],
) -> None:
    client, _ = test_app_and_client

    # 1. Setup owner
    setup_res = await client.post(
        "/admin/setup",
        json={"email": "owner@example.com", "password": "CorrectHorseBatteryStaple123!"},
    )
    csrf_token = setup_res.json()["csrf_token"]

    # 2. Change password
    change_res = await client.post(
        "/admin/auth/change-password",
        json={
            "current_password": "CorrectHorseBatteryStaple123!",
            "new_password": "NewCorrectHorseBatteryStaple456!",
        },
        headers={"X-CSRF-Token": csrf_token},
    )
    assert change_res.status_code == 200
    assert "revoked" in change_res.json()["message"]

    # 3. Old session must now be rejected
    me_res = await client.get("/admin/auth/me")
    assert me_res.status_code == 401

    # 4. Login with old password fails
    old_login = await client.post(
        "/admin/auth/login",
        json={"email": "owner@example.com", "password": "CorrectHorseBatteryStaple123!"},
    )
    assert old_login.status_code == 401

    # 5. Login with new password succeeds
    new_login = await client.post(
        "/admin/auth/login",
        json={"email": "owner@example.com", "password": "NewCorrectHorseBatteryStaple456!"},
    )
    assert new_login.status_code == 200
