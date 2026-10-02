import time
import uuid
from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base, uuid7
from app.db.models import (
    AppSetting,
    AuditEvent,
    BudgetAlert,
    GatewayKey,
    ModelPrice,
    OwnerUser,
    Project,
    ProjectConfig,
    ProviderCredential,
    RequestContent,
    RequestLog,
    Session,
)


def test_uuid7_properties() -> None:
    u1 = uuid7()
    time.sleep(0.002)
    u2 = uuid7()

    assert u1.version == 7
    assert u2.version == 7
    assert u1.variant == uuid.RFC_4122
    assert str(u1) < str(u2)
    assert u1 != u2


@pytest.mark.asyncio
async def test_models_lifecycle_and_constraints() -> None:
    # Use SQLite in-memory for testing model definitions and relationships
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        # 1. Test OwnerUser and single_owner constraint
        owner1 = OwnerUser(
            email="owner@example.com",
            password_hash="argon2id$hashed",
        )
        session.add(owner1)
        await session.commit()
        await session.refresh(owner1)

        assert owner1.id is not None
        assert owner1.email == "owner@example.com"
        saved_owner_id = owner1.id
        saved_created_at = owner1.created_at

        # Attempting second owner must violate single_owner_guard
        owner2 = OwnerUser(
            email="owner2@example.com",
            password_hash="argon2id$hashed2",
        )
        session.add(owner2)
        with pytest.raises(IntegrityError):
            await session.commit()
        await session.rollback()

        # 2. Test Session
        owner_session = Session(
            id="session_token_hash_64_chars_hex_value_for_testing_1234567890abcdef",
            owner_id=saved_owner_id,
            csrf_token_hash="csrf_hash_64_chars_value_for_testing",
            expires_at=saved_created_at,
        )
        session.add(owner_session)
        await session.commit()

        # 3. Test Project & ProjectConfig & GatewayKey
        project = Project(
            name="Production App",
            slug="prod-app",
            description="Main customer-facing application",
        )
        session.add(project)
        await session.flush()

        config = ProjectConfig(
            project_id=project.id,
            daily_budget_micro_usd=10_000_000,
            monthly_budget_micro_usd=100_000_000,
            warn_thresholds=[50, 80, 100],
            block_at_limit=True,
            fallback_chain=[{"provider": "anthropic", "model": "claude-haiku-4-5"}],
        )
        session.add(config)

        key = GatewayKey(
            project_id=project.id,
            name="Default Key",
            prefix="lgw_abcd",
            key_hash="hash_of_key_64_chars_here_for_testing_purposes_only_12345678901234",
        )
        session.add(key)
        await session.commit()

        # 4. Test ProviderCredential & ModelPrice
        cred = ProviderCredential(
            provider="openai",
            name="OpenAI Prod",
            encrypted_key=b"encrypted_secret_bytes",
            key_last4="abcd",
        )
        session.add(cred)

        price = ModelPrice(
            provider="openai",
            model="gpt-5",
            input_micro_usd_per_mtok=1_250_000,
            output_micro_usd_per_mtok=10_000_000,
            source_url="https://openai.com/api/pricing/",
            verified_on=date(2026, 10, 3),
            is_seed=True,
        )
        session.add(price)
        await session.commit()

        # 5. Test RequestLog & RequestContent
        req = RequestLog(
            project_id=project.id,
            gateway_key_id=key.id,
            endpoint="chat",
            provider="openai",
            model_requested="openai/gpt-5",
            model_used="openai/gpt-5",
            status="ok",
            http_status=200,
            input_tokens=100,
            output_tokens=50,
            cost_micro_usd=625,
            latency_ms=450,
        )
        session.add(req)
        await session.flush()

        content = RequestContent(
            request_id=req.id,
            request_json={"messages": [{"role": "user", "content": "hi"}]},
            response_json={"choices": [{"message": {"content": "hello"}}]},
        )
        session.add(content)
        await session.commit()

        # 6. Test BudgetAlert, AuditEvent, AppSetting
        alert = BudgetAlert(
            project_id=project.id,
            period="daily",
            period_start=saved_created_at,
            threshold_percent=80,
            spend_micro_usd=8_000_000,
            budget_micro_usd=10_000_000,
        )
        session.add(alert)

        audit = AuditEvent(
            action="project_created",
            actor_type="owner",
            actor_id=str(saved_owner_id),
            target_type="project",
            target_id=str(project.id),
        )
        session.add(audit)

        setting = AppSetting(
            key="retention_days",
            value=30,
        )
        session.add(setting)
        await session.commit()

        # 7. Query and verify relationships
        stmt = select(Project).where(Project.slug == "prod-app")
        loaded_project = (await session.execute(stmt)).scalar_one()
        assert loaded_project.name == "Production App"
        assert loaded_project.config is not None
        assert loaded_project.config.block_at_limit is True
        assert len(loaded_project.keys) == 1

    await engine.dispose()
