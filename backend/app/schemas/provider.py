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
    created_at: datetime
    disabled_at: datetime | None


class ProviderTestResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    message: str
    latency_ms: int
