import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


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
    key_suffix: str = ""  # alias for key_last4 used by frontend
    created_at: datetime
    disabled_at: datetime | None
    is_enabled: bool = True  # computed from disabled_at

    @model_validator(mode="after")
    def _compute_fields(self) -> "ProviderCredentialResponse":
        self.is_enabled = self.disabled_at is None
        if not self.key_suffix:
            self.key_suffix = self.key_last4
        return self


class ProviderTestResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    success: bool = True  # True when status == "ok"
    message: str
    latency_ms: int
