import asyncio
import contextlib
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.budget import record_spend_and_check_alerts
from app.core.pricing import calculate_cost, get_price_for_model
from app.db.models.provider import ModelPrice
from app.db.models.request import RequestContent, RequestLog
from app.db.session import get_sessionmaker
from app.logging_setup import redact_string
from app.services.webhook import deliver_webhook

logger = logging.getLogger(__name__)


@dataclass
class RequestLogItem:
    id: uuid.UUID
    project_id: uuid.UUID
    gateway_key_id: uuid.UUID | None
    created_at: datetime
    endpoint: str  # 'chat' | 'embeddings'
    provider: str
    model_requested: str
    model_used: str
    status: str  # 'ok' | 'error' | 'blocked' | 'rate_limited'
    http_status: int
    error_type: str | None = None
    error_message: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: int = 0
    usage_estimated: bool = False
    saved_micro_usd: int = 0
    latency_ms: int = 0
    ttft_ms: int | None = None
    streamed: bool = False
    cache_hit: bool = False
    fallback_used: bool = False
    fallback_from: str | None = None
    fallback_reason: str | None = None
    finish_reason: str | None = None
    user_tag: str | None = None
    request_hash: bytes | None = None
    log_content: bool = False
    request_json: dict[str, Any] | None = None
    response_json: dict[str, Any] | None = None
    output_content: str | None = None
    config: Any | None = None


