import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ProviderCredentialCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=100)
    api_key: str = Field(..., min_length=1, max_length=1000)
    base_url: str | None = Field(default=None, max_length=2048)


class ProviderCredentialUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=100)
    api_key: str | None = Field(default=None, min_length=1, max_length=1000)
    base_url: str | None = Field(default=None, max_length=2048)
    is_disabled: bool | None = None


class ProviderCredentialResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    provider: str
    name: str
    base_url: str | None
    key_last4: str
    key_suffix: str = ""   # alias for key_last4 used by frontend
    created_at: datetime
    disabled_at: datetime | None
    is_enabled: bool = True  # computed from disabled_at

    @classmethod
    def model_validate(cls, obj: object, **kwargs: object) -> "ProviderCredentialResponse":  # type: ignore[override]
        instance = super().model_validate(obj, **kwargs)
        # disabled_at being set means it is disabled
        if hasattr(obj, "disabled_at"):
            instance.is_enabled = obj.disabled_at is None  # type: ignore[union-attr]
            instance.key_suffix = getattr(obj, "key_last4", "")
        return instance


class ProviderTestResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    success: bool = True   # True when status == "ok"
    message: str
    latency_ms: int
