from typing import Any

from pydantic import BaseModel, Field


class DemoBannerData(BaseModel):
    is_demo: bool = False
    message: str = "Demo mode is active. Using deterministic mock provider without real keys."
    has_sample_data: bool = False


class SettingsResponse(BaseModel):
    retention_days: int = 30
    demo_mode: bool = False
    demo_banner: DemoBannerData
    notification_defaults: dict[str, Any] = Field(default_factory=dict)


class SettingsUpdate(BaseModel):
    retention_days: int | None = Field(None, ge=1, le=365)
    demo_mode: bool | None = None
    notification_defaults: dict[str, Any] | None = None
