from typing import Any

from fastapi import APIRouter, Depends, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models.owner import OwnerUser, Session
from app.db.models.request import RequestLog
from app.db.models.setting import AppSetting
from app.db.session import get_db_session
from app.deps import require_csrf, require_owner
from app.schemas.auth import MessageResponse
from app.schemas.settings import DemoBannerData, SettingsResponse, SettingsUpdate
from app.services.audit import log_audit_event

router = APIRouter(prefix="/admin/settings", tags=["settings"])


async def _get_setting_value(db: AsyncSession, key: str, default: Any = None) -> Any:
    stmt = select(AppSetting).where(AppSetting.key == key)
    res = await db.execute(stmt)
    setting = res.scalar_one_or_none()
    return setting.value if setting is not None else default


async def _set_setting_value(db: AsyncSession, key: str, value: Any) -> None:
    stmt = select(AppSetting).where(AppSetting.key == key)
    res = await db.execute(stmt)
    setting = res.scalar_one_or_none()
    if setting is not None:
        setting.value = value
    else:
        setting = AppSetting(key=key, value=value)
        db.add(setting)


@router.get("", response_model=SettingsResponse)
async def get_system_settings(
    db: AsyncSession = Depends(get_db_session),
    _owner_auth: tuple[OwnerUser, Session] = Depends(require_owner),
) -> Any:
    """Retrieve system settings, demo mode status, and DemoBanner info."""
    settings = get_settings()

    retention_days = await _get_setting_value(db, "retention_days", settings.DEFAULT_RETENTION_DAYS)
    demo_mode = await _get_setting_value(db, "demo_mode", settings.DEMO_MODE)
    notification_defaults = await _get_setting_value(db, "notification_defaults", {})

    # Check if sample data exists in request_log
    sample_count = await db.scalar(select(func.count(RequestLog.id)))
    has_sample_data = (sample_count or 0) > 0

    return SettingsResponse(
        retention_days=int(retention_days),
        demo_mode=bool(demo_mode),
        demo_banner=DemoBannerData(
            is_demo=bool(demo_mode),
            has_sample_data=has_sample_data,
        ),
        notification_defaults=notification_defaults or {},
    )


@router.put("", response_model=SettingsResponse, dependencies=[Depends(require_csrf)])
async def update_system_settings(
    update_data: SettingsUpdate,
    db: AsyncSession = Depends(get_db_session),
    owner_auth: tuple[OwnerUser, Session] = Depends(require_owner),
) -> Any:
    """Update system settings (retention period, demo mode flag, notification defaults)."""
    owner, _ = owner_auth
    updated_fields: dict[str, Any] = {}

    if update_data.retention_days is not None:
        await _set_setting_value(db, "retention_days", update_data.retention_days)
        updated_fields["retention_days"] = update_data.retention_days

    if update_data.demo_mode is not None:
        await _set_setting_value(db, "demo_mode", update_data.demo_mode)
        updated_fields["demo_mode"] = update_data.demo_mode

    if update_data.notification_defaults is not None:
        await _set_setting_value(db, "notification_defaults", update_data.notification_defaults)
        updated_fields["notification_defaults"] = update_data.notification_defaults

    await db.commit()

    await log_audit_event(
        db,
        action="settings_updated",
        actor_type="owner",
        actor_id=owner.id,
        details=updated_fields,
    )

    return await get_system_settings(db, _owner_auth=owner_auth)


@router.post(
    "/seed-demo",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_csrf)],
)
async def trigger_seed_demo(
    db: AsyncSession = Depends(get_db_session),
    owner_auth: tuple[OwnerUser, Session] = Depends(require_owner),
) -> Any:
    """Seed demo data on demand from the dashboard."""
    owner, _ = owner_auth
    from scripts.seed_demo import seed_demo

    result = await seed_demo(db)
    await log_audit_event(
        db,
        action="demo_data_seeded",
        actor_type="owner",
        actor_id=owner.id,
        details=result,
    )
    return MessageResponse(message="Demo data successfully loaded.")


@router.post(
    "/clear-demo",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_csrf)],
)
async def trigger_clear_demo(
    db: AsyncSession = Depends(get_db_session),
    owner_auth: tuple[OwnerUser, Session] = Depends(require_owner),
) -> Any:
    """Purge synthetic demo data and revert dashboard to real data only."""
    owner, _ = owner_auth
    from scripts.seed_demo import clear_demo

    result = await clear_demo(db)
    await log_audit_event(
        db,
        action="demo_data_cleared",
        actor_type="owner",
        actor_id=owner.id,
        details=result,
    )
    return MessageResponse(message="Demo data successfully unloaded.")
