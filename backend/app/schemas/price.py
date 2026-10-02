import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class ModelPriceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str = Field(..., min_length=1, max_length=50)
    model: str = Field(..., min_length=1, max_length=100)
    input_micro_usd_per_mtok: int = Field(..., ge=0)
    output_micro_usd_per_mtok: int = Field(..., ge=0)
    cached_input_micro_usd_per_mtok: int | None = Field(default=None, ge=0)
    source_url: str = Field(..., max_length=1000)
    verified_on: date


class ModelPriceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_micro_usd_per_mtok: int | None = Field(default=None, ge=0)
    output_micro_usd_per_mtok: int | None = Field(default=None, ge=0)
    cached_input_micro_usd_per_mtok: int | None = Field(default=None, ge=0)
    source_url: str | None = Field(default=None, max_length=1000)
    verified_on: date | None = None


class ModelPriceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    provider: str
    model: str
    input_micro_usd_per_mtok: int
    output_micro_usd_per_mtok: int
    cached_input_micro_usd_per_mtok: int | None
    source_url: str
    verified_on: date
    is_seed: bool
    updated_at: datetime


class ModelPriceImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prices: list[ModelPriceCreate] = Field(..., min_length=1, max_length=500)
