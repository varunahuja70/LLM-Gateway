import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class RequestContentDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    request_id: uuid.UUID
    request_json: dict[str, Any]
    response_json: dict[str, Any]


class RequestLogSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    gateway_key_id: uuid.UUID | None = None
    created_at: datetime
    endpoint: str
    provider: str
    model_requested: str
    model_used: str
    status: str
    http_status: int
    error_type: str | None = None
    error_message_safe: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: int = 0
    usage_estimated: bool = False
    cost_micro_usd: int | None = None
    saved_micro_usd: int = 0
    latency_ms: int
    ttft_ms: int | None = None
    streamed: bool = False
    cache_hit: bool = False
    fallback_used: bool = False
    fallback_from: str | None = None
    fallback_reason: str | None = None
    finish_reason: str | None = None
    empty_or_truncated: bool = False
    user_tag: str | None = None
    feedback_score: int | None = None


class RequestDetailResponse(RequestLogSummary):
    content: RequestContentDetail | None = None


class RequestListResponse(BaseModel):
    items: list[RequestLogSummary]
    next_cursor: str | None = None
    has_more: bool = False
