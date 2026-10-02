import re
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class FallbackTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str = Field(..., min_length=1, max_length=50)
    model: str = Field(..., min_length=1, max_length=100)


class ProjectCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=100)
    slug: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=1000)

    @field_validator("slug", mode="before")
    @classmethod
    def validate_or_generate_slug(cls, v: str | None) -> str | None:
        if v is not None:
            clean = re.sub(r"[^a-z0-9\-]+", "-", v.lower().strip()).strip("-")
            if not clean:
                raise ValueError("Invalid slug format.")
            return clean
        return None


class ProjectUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=1000)


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    description: str | None
    created_at: datetime
    archived_at: datetime | None
    active_keys_count: int = 0


class ProjectConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    project_id: uuid.UUID
    daily_budget_micro_usd: int | None
    monthly_budget_micro_usd: int | None
    warn_thresholds: list[int]
    block_at_limit: bool
    fallback_chain: list[FallbackTarget]
    max_fallbacks: int
    request_timeout_s: int
    cache_enabled: bool
    cache_ttl_s: int
    rpm_limit: int
    log_content: bool
    webhook_url: str | None
    has_webhook_secret: bool
    provider_credential_id: dict[str, Any]


class ProjectConfigUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    daily_budget_micro_usd: int | None = Field(default=None, ge=0)
    monthly_budget_micro_usd: int | None = Field(default=None, ge=0)
    warn_thresholds: list[int] | None = Field(default=None)
    block_at_limit: bool | None = None
    fallback_chain: list[FallbackTarget] | None = None
    max_fallbacks: int | None = Field(default=None, ge=0, le=5)
    request_timeout_s: int | None = Field(default=None, ge=5, le=300)
    cache_enabled: bool | None = None
    cache_ttl_s: int | None = Field(default=None, ge=60, le=2592000)
    rpm_limit: int | None = Field(default=None, ge=1, le=100000)
    log_content: bool | None = None
    webhook_url: str | None = Field(default=None, max_length=2048)
    webhook_secret: str | None = Field(default=None, min_length=8, max_length=256)
    provider_credential_id: dict[str, Any] | None = None

    @field_validator("warn_thresholds")
    @classmethod
    def validate_thresholds(cls, v: list[int] | None) -> list[int] | None:
        if v is not None:
            if not v:
                raise ValueError("warn_thresholds cannot be empty")
            for t in v:
                if not (1 <= t <= 100):
                    raise ValueError("Thresholds must be integers between 1 and 100")
            return sorted(set(v))
        return v
