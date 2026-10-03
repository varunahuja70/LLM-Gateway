import hashlib
import json
import time
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.budget import get_spend_counters
from app.core.errors import GatewayAPIException
from app.core.fallback import build_fallback_chain, is_fallback_trigger
from app.core.rate_limit import check_rate_limit
from app.core.routing import resolve_model, resolve_provider_credentials
from app.db.base import utc_now, uuid7
from app.db.models.project import GatewayKey, Project
from app.db.session import get_db_session
from app.deps import require_gateway_key
from app.providers.base import (
    EmbeddingRequest as ProviderEmbeddingRequest,
)
from app.providers.base import (
    ProviderError,
)
from app.providers.registry import get_adapter
from app.schemas.embeddings import EmbeddingRequest
from app.services.request_logger import RequestLogItem, request_logger

router = APIRouter(prefix="/v1", tags=["gateway-embeddings"])

MAX_BODY_SIZE = 4 * 1024 * 1024  # 4 MB limit


def _sanitize_user_tag(tag: str | None) -> str | None:
    if not tag:
        return None
    cleaned = "".join(c for c in tag if c.isprintable())[:128]
    return cleaned if cleaned else None


def _map_provider_error_status(err: ProviderError) -> int:
    from app.providers.base import (
        ProviderAuthError,
        ProviderBadRequestError,
        ProviderRateLimitError,
        ProviderTimeoutError,
    )

    if isinstance(err, ProviderRateLimitError):
        return 429
    if isinstance(err, ProviderAuthError):
        return 502
    if isinstance(err, ProviderTimeoutError):
        return 504
    if isinstance(err, ProviderBadRequestError):
        return 400
    return err.status_code if err.status_code != 500 else 502


