import time
from collections.abc import AsyncIterator

from app.providers.base import (
    ChatRequest,
    ChatResponse,
    ChatStreamChunk,
    Choice,
    EmbeddingItem,
    EmbeddingRequest,
    EmbeddingResponse,
    ProviderAdapter,
    ProviderError,
    ProviderOverloadedError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    StreamChoice,
    StreamDelta,
    UsageInfo,
    estimate_tokens,
)


class MockProviderAdapter(ProviderAdapter):
    """Deterministic mock provider that simulates realistic LLM behavior.

    Supports failure simulation on demand via the header `X-Mock-Fail: 500|429|timeout`.
    """

    def _check_fail_on_demand(self, request: ChatRequest) -> None:
        fail_mode = request.extra_headers.get("x-mock-fail") or request.extra_headers.get(
            "X-Mock-Fail"
        )
        if not fail_mode:
            return

        mode = fail_mode.lower().strip()
        if mode in ("500", "503", "error"):
            raise ProviderOverloadedError("Mock provider simulated 503 error.", provider="mock")
        if mode == "429":
            raise ProviderRateLimitError(
                "Mock provider simulated 429 rate limit exceeded.", provider="mock"
            )
        if mode == "timeout":
            raise ProviderTimeoutError(
                "Mock provider simulated gateway request timeout.", provider="mock"
            )
        raise ProviderError(
            f"Mock provider simulated generic error: {mode}", status_code=500, provider="mock"
        )

    async def chat(
        self, request: ChatRequest, api_key: str, base_url: str | None = None
    ) -> ChatResponse:
        self._check_fail_on_demand(request)
        _ = (api_key, base_url)

        # Deterministic generation
        last_message = request.messages[-1].get("content", "") if request.messages else "Hello"
        content = f"Mock response to: {last_message}"

        all_input_text = " ".join(
            str(m.get("content", "")) for m in request.messages if m.get("content")
        )
        prompt_tokens = estimate_tokens(all_input_text)
        completion_tokens = estimate_tokens(content)

        return ChatResponse(
            id=f"chatcmpl-mock-{int(time.time() * 1000)}",
            model=request.model,
            choices=[
                Choice(
                    index=0,
                    message={"role": "assistant", "content": content},
                    finish_reason="stop",
                )
            ],
            usage=UsageInfo(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
                cached_prompt_tokens=0,
                usage_estimated=False,
            ),
        )

    async def stream_chat(
        self, request: ChatRequest, api_key: str, base_url: str | None = None
    ) -> AsyncIterator[ChatStreamChunk]:
        self._check_fail_on_demand(request)
        _ = (api_key, base_url)

        last_message = request.messages[-1].get("content", "") if request.messages else "Hello"
        content = f"Mock response to: {last_message}"
        tokens = content.split(" ")

        req_id = f"chatcmpl-mock-stream-{int(time.time() * 1000)}"
        all_input_text = " ".join(
            str(m.get("content", "")) for m in request.messages if m.get("content")
        )
        prompt_tokens = estimate_tokens(all_input_text)
        completion_tokens = estimate_tokens(content)

        # First chunk: role
        yield ChatStreamChunk(
            id=req_id,
            model=request.model,
            choices=[StreamChoice(index=0, delta=StreamDelta(role="assistant"))],
        )

        # Content chunks
        for i, word in enumerate(tokens):
            delta_text = word if i == 0 else f" {word}"
            yield ChatStreamChunk(
                id=req_id,
                model=request.model,
                choices=[StreamChoice(index=0, delta=StreamDelta(content=delta_text))],
            )

        # Final chunk with finish_reason and usage
        yield ChatStreamChunk(
            id=req_id,
            model=request.model,
            choices=[StreamChoice(index=0, delta=StreamDelta(), finish_reason="stop")],
            usage=UsageInfo(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
                cached_prompt_tokens=0,
                usage_estimated=False,
            ),
        )

    async def embeddings(
        self, request: EmbeddingRequest, api_key: str, base_url: str | None = None
    ) -> EmbeddingResponse:
        _ = (api_key, base_url)
        inputs = [request.input] if isinstance(request.input, str) else request.input
        items: list[EmbeddingItem] = []
        total_prompt_tokens = 0

        for i, text in enumerate(inputs):
            # Deterministic pseudo-embedding of 1536 floats
            token_count = estimate_tokens(text)
            total_prompt_tokens += token_count
            val = (hash(text) % 1000) / 1000.0
            vector = [val] * 1536
            items.append(EmbeddingItem(index=i, embedding=vector))

        return EmbeddingResponse(
            model=request.model,
            data=items,
            usage=UsageInfo(
                prompt_tokens=total_prompt_tokens,
                completion_tokens=0,
                total_tokens=total_prompt_tokens,
                usage_estimated=False,
            ),
        )