class RequestLoggerService:
    def __init__(self) -> None:
        self._queue: asyncio.Queue[RequestLogItem] = asyncio.Queue()
        self._worker_task: asyncio.Task[None] | None = None
        self._running = False
        self._sessionmaker: async_sessionmaker[AsyncSession] | None = None
        self._price_cache: dict[tuple[str, str], ModelPrice | None] = {}

    def log(self, item: RequestLogItem) -> None:
        """Add request log entry to the in-memory queue. Non-blocking."""
        self._queue.put_nowait(item)

        # Update Prometheus metrics
        try:
            from app.core.metrics import (
                BUDGET_BLOCKS_TOTAL,
                CACHE_HITS_TOTAL,
                PROVIDER_ERRORS_TOTAL,
                REQUEST_DURATION_SECONDS,
                REQUESTS_TOTAL,
            )

            REQUESTS_TOTAL.labels(
                endpoint=item.endpoint,
                provider=item.provider,
                model=item.model_used,
                status=item.status,
            ).inc()

            if item.latency_ms > 0:
                REQUEST_DURATION_SECONDS.labels(
                    endpoint=item.endpoint,
                    model=item.model_used,
                ).observe(item.latency_ms / 1000.0)

            if item.cache_hit:
                CACHE_HITS_TOTAL.labels(
                    endpoint=item.endpoint,
                    model=item.model_used,
                ).inc()

            if item.status == "error" and item.error_type:
                PROVIDER_ERRORS_TOTAL.labels(
                    provider=item.provider,
                    error_type=item.error_type,
                ).inc()

            if item.status == "blocked" and item.error_type == "budget_exceeded":
                BUDGET_BLOCKS_TOTAL.labels(
                    project_id=str(item.project_id),
                    period="limit",
                ).inc()
        except Exception as exc:
            logger.debug("Failed to record prometheus metrics: %s", exc)

    def queue_size(self) -> int:
        """Return the current number of items waiting in the log queue."""
        return self._queue.qsize()

    def start(self, session_factory: async_sessionmaker[AsyncSession] | None = None) -> None:
        """Start the background worker if not already running."""
        if self._worker_task is not None and not self._worker_task.done():
            return
        self._running = True
        self._sessionmaker = session_factory or get_sessionmaker()
        self._worker_task = asyncio.create_task(self._batch_worker())

    async def stop(self) -> None:
        """Stop worker and flush remaining logs."""
        self._running = False
        if self._worker_task is not None:
            self._worker_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._worker_task
            self._worker_task = None
        await self.flush()

    async def flush(self) -> None:
        """Process and commit all items currently pending in the queue."""
        batch: list[RequestLogItem] = []
        while not self._queue.empty():
            try:
                batch.append(self._queue.get_nowait())
            except asyncio.QueueEmpty:
                break

        if batch:
            await self._write_batch(batch)

    async def _batch_worker(self) -> None:
        """Background worker that pulls logs from queue in batches."""
        while self._running:
            batch: list[RequestLogItem] = []
            try:
                # Wait for first item
                item = await self._queue.get()
                batch.append(item)

                # Collect any other ready items up to 50
                while len(batch) < 50:
                    try:
                        batch.append(self._queue.get_nowait())
                    except asyncio.QueueEmpty:
                        break

                await self._write_batch(batch)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception("Error in request logger batch worker: %s", e)
                await asyncio.sleep(0.1)

    async def _write_batch(self, items: list[RequestLogItem]) -> None:
        if not items:
            return

        session_factory = self._sessionmaker or get_sessionmaker()
        async with session_factory() as session:
            try:
                for item in items:
                    # Resolve price
                    model_name = (
                        item.model_used[len(item.provider) + 1 :]
                        if item.model_used.startswith(f"{item.provider}/")
                        else item.model_used
                    )
                    cache_key = (item.provider, model_name)
                    if cache_key not in self._price_cache:
                        price = await get_price_for_model(session, item.provider, model_name)
                        if not price and model_name != item.model_used:
                            price = await get_price_for_model(
                                session, item.provider, item.model_used
                            )
                        self._price_cache[cache_key] = price
                    price_record = self._price_cache[cache_key]

                    # Calculate cost (None if unknown price, never 0)
                    cost = calculate_cost(
                        provider=item.provider,
                        model=model_name,
                        input_tokens=item.input_tokens,
                        output_tokens=item.output_tokens,
                        cached_input_tokens=item.cached_input_tokens,
                        price=price_record,
                    )

                    saved_micro_usd = item.saved_micro_usd
                    if item.cache_hit:
                        if saved_micro_usd == 0 and cost is not None:
                            saved_micro_usd = cost
                        cost = 0

                    # Record spend in budget counters and trigger alerts if thresholds crossed
                    if not item.cache_hit and cost and cost > 0 and item.config:
                        try:
                            alerts = await record_spend_and_check_alerts(
                                item.project_id, cost, item.config, session
                            )
                            for alert in alerts:
                                if item.config.webhook_url:
                                    payload = {
                                        "event": "budget_alert",
                                        "alert_id": str(alert.id),
                                        "project_id": str(alert.project_id),
                                        "period": alert.period,
                                        "threshold_percent": alert.threshold_percent,
                                        "spend_micro_usd": alert.spend_micro_usd,
                                        "budget_micro_usd": alert.budget_micro_usd,
                                        "timestamp": alert.created_at.isoformat(),
                                    }
                                    asyncio.create_task(
                                        deliver_webhook(
                                            alert.id,
                                            alert.project_id,
                                            item.config.webhook_url,
                                            item.config.webhook_secret_encrypted,
                                            payload,
                                            session_factory=session_factory,
                                        )
                                    )
                        except Exception as alert_err:
                            logger.warning("Error checking budget alerts: %s", alert_err)

                    # Compute quality signal: empty_or_truncated
                    is_empty_or_truncated = (item.finish_reason == "length") or (
                        item.endpoint == "chat"
                        and item.status == "ok"
                        and not (item.output_content or "").strip()
                    )

                    # Redact error message
                    safe_error = redact_string(item.error_message) if item.error_message else None

                    req_log = RequestLog(
                        id=item.id,
                        project_id=item.project_id,
                        gateway_key_id=item.gateway_key_id,
                        created_at=item.created_at,
                        endpoint=item.endpoint,
                        provider=item.provider,
                        model_requested=item.model_requested,
                        model_used=item.model_used,
                        status=item.status,
                        http_status=item.http_status,
                        error_type=item.error_type,
                        error_message_safe=safe_error,
                        input_tokens=0 if item.cache_hit else item.input_tokens,
                        output_tokens=0 if item.cache_hit else item.output_tokens,
                        cached_input_tokens=0 if item.cache_hit else item.cached_input_tokens,
                        usage_estimated=item.usage_estimated,
                        cost_micro_usd=cost,
                        saved_micro_usd=saved_micro_usd,
                        latency_ms=item.latency_ms,
                        ttft_ms=item.ttft_ms,
                        streamed=item.streamed,
                        cache_hit=item.cache_hit,
                        fallback_used=item.fallback_used,
                        fallback_from=item.fallback_from,
                        fallback_reason=item.fallback_reason,
                        finish_reason=item.finish_reason,
                        empty_or_truncated=is_empty_or_truncated,
                        user_tag=item.user_tag,
                        feedback_score=None,
                        request_hash=item.request_hash,
                    )
                    session.add(req_log)

                    if item.log_content and item.request_json and item.response_json:
                        content_record = RequestContent(
                            request_id=item.id,
                            request_json=item.request_json,
                            response_json=item.response_json,
                        )
                        session.add(content_record)

                await session.commit()
            except Exception as e:
                await session.rollback()
                logger.exception("Failed to write request log batch to database: %s", e)


# Global singleton instance
request_logger = RequestLoggerService()