@router.post("/embeddings")
async def create_embeddings(
    request: Request,
    payload: EmbeddingRequest,
    auth_data: tuple[Project, GatewayKey] = Depends(require_gateway_key),
    db: AsyncSession = Depends(get_db_session),
) -> JSONResponse:
    project, gateway_key = auth_data
    req_id = uuid7()
    req_time = utc_now()
    start_time = time.perf_counter()

    # 1. Enforce body size limit
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > MAX_BODY_SIZE:
                raise GatewayAPIException(
                    status_code=413,
                    message="Request body exceeds maximum allowed size of 4 MB.",
                    error_type="invalid_request_error",
                    code="request_too_large",
                )
        except ValueError:
            pass

    # 2. User tag
    raw_user_header = request.headers.get("X-Gateway-User") or payload.user
    user_tag = _sanitize_user_tag(raw_user_header)

    # 3. Cache header check
    cache_header = request.headers.get("X-Gateway-Cache", "").lower()
    cache_status = "bypass" if cache_header == "bypass" else "miss"

    # 4. Resolve primary model and candidate fallback chain
    fallback_chain = project.config.fallback_chain if project.config else None
    max_fallbacks = project.config.max_fallbacks if project.config else 2
    primary_provider, primary_model = await resolve_model(payload.model, fallback_chain, db)

    # Spec: Embeddings fallback only inside the same provider
    candidates = build_fallback_chain(
        primary_provider=primary_provider,
        primary_model=primary_model,
        fallback_chain=fallback_chain,
        max_fallbacks=max_fallbacks,
        is_embedding=True,
    )

    primary_model_used = f"{primary_provider}/{primary_model}"

    # 5. Rate limit check
    rpm_limit = project.config.rpm_limit if project.config else 60
    allowed, rate_retry = await check_rate_limit(project.id, limit_rpm=rpm_limit)
    if not allowed:
        log_item = RequestLogItem(
            id=req_id,
            project_id=project.id,
            gateway_key_id=gateway_key.id,
            created_at=req_time,
            endpoint="embeddings",
            provider=primary_provider,
            model_requested=payload.model or primary_model_used,
            model_used=primary_model_used,
            status="rate_limited",
            http_status=429,
            error_type="requests",
            error_message=f"Rate limit exceeded. Please retry after {rate_retry} seconds.",
            user_tag=user_tag,
        )
        request_logger.log(log_item)
        raise GatewayAPIException(
            status_code=429,
            message=f"Rate limit exceeded. Please retry after {rate_retry} seconds.",
            error_type="requests",
            code="rate_limit_exceeded",
            headers={
                "Retry-After": str(rate_retry),
                "X-Gateway-Request-Id": str(req_id),
                "X-Gateway-Cache": cache_status,
                "X-Gateway-Model-Used": primary_model_used,
                "X-Gateway-Fallback": "none",
            },
        )

    # 6. Budget check
    daily_spent, monthly_spent = await get_spend_counters(project.id)
    daily_limit = project.config.daily_budget_micro_usd if project.config else None
    monthly_limit = project.config.monthly_budget_micro_usd if project.config else None
    block_at_limit = project.config.block_at_limit if project.config else False

    is_blocked = False
    budget_retry = 3600
    period_name = "daily"

    if block_at_limit:
        if daily_limit and daily_spent >= daily_limit:
            is_blocked = True
            period_name = "daily"
        elif monthly_limit and monthly_spent >= monthly_limit:
            is_blocked = True
            period_name = "monthly"

    if is_blocked:
        log_item = RequestLogItem(
            id=req_id,
            project_id=project.id,
            gateway_key_id=gateway_key.id,
            created_at=req_time,
            endpoint="embeddings",
            provider=primary_provider,
            model_requested=payload.model or primary_model_used,
            model_used=primary_model_used,
            status="blocked",
            http_status=429,
            error_type="budget_exceeded",
            error_message=f"Project {period_name} budget exceeded.",
            user_tag=user_tag,
        )
        request_logger.log(log_item)
        raise GatewayAPIException(
            status_code=429,
            message=f"Project {period_name} budget exceeded.",
            error_type="budget_exceeded",
            code="budget_exceeded",
            headers={
                "Retry-After": str(budget_retry),
                "X-Gateway-Request-Id": str(req_id),
                "X-Gateway-Cache": cache_status,
                "X-Gateway-Model-Used": primary_model_used,
                "X-Gateway-Fallback": "none",
            },
        )

    # 7. Execution loop with fallback
    cred_map = project.config.provider_credential_id if project.config else None
    extra_headers: dict[str, str] = {}
    for h in ("x-mock-fail", "x-mock-fail-model"):
        val = request.headers.get(h)
        if val:
            extra_headers[h] = val

    raw_request_dict = payload.model_dump(exclude_none=True)
    request_canonical = json.dumps(raw_request_dict, sort_keys=True)
    request_hash = hashlib.sha256(request_canonical.encode("utf-8")).digest()
    log_content_enabled = bool(project.config and project.config.log_content)

    fallback_used = False
    fallback_from: str | None = None
    fallback_reason: str | None = None
    selected_provider = primary_provider
    selected_model = primary_model
    emb_res = None
    last_err: Exception | None = None

    for cand_idx, (cand_provider, cand_model) in enumerate(candidates):
        selected_provider = cand_provider
        selected_model = cand_model
        if cand_idx > 0:
            fallback_used = True
            fallback_from = f"{primary_provider}/{primary_model}"

        try:
            api_key, base_url = await resolve_provider_credentials(cred_map, cand_provider, db)
            adapter = get_adapter(cand_provider)
            if isinstance(payload.input, str):
                emb_input: str | list[str] = payload.input
            else:
                emb_input = [str(x) for x in payload.input]

            emb_req = ProviderEmbeddingRequest(
                model=cand_model,
                input=emb_input,
                extra_headers=extra_headers,
            )
            emb_res = await adapter.embeddings(emb_req, api_key=api_key, base_url=base_url)
            break
        except Exception as err:
            last_err = err
            can_fallback, reason = is_fallback_trigger(err)
            if can_fallback and cand_idx + 1 < len(candidates):
                fallback_reason = reason
                continue
            break

    final_model_used = f"{selected_provider}/{selected_model}"
    response_headers = {
        "X-Gateway-Request-Id": str(req_id),
        "X-Gateway-Cache": cache_status,
        "X-Gateway-Model-Used": final_model_used,
        "X-Gateway-Fallback": fallback_from if fallback_used and fallback_from else "none",
    }

    if emb_res is None:
        latency_ms = int((time.perf_counter() - start_time) * 1000)
        status_code = 502
        err_msg = str(last_err)
        err_type = "provider_error"
        err_code = None

        if isinstance(last_err, ProviderError):
            status_code = _map_provider_error_status(last_err)
            err_msg = last_err.message
            err_type = last_err.error_type
            err_code = last_err.code

        log_item = RequestLogItem(
            id=req_id,
            project_id=project.id,
            gateway_key_id=gateway_key.id,
            created_at=req_time,
            endpoint="embeddings",
            provider=selected_provider,
            model_requested=payload.model or primary_model_used,
            model_used=final_model_used,
            status="error",
            http_status=status_code,
            error_type=err_type,
            error_message=err_msg,
            latency_ms=latency_ms,
            fallback_used=fallback_used,
            fallback_from=fallback_from,
            fallback_reason=fallback_reason,
            user_tag=user_tag,
            request_hash=request_hash,
        )
        request_logger.log(log_item)

        raise GatewayAPIException(
            status_code=status_code,
            message=err_msg,
            error_type=err_type,
            code=err_code,
            headers=response_headers,
        )

    latency_ms = int((time.perf_counter() - start_time) * 1000)
    input_tokens = emb_res.usage.prompt_tokens

    response_data: dict[str, Any] = {
        "object": "list",
        "data": [
            {
                "object": "embedding",
                "index": item.index,
                "embedding": item.embedding,
            }
            for item in emb_res.data
        ],
        "model": emb_res.model,
        "usage": {
            "prompt_tokens": emb_res.usage.prompt_tokens,
            "total_tokens": emb_res.usage.total_tokens,
        },
    }

    log_item = RequestLogItem(
        id=req_id,
        project_id=project.id,
        gateway_key_id=gateway_key.id,
        created_at=req_time,
        endpoint="embeddings",
        provider=selected_provider,
        model_requested=payload.model or primary_model_used,
        model_used=final_model_used,
        status="ok",
        http_status=200,
        input_tokens=input_tokens,
        output_tokens=0,
        cached_input_tokens=0,
        usage_estimated=emb_res.usage.usage_estimated,
        latency_ms=latency_ms,
        streamed=False,
        fallback_used=fallback_used,
        fallback_from=fallback_from,
        fallback_reason=fallback_reason,
        user_tag=user_tag,
        request_hash=request_hash,
        log_content=log_content_enabled,
        request_json=raw_request_dict if log_content_enabled else None,
        response_json=response_data if log_content_enabled else None,
        config=project.config,
    )
    request_logger.log(log_item)

    return JSONResponse(
        content=response_data,
        status_code=200,
        headers=response_headers,
    )
