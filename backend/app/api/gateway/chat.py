import hashlib
import json
import re
import time
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.budget import check_budget_block
from app.core.errors import GatewayAPIException
from app.core.fallback import build_fallback_chain, is_fallback_trigger
from app.core.rate_limit import check_rate_limit
from app.core.routing import resolve_model, resolve_provider_credentials
from app.db.base import utc_now, uuid7
from app.db.models.project import GatewayKey, Project
from app.db.session import get_db_session
from app.deps import require_gateway_key
from app.providers.base import (
    ChatRequest,
    ProviderAuthError,
    ProviderBadRequestError,
    ProviderError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)
from app.providers.registry import get_adapter
from app.schemas.chat import ChatCompletionRequest
from app.services.request_logger import RequestLogItem, request_logger

router = APIRouter(prefix="/v1", tags=["gateway-chat"])

MAX_BODY_SIZE = 4 * 1024 * 1024  # 4 MB
MAX_TOKENS_CAP = 32768
USER_TAG_REGEX = re.compile(r"^[A-Za-z0-9_.\-@]{1,128}$")


def _sanitize_user_tag(raw_tag: str | None) -> str | None:
    if not raw_tag:
        return None
    cleaned = raw_tag.strip()
    if USER_TAG_REGEX.match(cleaned):
        return cleaned
    filtered = re.sub(r"[^A-Za-z0-9_.\-@]", "", cleaned)[:128]
    return filtered or None


def _map_provider_error_status(err: ProviderError) -> int:
    if isinstance(err, ProviderRateLimitError):
        return 429
    if isinstance(err, ProviderAuthError):
        return 502
    if isinstance(err, ProviderTimeoutError):
        return 504
    if isinstance(err, ProviderBadRequestError):
        return 400
    return err.status_code if err.status_code != 500 else 502


