import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.providers.base import (
    ChatRequest,
    ChatResponse,
    ChatStreamChunk,
    Choice,
    EmbeddingRequest,
    EmbeddingResponse,
    ProviderAdapter,
    ProviderAuthError,
    ProviderBadRequestError,
    ProviderError,
    ProviderOverloadedError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    StreamChoice,
    StreamDelta,
    UsageInfo,
    estimate_tokens,
    get_shared_http_client,
)

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"


class AnthropicAdapter(ProviderAdapter):
    """Anthropic Messages API adapter translating to/from OpenAI shapes."""

    def _map_finish_reason(self, stop_reason: str | None) -> str | None:
        if not stop_reason:
            return None
        mapping = {
            "end_turn": "stop",
            "stop_sequence": "stop",
            "max_tokens": "length",
            "tool_use": "tool_calls",
        }
        return mapping.get(stop_reason, stop_reason)

    def _map_error(self, status_code: int, response_text: str) -> ProviderError:
        message = response_text
        code: str | None = None
        try:
            err_json = json.loads(response_text)
            if "error" in err_json:
                message = err_json["error"].get("message", response_text)
                code = err_json["error"].get("type")
        except Exception:
            pass

        if status_code == 401:
            return ProviderAuthError(f"Anthropic auth failed: {message}", provider="anthropic")
        if status_code == 429:
            return ProviderRateLimitError(f"Anthropic rate limit: {message}", provider="anthropic")
        if status_code in (500, 529, 503, 502):
            return ProviderOverloadedError(
                f"Anthropic overloaded/error ({status_code}): {message}", provider="anthropic"
            )
        if status_code == 400:
            return ProviderBadRequestError(
                f"Anthropic bad request: {message}", provider="anthropic", code=code
            )
        return ProviderError(
            f"Anthropic API error ({status_code}): {message}",
            status_code=status_code,
            provider="anthropic",
            code=code,
        )

    def _prepare_payload(
        self, request: ChatRequest, stream: bool = False
    ) -> tuple[dict[str, Any], dict[str, str]]:
        system_content: list[str] = []
        anthropic_messages: list[dict[str, Any]] = []

        for msg in request.messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role == "system":
                if content:
                    system_content.append(str(content))
            elif role in ("user", "assistant"):
                anthropic_messages.append(
                    {"role": role, "content": str(content) if content is not None else ""}
                )

        payload: dict[str, Any] = {
            "model": request.model,
            "messages": anthropic_messages,
            "max_tokens": request.max_tokens if request.max_tokens is not None else 4096,
            "stream": stream,
        }

        if system_content:
            payload["system"] = "\n\n".join(system_content)
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.top_p is not None:
            payload["top_p"] = request.top_p

        headers = {
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        }
        return payload, headers

    async def chat(
        self, request: ChatRequest, api_key: str, base_url: str | None = None
    ) -> ChatResponse:
        client = get_shared_http_client()
        url = (base_url.rstrip("/") + "/messages") if base_url else ANTHROPIC_API_URL
        payload, headers = self._prepare_payload(request, stream=False)
        headers["x-api-key"] = api_key

        try:
            res = await client.post(url, json=payload, headers=headers)
        except httpx.TimeoutException as e:
            raise ProviderTimeoutError(
                f"Anthropic request timed out: {e}", provider="anthropic"
            ) from e
        except httpx.RequestError as e:
            raise ProviderError(
                f"Network error calling Anthropic: {e}", status_code=502, provider="anthropic"
            ) from e

        if res.is_error:
            raise self._map_error(res.status_code, res.text)

        data = res.json()
        content_text = ""
        for block in data.get("content", []):
            if block.get("type") == "text":
                content_text += block.get("text", "")

        raw_usage = data.get("usage", {})
        prompt_tokens = raw_usage.get("input_tokens")
        completion_tokens = raw_usage.get("output_tokens")
        cached_tokens = raw_usage.get("cache_read_input_tokens", 0)

        usage_estimated = False
        if prompt_tokens is None or completion_tokens is None:
            all_input = " ".join(str(m.get("content", "")) for m in request.messages)
            prompt_tokens = estimate_tokens(all_input)
            completion_tokens = estimate_tokens(content_text)
            usage_estimated = True

        usage = UsageInfo(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            cached_prompt_tokens=cached_tokens,
            usage_estimated=usage_estimated,
        )

        choice = Choice(
            index=0,
            message={"role": "assistant", "content": content_text},
            finish_reason=self._map_finish_reason(data.get("stop_reason")),
        )

        return ChatResponse(
            id=data.get("id", "msg-anthropic"),
            model=data.get("model", request.model),
            choices=[choice],
            usage=usage,
        )

    async def stream_chat(
        self, request: ChatRequest, api_key: str, base_url: str | None = None
    ) -> AsyncIterator[ChatStreamChunk]:
        client = get_shared_http_client()
        url = (base_url.rstrip("/") + "/messages") if base_url else ANTHROPIC_API_URL
        payload, headers = self._prepare_payload(request, stream=True)
        headers["x-api-key"] = api_key

        try:
            req = client.build_request("POST", url, json=payload, headers=headers)
            res = await client.send(req, stream=True)
        except httpx.TimeoutException as e:
            raise ProviderTimeoutError(
                f"Anthropic stream request timed out: {e}", provider="anthropic"
            ) from e
        except httpx.RequestError as e:
            raise ProviderError(
                f"Network error starting Anthropic stream: {e}",
                status_code=502,
                provider="anthropic",
            ) from e

        if res.is_error:
            error_body = await res.aread()
            await res.aclose()
            raise self._map_error(res.status_code, error_body.decode(errors="replace"))

        msg_id = "msg-stream"
        input_tokens = 0
        output_tokens = 0
        cached_tokens = 0
        accumulated_text: list[str] = []

        try:
            async for line in res.aiter_lines():
                if not line or not line.startswith("data: "):
                    continue
                data_str = line[6:].strip()
                try:
                    event = json.loads(data_str)
                except Exception:
                    continue

                event_type = event.get("type")
                if event_type == "message_start":
                    message = event.get("message", {})
                    msg_id = message.get("id", msg_id)
                    raw_usage = message.get("usage", {})
                    input_tokens = raw_usage.get("input_tokens", 0)
                    cached_tokens = raw_usage.get("cache_read_input_tokens", 0)

                    yield ChatStreamChunk(
                        id=msg_id,
                        model=request.model,
                        choices=[StreamChoice(index=0, delta=StreamDelta(role="assistant"))],
                    )

                elif event_type == "content_block_delta":
                    delta = event.get("delta", {})
                    if delta.get("type") == "text_delta":
                        text = delta.get("text", "")
                        accumulated_text.append(text)
                        yield ChatStreamChunk(
                            id=msg_id,
                            model=request.model,
                            choices=[StreamChoice(index=0, delta=StreamDelta(content=text))],
                        )

                elif event_type == "message_delta":
                    delta = event.get("delta", {})
                    stop_reason = self._map_finish_reason(delta.get("stop_reason"))
                    raw_usage = event.get("usage", {})
                    output_tokens = raw_usage.get("output_tokens", 0)

                    usage = UsageInfo(
                        prompt_tokens=input_tokens,
                        completion_tokens=output_tokens,
                        total_tokens=input_tokens + output_tokens,
                        cached_prompt_tokens=cached_tokens,
                        usage_estimated=False,
                    )
                    yield ChatStreamChunk(
                        id=msg_id,
                        model=request.model,
                        choices=[
                            StreamChoice(index=0, delta=StreamDelta(), finish_reason=stop_reason)
                        ],
                        usage=usage,
                    )
        finally:
            await res.aclose()

    async def embeddings(
        self,
        _request: EmbeddingRequest,
        _api_key: str,
        _base_url: str | None = None,
    ) -> EmbeddingResponse:
        raise ProviderBadRequestError(
            "Anthropic does not offer a standalone embeddings API endpoint.", provider="anthropic"
        )
