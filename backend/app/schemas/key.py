import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class GatewayKeyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=100)
    expires_at: datetime | None = None


class GatewayKeyCreatedResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    prefix: str
    created_at: datetime
    expires_at: datetime | None
    raw_key: str  # Only returned once upon creation or rotation!


class GatewayKeyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    prefix: str
    created_at: datetime
    last_used_at: datetime | None
    revoked_at: datetime | None
    expires_at: datetime | None
