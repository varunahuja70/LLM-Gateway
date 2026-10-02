from collections.abc import AsyncIterator

from app.providers.base import (
    ChatRequest,
    ChatResponse,
    ChatStreamChunk,
    EmbeddingRequest,
    EmbeddingResponse,
    ProviderBadRequestError,
)
from app.providers.openai import OpenAIAdapter


class OpenAICompatibleAdapter(OpenAIAdapter):
    """Adapter for OpenAI-compatible providers (e.g. vLLM, Ollama, Together, Groq, Fireworks)."""

    def __init__(self) -> None:
        super().__init__(default_base_url="")

    def _get_base_url(self, override: str | None = None) -> str:
        if not override or not override.strip():
            raise ProviderBadRequestError(
                "openai_compatible provider requires an explicit base_url configured on the credential.",
                provider="openai_compatible",
            )
        return override.rstrip("/")

    async def chat(
        self, request: ChatRequest, api_key: str, base_url: str | None = None
    ) -> ChatResponse:
        return await super().chat(request, api_key, base_url=base_url)

    async def stream_chat(
        self, request: ChatRequest, api_key: str, base_url: str | None = None
    ) -> AsyncIterator[ChatStreamChunk]:
        async for chunk in super().stream_chat(request, api_key, base_url=base_url):
            yield chunk

    async def embeddings(
        self, request: EmbeddingRequest, api_key: str, base_url: str | None = None
    ) -> EmbeddingResponse:
        return await super().embeddings(request, api_key, base_url=base_url)
