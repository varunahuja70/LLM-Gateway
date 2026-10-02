import base64
import os
import uuid
from collections.abc import AsyncGenerator
from datetime import date

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.admin.auth import reset_rate_limits
from app.core.crypto import decrypt
from app.db.base import Base
from app.db.models.provider import ModelPrice, ProviderCredential
from app.db.session import get_db_session
from app.deps import clear_gateway_key_memory_cache
from app.main import create_app
from scripts.seed_prices import seed_prices


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
async def test_stored_provider_key_never_returned_by_endpoints(
    app_and_client: tuple[AsyncClient, FastAPI, async_sessionmaker[AsyncSession]],
) -> None:
    """Security rule: A stored key is never returned by any endpoint. Only key_last4 on read."""
    client, _, session_factory = app_and_client
    csrf_token = await _setup_owner_and_login(client)

    secret_key = "sk-super-secret-production-openai-api-key-123456"

    # 1. Create provider credential
    create_res = await client.post(
        "/admin/providers",
        json={
            "provider": "openai",
            "name": "Production OpenAI Account",
            "api_key": secret_key,
        },
        headers={"X-CSRF-Token": csrf_token},
    )
    assert create_res.status_code == 200
    data = create_res.json()

    # Verify secret key is NOT in response
    assert secret_key not in str(data)
    assert "encrypted_key" not in data
    assert data["key_last4"] == "23456"[-4:]
    cred_id = uuid.UUID(data["id"])

    # 2. List provider credentials
    list_res = await client.get("/admin/providers")
    assert list_res.status_code == 200
    list_data = list_res.json()
    assert len(list_data) == 1
    assert secret_key not in str(list_data)
    assert "encrypted_key" not in str(list_data)
    assert list_data[0]["key_last4"] == "3456"

    # 3. Verify in DB that it is stored encrypted and decrypts with row ID as associated data
    async with session_factory() as session:
        result = await session.execute(
            select(ProviderCredential).where(ProviderCredential.id == cred_id)
        )
        record = result.scalar_one()
        assert record.encrypted_key != secret_key.encode()
        decrypted = decrypt(record.encrypted_key, associated_data=str(cred_id))
        assert decrypted == secret_key

    # 4. Test provider connectivity endpoint
    test_res = await client.post(f"/admin/providers/{cred_id}/test")
    assert test_res.status_code == 200
    assert test_res.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_prices_crud_and_json_import(
    app_and_client: tuple[AsyncClient, FastAPI, async_sessionmaker[AsyncSession]],
) -> None:
    client, _, _ = app_and_client
    csrf_token = await _setup_owner_and_login(client)

    # 1. Create a custom model price
    create_res = await client.post(
        "/admin/prices",
        json={
            "provider": "custom_provider",
            "model": "deep-thinker-v1",
            "input_micro_usd_per_mtok": 3_000_000,
            "output_micro_usd_per_mtok": 12_000_000,
            "cached_input_micro_usd_per_mtok": 300_000,
            "source_url": "https://custom.ai/pricing",
            "verified_on": "2026-10-03",
        },
        headers={"X-CSRF-Token": csrf_token},
    )
    assert create_res.status_code == 200
    price_data = create_res.json()
    assert price_data["provider"] == "custom_provider"
    assert price_data["is_seed"] is False
    price_id = price_data["id"]

    # 2. List prices includes new price
    list_res = await client.get("/admin/prices")
    assert list_res.status_code == 200
    assert any(p["model"] == "deep-thinker-v1" for p in list_res.json())

    # 3. Patch price
    patch_res = await client.patch(
        f"/admin/prices/{price_id}",
        json={"output_micro_usd_per_mtok": 15_000_000},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["output_micro_usd_per_mtok"] == 15_000_000

    # 4. JSON Import of multiple prices
    import_payload = {
        "prices": [
            {
                "provider": "import_provider",
                "model": "fast-v1",
                "input_micro_usd_per_mtok": 500_000,
                "output_micro_usd_per_mtok": 1_000_000,
                "cached_input_micro_usd_per_mtok": None,
                "source_url": "https://fast.ai/pricing",
                "verified_on": "2026-10-03",
            }
        ]
    }
    import_res = await client.post(
        "/admin/prices/import",
        json=import_payload,
        headers={"X-CSRF-Token": csrf_token},
    )
    assert import_res.status_code == 200
    assert "Successfully imported 1" in import_res.json()["message"]


@pytest.mark.asyncio
async def test_seed_prices_loader(
    app_and_client: tuple[AsyncClient, FastAPI, async_sessionmaker[AsyncSession]],
) -> None:
    """Verify seed_prices script loads seed prices with is_seed = True."""
    _, _, session_factory = app_and_client

    async with session_factory() as session:
        count = await seed_prices(session)
        assert count >= 10  # 12 seed prices defined in prices.seed.json

        # Query all seed prices
        res = await session.execute(select(ModelPrice).where(ModelPrice.is_seed.is_(True)))
        rows = res.scalars().all()
        assert len(rows) == count

        # Verify specific seed row
        gpt5 = next((r for r in rows if r.provider == "openai" and r.model == "gpt-5"), None)
        assert gpt5 is not None
        assert gpt5.input_micro_usd_per_mtok == 1_250_000
        assert gpt5.output_micro_usd_per_mtok == 10_000_000
        assert gpt5.cached_input_micro_usd_per_mtok == 125_000
        assert gpt5.source_url == "https://openai.com/api/pricing"
        assert gpt5.verified_on == date(2026, 10, 3)
