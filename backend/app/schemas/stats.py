import uuid
from datetime import datetime

from pydantic import BaseModel


class OverviewStats(BaseModel):
    total_requests: int = 0
    total_tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: int = 0
    total_cost_micro_usd: int = 0
    saved_micro_usd: int = 0
    error_rate: float = 0.0
    fallback_rate: float = 0.0
    avg_latency_ms: float = 0.0
    cache_hit_rate: float = 0.0


class TimeseriesBucket(BaseModel):
    timestamp: datetime
    requests: int = 0
    errors: int = 0
    tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_micro_usd: int = 0
    saved_micro_usd: int = 0
    cache_hits: int = 0
    p50_latency_ms: float | None = None
    p95_latency_ms: float | None = None
    p99_latency_ms: float | None = None


class TimeseriesResponse(BaseModel):
    bucket: str
    data: list[TimeseriesBucket]


class ModelQualityStat(BaseModel):
    model: str
    provider: str
    total_requests: int = 0
    total_tokens: int = 0
    total_cost_micro_usd: int = 0
    error_rate: float = 0.0
    fallback_rate: float = 0.0
    p50_latency_ms: float | None = None
    p95_latency_ms: float | None = None
    p99_latency_ms: float | None = None
    avg_ttft_ms: float | None = None
    empty_or_truncated_rate: float = 0.0
    avg_feedback_score: float | None = None


class ModelsQualityResponse(BaseModel):
    data: list[ModelQualityStat]


class ProjectStatsResponse(BaseModel):
    project_id: uuid.UUID
    overview: OverviewStats
    models: list[ModelQualityStat]
    budget_daily_used_micro_usd: int = 0
    budget_monthly_used_micro_usd: int = 0
