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

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"


class GoogleGeminiAdapter(ProviderAdapter):
    """Google Gemini REST API adapter translating to/from OpenAI shapes."""

    def _map_finish_reason(self, finish_reason: str | None) -> str | None:
        if not finish_reason:
            return None
        mapping = {
            "STOP": "stop",
            "MAX_TOKENS": "length",
            "SAFETY": "content_filter",
            "RECITATION": "content_filter",
        }
        return mapping.get(finish_reason, finish_reason.lower())

    def _map_error(self, status_code: int, response_text: str) -> ProviderError:
        message = response_text
        code: str | None = None
        try:
            err_json = json.loads(response_text)
            if "error" in err_json:
                message = err_json["error"].get("message", response_text)
                code = err_json["error"].get("status")
        except Exception:
            pass

        if status_code in (400, 403) and ("API_KEY" in message or "KEY_INVALID" in message):
            return ProviderAuthError(f"Gemini API key error: {message}", provider="google")
        if status_code == 429 or "RESOURCE_EXHAUSTED" in str(code):
            return ProviderRateLimitError(f"Gemini quota exceeded: {message}", provider="google")
        if status_code in (500, 503, 502):
            return ProviderOverloadedError(
                f"Gemini provider error ({status_code}): {message}", provider="google"
            )
        if status_code == 400:
            return ProviderBadRequestError(
                f"Gemini bad request: {message}", provider="google", code=code
            )
        return ProviderError(
            f"Gemini error ({status_code}): {message}",
            status_code=status_code,
            provider="google",
            code=code,
        )

    def _prepare_payload(self, request: ChatRequest) -> dict[str, Any]:
        contents: list[dict[str, Any]] = []
        system_text: list[str] = []

        for msg in request.messages:
            role = msg.get("role", "")
            content = str(msg.get("content", "")) if msg.get("content") is not None else ""
            if role == "system":
                if content:
                    system_text.append(content)
            elif role == "user":
                contents.append({"role": "user", "parts": [{"text": content}]})
            elif role == "assistant":
                contents.append({"role": "model", "parts": [{"text": content}]})

        payload: dict[str, Any] = {"contents": contents}

        if system_text:
            payload["systemInstruction"] = {"parts": [{"text": "\n\n".join(system_text)}]}

        gen_config: dict[str, Any] = {}
        if request.temperature is not None:
            gen_config["temperature"] = request.temperature
        if request.max_tokens is not None:
            gen_config["maxOutputTokens"] = request.max_tokens
        if request.top_p is not None:
            gen_config["topP"] = request.top_p

        if gen_config:
            payload["generationConfig"] = gen_config

        return payload

    async def chat(
        self, request: ChatRequest, api_key: str, base_url: str | None = None
    ) -> ChatResponse:
        client = get_shared_http_client()
        base = base_url.rstrip("/") if base_url else GEMINI_BASE_URL
        url = f"{base}/models/{request.model}:generateContent?key={api_key}"
        payload = self._prepare_payload(request)

        try:
            res = await client.post(url, json=payload, headers={"Content-Type": "application/json"})
        except httpx.TimeoutException as e:
            raise ProviderTimeoutError(f"Gemini request timed out: {e}", provider="google") from e
        except httpx.RequestError as e:
            raise ProviderError(
                f"Network error calling Gemini: {e}", status_code=502, provider="google"
            ) from e

        if res.is_error:
            raise self._map_error(res.status_code, res.text)

        data = res.json()
        candidates = data.get("candidates", [])
        content_text = ""
        finish_reason = "stop"

        if candidates:
            first_c = candidates[0]
            parts = first_c.get("content", {}).get("parts", [])
            content_text = "".join(p.get("text", "") for p in parts)
            finish_reason = self._map_finish_reason(first_c.get("finishReason")) or "stop"

        meta = data.get("usageMetadata", {})
        prompt_tokens = meta.get("promptTokenCount")
        completion_tokens = meta.get("candidatesTokenCount")
        cached_tokens = meta.get("cachedContentTokenCount", 0)

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
            finish_reason=finish_reason,
        )

        return ChatResponse(
            id=f"gemini-{hash(content_text) & 0x7FFFFFFF}",
            model=request.model,
            choices=[choice],
            usage=usage,
        )

    async def stream_chat(
        self, request: ChatRequest, api_key: str, base_url: str | None = None
    ) -> AsyncIterator[ChatStreamChunk]:
        client = get_shared_http_client()
        base = base_url.rstrip("/") if base_url else GEMINI_BASE_URL
        url = f"{base}/models/{request.model}:streamGenerateContent?alt=sse&key={api_key}"
        payload = self._prepare_payload(request)

        try:
            req = client.build_request(
                "POST", url, json=payload, headers={"Content-Type": "application/json"}
            )
            res = await client.send(req, stream=True)
        except httpx.TimeoutException as e:
            raise ProviderTimeoutError(
                f"Gemini streaming request timed out: {e}", provider="google"
            ) from e
        except httpx.RequestError as e:
            raise ProviderError(
                f"Network error starting Gemini stream: {e}", status_code=502, provider="google"
            ) from e

        if res.is_error:
            error_body = await res.aread()
            await res.aclose()
            raise self._map_error(res.status_code, error_body.decode(errors="replace"))

        chunk_id = "gemini-stream"
        accumulated_text: list[str] = []
        last_usage: UsageInfo | None = None

        try:
            async for line in res.aiter_lines():
                if not line or not line.startswith("data: "):
                    continue
                data_str = line[6:].strip()
                try:
                    event = json.loads(data_str)
                except Exception:
                    continue

                candidates = event.get("candidates", [])
                delta_text = ""
                finish_reason = None
                if candidates:
                    first_c = candidates[0]
                    parts = first_c.get("content", {}).get("parts", [])
                    delta_text = "".join(p.get("text", "") for p in parts)
                    if delta_text:
                        accumulated_text.append(delta_text)
                    finish_reason = self._map_finish_reason(first_c.get("finishReason"))

                parsed_usage = None
                meta = event.get("usageMetadata")
                if meta:
                    p_tok = meta.get("promptTokenCount", 0)
                    c_tok = meta.get("candidatesTokenCount", 0)
                    parsed_usage = UsageInfo(
                        prompt_tokens=p_tok,
                        completion_tokens=c_tok,
                        total_tokens=p_tok + c_tok,
                        cached_prompt_tokens=meta.get("cachedContentTokenCount", 0),
                        usage_estimated=False,
                    )
                    last_usage = parsed_usage

                yield ChatStreamChunk(
                    id=chunk_id,
                    model=request.model,
                    choices=[
                        StreamChoice(
                            index=0,
                            delta=StreamDelta(content=delta_text),
                            finish_reason=finish_reason,
                        )
                    ],
                    usage=parsed_usage,
                )
        finally:
            await res.aclose()

        # If usage metadata was missing, emit estimated usage
        if last_usage is None:
            all_input = " ".join(str(m.get("content", "")) for m in request.messages)
            all_output = "".join(accumulated_text)
            p_est = estimate_tokens(all_input)
            c_est = estimate_tokens(all_output)
            yield ChatStreamChunk(
                id=chunk_id,
                model=request.model,
                choices=[],
                usage=UsageInfo(
                    prompt_tokens=p_est,
                    completion_tokens=c_est,
                    total_tokens=p_est + c_est,
                    usage_estimated=True,
                ),
            )

    async def embeddings(
        self, request: EmbeddingRequest, api_key: str, base_url: str | None = None
    ) -> EmbeddingResponse:
        client = get_shared_http_client()
        base = base_url.rstrip("/") if base_url else GEMINI_BASE_URL
        url = f"{base}/models/{request.model}:embedContent?key={api_key}"

        text = request.input if isinstance(request.input, str) else " ".join(request.input)
        payload = {"content": {"parts": [{"text": text}]}}

        try:
            res = await client.post(url, json=payload)
        except Exception as e:
            raise ProviderError(f"Gemini embedding error: {e}", provider="google") from e

        if res.is_error:
            raise self._map_error(res.status_code, res.text)

        data = res.json()
        values = data.get("embedding", {}).get("values", [])
        return EmbeddingResponse(
            model=request.model,
            data=[EmbeddingItem(index=0, embedding=values)],
            usage=UsageInfo(
                prompt_tokens=estimate_tokens(text),
                completion_tokens=0,
                total_tokens=estimate_tokens(text),
            ),
        )
