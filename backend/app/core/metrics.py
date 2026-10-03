from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

# 1. Request count
REQUESTS_TOTAL = Counter(
    "gateway_requests_total",
    "Total requests processed by the gateway",
    ["endpoint", "provider", "model", "status"],
)

# 2. Latency histogram
REQUEST_DURATION_SECONDS = Histogram(
    "gateway_request_duration_seconds",
    "Request duration in seconds",
    ["endpoint", "model"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
)

# 3. Provider errors
PROVIDER_ERRORS_TOTAL = Counter(
    "gateway_provider_errors_total",
    "Total provider/upstream errors encountered",
    ["provider", "error_type"],
)

# 4. Queue depth
LOG_QUEUE_DEPTH = Gauge(
    "gateway_log_queue_depth",
    "Current number of pending log items in the batch logger queue",
)

# 5. Cache hits
CACHE_HITS_TOTAL = Counter(
    "gateway_cache_hits_total",
    "Total requests served from cache",
    ["endpoint", "model"],
)

# 6. Budget blocks
BUDGET_BLOCKS_TOTAL = Counter(
    "gateway_budget_blocks_total",
    "Total requests blocked due to budget limit",
    ["project_id", "period"],
)


def get_metrics_output() -> tuple[bytes, str]:
    """Render Prometheus metrics snapshot with updated queue depth."""
    from app.services.request_logger import request_logger

    LOG_QUEUE_DEPTH.set(request_logger.queue_size())
    return generate_latest(), CONTENT_TYPE_LATEST
