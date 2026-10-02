import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.providers.base import (
    ChatRequest,
    ChatResponse,
    ChatStreamChunk,
    Choice,
    EmbeddingItem,
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


class OpenAIAdapter(ProviderAdapter):
    """OpenAI API adapter using official chat completions and embeddings specs."""

    def __init__(self, default_base_url: str = "https://api.openai.com/v1") -> None:
        self.default_base_url = default_base_url.rstrip("/")

    def _get_base_url(self, override: str | None = None) -> str:
        if override and override.strip():
            return override.rstrip("/")
        return self.default_base_url

    def _map_error(
        self, status_code: int, response_text: str, provider_name: str = "openai"
    ) -> ProviderError:
        message = response_text
        code: str | None = None
        try:
            err_json = json.loads(response_text)
            if "error" in err_json:
                message = err_json["error"].get("message", response_text)
                code = err_json["error"].get("code")
        except Exception:
            pass

        if status_code == 401:
            return ProviderAuthError(f"Authentication failed: {message}", provider=provider_name)
        if status_code == 429:
            return ProviderRateLimitError(f"Rate limit exceeded: {message}", provider=provider_name)
        if status_code in (500, 502, 503, 504):
            return ProviderOverloadedError(
                f"Provider error ({status_code}): {message}", provider=provider_name
            )
        if status_code == 400:
            return ProviderBadRequestError(
                f"Bad request: {message}", provider=provider_name, code=code
            )
        return ProviderError(
            f"API error ({status_code}): {message}",
            status_code=status_code,
            provider=provider_name,
            code=code,
        )

    def _parse_usage(
        self, usage_data: dict[str, Any] | None, fallback_prompt: str, fallback_completion: str
    ) -> UsageInfo:
        if usage_data:
            p_tokens = usage_data.get("prompt_tokens", 0)
            c_tokens = usage_data.get("completion_tokens", 0)
            t_tokens = usage_data.get("total_tokens", p_tokens + c_tokens)
            cached_tokens = 0
            details = usage_data.get("prompt_tokens_details")
            if isinstance(details, dict):
                cached_tokens = details.get("cached_tokens", 0)
            return UsageInfo(
                prompt_tokens=p_tokens,
                completion_tokens=c_tokens,
                total_tokens=t_tokens,
                cached_prompt_tokens=cached_tokens,
                usage_estimated=False,
            )
        # Fallback estimation using tiktoken
        p_est = estimate_tokens(fallback_prompt)
        c_est = estimate_tokens(fallback_completion)
        return UsageInfo(
            prompt_tokens=p_est,
            completion_tokens=c_est,
            total_tokens=p_est + c_est,
            cached_prompt_tokens=0,
            usage_estimated=True,
        )

    async def chat(
        self, request: ChatRequest, api_key: str, base_url: str | None = None
    ) -> ChatResponse:
        client = get_shared_http_client()
        url = f"{self._get_base_url(base_url)}/chat/completions"

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        payload: dict[str, Any] = {
            "model": request.model,
            "messages": request.messages,
            "stream": False,
        }
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens
        if request.top_p is not None:
            payload["top_p"] = request.top_p
        if request.tools is not None:
            payload["tools"] = request.tools
        if request.tool_choice is not None:
            payload["tool_choice"] = request.tool_choice

        try:
            res = await client.post(url, json=payload, headers=headers)
        except httpx.TimeoutException as e:
            raise ProviderTimeoutError(
                f"Request to OpenAI timed out: {e}", provider="openai"
            ) from e
        except httpx.RequestError as e:
            raise ProviderError(
                f"Network error calling OpenAI: {e}", status_code=502, provider="openai"
            ) from e

        if res.is_error:
            raise self._map_error(res.status_code, res.text, provider_name="openai")

        data = res.json()
        choices = [
            Choice(
                index=c["index"],
                message=c["message"],
                finish_reason=c.get("finish_reason", "stop"),
            )
            for c in data.get("choices", [])
        ]

        prompt_str = " ".join(str(m.get("content", "")) for m in request.messages)
        completion_str = "".join(str(c.message.get("content", "")) for c in choices)
        usage = self._parse_usage(data.get("usage"), prompt_str, completion_str)

        return ChatResponse(
            id=data.get("id", "chatcmpl-unknown"),
            model=data.get("model", request.model),
            choices=choices,
            usage=usage,
            created=data.get("created", 0),
            system_fingerprint=data.get("system_fingerprint"),
        )

    async def stream_chat(
        self, request: ChatRequest, api_key: str, base_url: str | None = None
    ) -> AsyncIterator[ChatStreamChunk]:
        client = get_shared_http_client()
        url = f"{self._get_base_url(base_url)}/chat/completions"

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        payload: dict[str, Any] = {
            "model": request.model,
            "messages": request.messages,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens
        if request.top_p is not None:
            payload["top_p"] = request.top_p
        if request.tools is not None:
            payload["tools"] = request.tools
        if request.tool_choice is not None:
            payload["tool_choice"] = request.tool_choice

        try:
            req = client.build_request("POST", url, json=payload, headers=headers)
            res = await client.send(req, stream=True)
        except httpx.TimeoutException as e:
            raise ProviderTimeoutError(
                f"Streaming request to OpenAI timed out: {e}", provider="openai"
            ) from e
        except httpx.RequestError as e:
            raise ProviderError(
                f"Network error initiating stream to OpenAI: {e}",
                status_code=502,
                provider="openai",
            ) from e

        if res.is_error:
            error_body = await res.aread()
            await res.aclose()
            raise self._map_error(
                res.status_code, error_body.decode(errors="replace"), provider_name="openai"
            )

        accumulated_content: list[str] = []
        usage_found: UsageInfo | None = None

        try:
            async for line in res.aiter_lines():
                if not line or not line.startswith("data: "):
                    continue
                data_str = line[6:].strip()
                if data_str == "[DONE]":
                    break

                try:
                    chunk_json = json.loads(data_str)
                except Exception:
                    continue

                raw_usage = chunk_json.get("usage")
                parsed_usage = None
                if raw_usage:
                    parsed_usage = self._parse_usage(raw_usage, "", "")
                    usage_found = parsed_usage

                choices = []
                for c in chunk_json.get("choices", []):
                    delta_raw = c.get("delta", {})
                    content_piece = delta_raw.get("content")
                    if content_piece:
                        accumulated_content.append(content_piece)

                    choices.append(
                        StreamChoice(
                            index=c.get("index", 0),
                            delta=StreamDelta(
                                role=delta_raw.get("role"),
                                content=content_piece,
                                tool_calls=delta_raw.get("tool_calls"),
                            ),
                            finish_reason=c.get("finish_reason"),
                        )
                    )

                yield ChatStreamChunk(
                    id=chunk_json.get("id", "chatcmpl-stream"),
                    model=chunk_json.get("model", request.model),
                    choices=choices,
                    usage=parsed_usage,
                    created=chunk_json.get("created", 0),
                )
        finally:
            await res.aclose()

        # If usage was not provided in stream, yield an estimate chunk if not emitted
        if usage_found is None:
            prompt_str = " ".join(str(m.get("content", "")) for m in request.messages)
            completion_str = "".join(accumulated_content)
            fallback_usage = self._parse_usage(None, prompt_str, completion_str)
            yield ChatStreamChunk(
                id="chatcmpl-stream-usage",
                model=request.model,
                choices=[],
                usage=fallback_usage,
            )

    async def embeddings(
        self, request: EmbeddingRequest, api_key: str, base_url: str | None = None
    ) -> EmbeddingResponse:
        client = get_shared_http_client()
        url = f"{self._get_base_url(base_url)}/embeddings"

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {"model": request.model, "input": request.input}

        try:
            res = await client.post(url, json=payload, headers=headers)
        except httpx.TimeoutException as e:
            raise ProviderTimeoutError(
                f"Embedding request to OpenAI timed out: {e}", provider="openai"
            ) from e
        except httpx.RequestError as e:
            raise ProviderError(
                f"Network error calling OpenAI embeddings: {e}", status_code=502, provider="openai"
            ) from e

        if res.is_error:
            raise self._map_error(res.status_code, res.text, provider_name="openai")

        data = res.json()
        items = [
            EmbeddingItem(index=item["index"], embedding=item["embedding"])
            for item in data.get("data", [])
        ]
        prompt_str = (
            " ".join(request.input) if isinstance(request.input, list) else str(request.input)
        )
        usage = self._parse_usage(data.get("usage"), prompt_str, "")

        return EmbeddingResponse(
            model=data.get("model", request.model),
            data=items,
            usage=usage,
        )