@router.post("/chat/completions")
async def chat_completions(
    request: Request,
    payload: ChatCompletionRequest,
    auth_data: tuple[Project, GatewayKey] = Depends(require_gateway_key),
    db: AsyncSession = Depends(get_db_session),
) -> Response:
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

    # 2. Enforce max_tokens cap
    requested_tokens = payload.max_tokens or payload.max_completion_tokens
    if requested_tokens is not None and requested_tokens > MAX_TOKENS_CAP:
        raise GatewayAPIException(
            status_code=400,
            message=f"max_tokens exceeds maximum allowed limit of {MAX_TOKENS_CAP}.",
            error_type="invalid_request_error",
            code="max_tokens_exceeded",
            param="max_tokens",
        )

    # 3. User tag header
    raw_user_header = request.headers.get("X-Gateway-User") or payload.user
    user_tag = _sanitize_user_tag(raw_user_header)

    # Cache header check
    cache_header = request.headers.get("X-Gateway-Cache", "").lower()
    cache_status = "bypass" if cache_header == "bypass" else "miss"

    # 4. Resolve primary model and candidate fallback chain
    fallback_chain = project.config.fallback_chain if project.config else None
    max_fallbacks = project.config.max_fallbacks if project.config else 2
    primary_provider, primary_model = await resolve_model(payload.model, fallback_chain, db)
    primary_model_used = f"{primary_provider}/{primary_model}"

    candidates = build_fallback_chain(
        primary_provider=primary_provider,
        primary_model=primary_model,
        fallback_chain=fallback_chain,
        max_fallbacks=max_fallbacks,
        is_embedding=False,
    )

    # Standard gateway response headers (initial)
    response_headers = {
        "X-Gateway-Request-Id": str(req_id),
        "X-Gateway-Cache": cache_status,
        "X-Gateway-Model-Used": primary_model_used,
        "X-Gateway-Fallback": "none",
    }

    # 4a. Rate limit check (sliding window)
    rpm_limit = project.config.rpm_limit if project.config else 60
    allowed, rate_retry = await check_rate_limit(project.id, limit_rpm=rpm_limit)
    if not allowed:
        log_item = RequestLogItem(
            id=req_id,
            project_id=project.id,
            gateway_key_id=gateway_key.id,
            created_at=req_time,
            endpoint="chat",
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
            headers={"Retry-After": str(rate_retry), **response_headers},
        )

    # 4b. Budget block check
    is_blocked, budget_retry, period_name = await check_budget_block(project.id, project.config)
    if is_blocked:
        log_item = RequestLogItem(
            id=req_id,
            project_id=project.id,
            gateway_key_id=gateway_key.id,
            created_at=req_time,
            endpoint="chat",
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
            headers={"Retry-After": str(budget_retry), **response_headers},
        )

    # 5. Prepare execution credentials and headers
    cred_map = project.config.provider_credential_id if project.config else None
    extra_headers: dict[str, str] = {}
    for h in ("x-mock-fail", "x-mock-fail-model", "x-mock-fail-after-chunks"):
        val = request.headers.get(h)
        if val:
            extra_headers[h] = val

    raw_messages = [m.model_dump(exclude_none=True) for m in payload.messages]
    raw_request_dict = payload.model_dump(exclude_none=True)
    request_canonical = json.dumps(raw_request_dict, sort_keys=True)
    request_hash = hashlib.sha256(request_canonical.encode("utf-8")).digest()
    log_content_enabled = bool(project.config and project.config.log_content)

    # 6. Non-streaming branch with fallback
    if not payload.stream:
        fallback_used = False
        fallback_from: str | None = None
        fallback_reason: str | None = None
        selected_provider = primary_provider
        selected_model = primary_model
        chat_res = None
        last_err: Exception | None = None

        for cand_idx, (cand_provider, cand_model) in enumerate(candidates):
            selected_provider = cand_provider
            selected_model = cand_model
            if cand_idx > 0:
                fallback_used = True
                fallback_from = primary_model_used

            try:
                api_key, base_url = await resolve_provider_credentials(cred_map, cand_provider, db)
                adapter = get_adapter(cand_provider)
                chat_request = ChatRequest(
                    model=cand_model,
                    messages=raw_messages,
                    stream=False,
                    temperature=payload.temperature,
                    max_tokens=requested_tokens,
                    top_p=payload.top_p,
                    tools=payload.tools,
                    tool_choice=payload.tool_choice,
                    extra_headers=extra_headers,
                )
                chat_res = await adapter.chat(chat_request, api_key=api_key, base_url=base_url)
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

        if chat_res is None:
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
                endpoint="chat",
                provider=selected_provider,
                model_requested=payload.model or primary_model_used,
                model_used=final_model_used,
                status="error",
                http_status=status_code,
                error_type=err_type,
                error_message=err_msg,
                latency_ms=latency_ms,
                streamed=False,
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
        input_tokens = chat_res.usage.prompt_tokens
        output_tokens = chat_res.usage.completion_tokens
        cached_tokens = chat_res.usage.cached_prompt_tokens

        choice = chat_res.choices[0] if chat_res.choices else None
        finish_reason = choice.finish_reason if choice else None
        output_content = None
        if choice and isinstance(choice.message, dict):
            output_content = str(choice.message.get("content") or "")

        response_data: dict[str, Any] = {
            "id": chat_res.id,
            "object": "chat.completion",
            "created": chat_res.created,
            "model": chat_res.model,
            "choices": [
                {
                    "index": c.index,
                    "message": c.message,
                    "finish_reason": c.finish_reason,
                }
                for c in chat_res.choices
            ],
            "usage": {
                "prompt_tokens": chat_res.usage.prompt_tokens,
                "completion_tokens": chat_res.usage.completion_tokens,
                "total_tokens": chat_res.usage.total_tokens,
                "prompt_tokens_details": {
                    "cached_tokens": chat_res.usage.cached_prompt_tokens,
                },
            },
        }
        if chat_res.system_fingerprint:
            response_data["system_fingerprint"] = chat_res.system_fingerprint

        log_item = RequestLogItem(
            id=req_id,
            project_id=project.id,
            gateway_key_id=gateway_key.id,
            created_at=req_time,
            endpoint="chat",
            provider=selected_provider,
            model_requested=payload.model or primary_model_used,
            model_used=final_model_used,
            status="ok",
            http_status=200,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_input_tokens=cached_tokens,
            usage_estimated=chat_res.usage.usage_estimated,
            latency_ms=latency_ms,
            streamed=False,
            finish_reason=finish_reason,
            fallback_used=fallback_used,
            fallback_from=fallback_from,
            fallback_reason=fallback_reason,
            user_tag=user_tag,
            request_hash=request_hash,
            log_content=log_content_enabled,
            request_json=raw_request_dict if log_content_enabled else None,
            response_json=response_data if log_content_enabled else None,
            output_content=output_content,
            config=project.config,
        )
        request_logger.log(log_item)

        return JSONResponse(
            content=response_data,
            status_code=200,
            headers=response_headers,
        )

    # 7. Streaming branch (SSE) with pre-first-byte fallback
    fallback_used = False
    fallback_from = None
    fallback_reason = None
    selected_provider = primary_provider
    selected_model = primary_model
    active_stream = None
    first_chunk = None
    last_err = None

    for cand_idx, (cand_provider, cand_model) in enumerate(candidates):
        selected_provider = cand_provider
        selected_model = cand_model
        if cand_idx > 0:
            fallback_used = True
            fallback_from = primary_model_used

        try:
            api_key, base_url = await resolve_provider_credentials(cred_map, cand_provider, db)
            adapter = get_adapter(cand_provider)
            chat_request = ChatRequest(
                model=cand_model,
                messages=raw_messages,
                stream=True,
                temperature=payload.temperature,
                max_tokens=requested_tokens,
                top_p=payload.top_p,
                tools=payload.tools,
                tool_choice=payload.tool_choice,
                extra_headers=extra_headers,
            )
            stream_iter = adapter.stream_chat(chat_request, api_key=api_key, base_url=base_url)
            # Pull first chunk before sending any byte to client
            first_chunk = await anext(stream_iter)
            active_stream = stream_iter
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

    if active_stream is None or first_chunk is None:
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
            endpoint="chat",
            provider=selected_provider,
            model_requested=payload.model or primary_model_used,
            model_used=final_model_used,
            status="error",
            http_status=status_code,
            error_type=err_type,
            error_message=err_msg,
            latency_ms=latency_ms,
            streamed=True,
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

    def _format_chunk(chunk: Any) -> str:
        chunk_dict: dict[str, Any] = {
            "id": chunk.id,
            "object": "chat.completion.chunk",
            "created": chunk.created,
            "model": chunk.model,
            "choices": [
                {
                    "index": sc.index,
                    "delta": {
                        k: v
                        for k, v in {
                            "role": sc.delta.role,
                            "content": sc.delta.content,
                            "tool_calls": sc.delta.tool_calls,
                        }.items()
                        if v is not None
                    },
                    "finish_reason": sc.finish_reason,
                }
                for sc in chunk.choices
            ],
        }
        if chunk.usage:
            chunk_dict["usage"] = {
                "prompt_tokens": chunk.usage.prompt_tokens,
                "completion_tokens": chunk.usage.completion_tokens,
                "total_tokens": chunk.usage.total_tokens,
            }
        return f"data: {json.dumps(chunk_dict)}\n\n"

    async def sse_event_stream() -> AsyncIterator[str]:
        ttft_ms: int | None = int((time.perf_counter() - start_time) * 1000)
        total_input_tokens = 0
        total_output_tokens = 0
        cached_tokens = 0
        usage_estimated = False
        finish_reason: str | None = None
        collected_content: list[str] = []
        is_error = False
        error_msg: str | None = None
        error_type: str | None = None

        try:
            assert first_chunk is not None
            assert active_stream is not None

            # Yield pre-fetched first chunk
            if first_chunk.choices:
                c = first_chunk.choices[0]
                if c.finish_reason:
                    finish_reason = c.finish_reason
                if c.delta and c.delta.content:
                    collected_content.append(c.delta.content)
            if first_chunk.usage:
                total_input_tokens = first_chunk.usage.prompt_tokens
                total_output_tokens = first_chunk.usage.completion_tokens
                cached_tokens = first_chunk.usage.cached_prompt_tokens
                usage_estimated = first_chunk.usage.usage_estimated

            yield _format_chunk(first_chunk)

            # Yield remaining chunks from active stream (no fallback allowed after first byte)
            async for chunk in active_stream:
                if chunk.choices:
                    c = chunk.choices[0]
                    if c.finish_reason:
                        finish_reason = c.finish_reason
                    if c.delta and c.delta.content:
                        collected_content.append(c.delta.content)

                if chunk.usage:
                    total_input_tokens = chunk.usage.prompt_tokens
                    total_output_tokens = chunk.usage.completion_tokens
                    cached_tokens = chunk.usage.cached_prompt_tokens
                    usage_estimated = chunk.usage.usage_estimated

                yield _format_chunk(chunk)

            yield "data: [DONE]\n\n"
        except Exception as err:
            is_error = True
            error_msg = str(err)
            error_type = type(err).__name__
            err_payload = json.dumps(
                {"error": {"message": error_msg, "type": "provider_error", "code": None}}
            )
            yield f"data: {err_payload}\n\n"
            yield "data: [DONE]\n\n"
        finally:
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            full_output = "".join(collected_content)

            if total_input_tokens == 0 and total_output_tokens == 0:
                from app.providers.base import estimate_tokens

                total_input_tokens = sum(
                    estimate_tokens(str(m.content or "")) for m in payload.messages
                )
                total_output_tokens = estimate_tokens(full_output)
                usage_estimated = True

            log_item = RequestLogItem(
                id=req_id,
                project_id=project.id,
                gateway_key_id=gateway_key.id,
                created_at=req_time,
                endpoint="chat",
                provider=selected_provider,
                model_requested=payload.model or primary_model_used,
                model_used=final_model_used,
                status="error" if is_error else "ok",
                http_status=500 if is_error else 200,
                error_type=error_type,
                error_message=error_msg,
                input_tokens=total_input_tokens,
                output_tokens=total_output_tokens,
                cached_input_tokens=cached_tokens,
                usage_estimated=usage_estimated,
                latency_ms=latency_ms,
                ttft_ms=ttft_ms,
                streamed=True,
                finish_reason=finish_reason,
                fallback_used=fallback_used,
                fallback_from=fallback_from,
                fallback_reason=fallback_reason,
                user_tag=user_tag,
                request_hash=request_hash,
                log_content=log_content_enabled,
                request_json=raw_request_dict if log_content_enabled else None,
                response_json={"content": full_output} if log_content_enabled else None,
                output_content=full_output,
                config=project.config,
            )
            request_logger.log(log_item)

    return StreamingResponse(
        sse_event_stream(),
        media_type="text/event-stream; charset=utf-8",
        headers={
            **response_headers,
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
