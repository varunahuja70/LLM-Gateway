import time
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

import httpx
import tiktoken

# Shared persistent HTTP client with pooling and standard timeouts
_shared_client: httpx.AsyncClient | None = None


def get_shared_http_client() -> httpx.AsyncClient:
    global _shared_client
    if _shared_client is None or _shared_client.is_closed:
        limits = httpx.Limits(max_keepalive_connections=100, max_connections=200)
        timeout = httpx.Timeout(connect=5.0, read=60.0, write=10.0, pool=5.0)
        _shared_client = httpx.AsyncClient(limits=limits, timeout=timeout)
    return _shared_client


async def close_shared_http_client() -> None:
    global _shared_client
    if _shared_client is not None and not _shared_client.is_closed:
        await _shared_client.aclose()
        _shared_client = None


def estimate_tokens(text: str) -> int:
    """Fallback token estimation using tiktoken."""
    try:
        encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))
    except Exception:
        # Fallback heuristic: approx 4 chars per token
        return max(1, len(text) // 4)


class ProviderError(Exception):
    """Base exception for upstream provider errors."""

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        provider: str = "unknown",
        error_type: str = "provider_error",
        code: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.provider = provider
        self.error_type = error_type
        self.code = code


class ProviderAuthError(ProviderError):
    def __init__(self, message: str, provider: str = "unknown") -> None:
        super().__init__(
            message,
            status_code=401,
            provider=provider,
            error_type="invalid_request_error",
            code="invalid_api_key",
        )


class ProviderRateLimitError(ProviderError):
    def __init__(self, message: str, provider: str = "unknown") -> None:
        super().__init__(
            message,
            status_code=429,
            provider=provider,
            error_type="requests",
            code="rate_limit_exceeded",
        )


class ProviderTimeoutError(ProviderError):
    def __init__(self, message: str, provider: str = "unknown") -> None:
        super().__init__(
            message, status_code=504, provider=provider, error_type="timeout", code="timeout"
        )


class ProviderOverloadedError(ProviderError):
    def __init__(self, message: str, provider: str = "unknown") -> None:
        super().__init__(
            message,
            status_code=503,
            provider=provider,
            error_type="overloaded",
            code="provider_overloaded",
        )


class ProviderBadRequestError(ProviderError):
    def __init__(self, message: str, provider: str = "unknown", code: str | None = None) -> None:
        super().__init__(
            message,
            status_code=400,
            provider=provider,
            error_type="invalid_request_error",
            code=code,
        )


@dataclass
class UsageInfo:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cached_prompt_tokens: int = 0
    usage_estimated: bool = False


@dataclass
class ChatMessage:
    role: str
    content: str | None = None
    name: str | None = None
    tool_calls: list[dict[str, Any]] | None = None


@dataclass
class ChatRequest:
    model: str
    messages: list[dict[str, Any]]
    stream: bool = False
    temperature: float | None = None
    max_tokens: int | None = None
    top_p: float | None = None
    tools: list[dict[str, Any]] | None = None
    tool_choice: Any | None = None
    extra_headers: dict[str, str] = field(default_factory=dict)


@dataclass
class Choice:
    index: int
    message: dict[str, Any]
    finish_reason: str | None = "stop"


@dataclass
class ChatResponse:
    id: str
    model: str
    choices: list[Choice]
    usage: UsageInfo
    created: int = field(default_factory=lambda: int(time.time()))
    system_fingerprint: str | None = None


@dataclass
class StreamDelta:
    role: str | None = None
    content: str | None = None
    tool_calls: list[dict[str, Any]] | None = None


@dataclass
class StreamChoice:
    index: int
    delta: StreamDelta
    finish_reason: str | None = None


@dataclass
class ChatStreamChunk:
    id: str
    model: str
    choices: list[StreamChoice]
    usage: UsageInfo | None = None
    created: int = field(default_factory=lambda: int(time.time()))


@dataclass
class EmbeddingRequest:
    model: str
    input: str | list[str]
    extra_headers: dict[str, str] = field(default_factory=dict)


@dataclass
class EmbeddingItem:
    index: int
    embedding: list[float]


@dataclass
class EmbeddingResponse:
    model: str
    data: list[EmbeddingItem]
    usage: UsageInfo


class ProviderAdapter(ABC):
    """Abstract base class for model provider adapters."""

    @abstractmethod
    async def chat(
        self, request: ChatRequest, api_key: str, base_url: str | None = None
    ) -> ChatResponse:
        """Execute a non-streaming chat completion request."""

    @abstractmethod
    def stream_chat(
        self, request: ChatRequest, api_key: str, base_url: str | None = None
    ) -> AsyncIterator[ChatStreamChunk]:
        """Execute a streaming chat completion request."""

    @abstractmethod
    async def embeddings(
        self, request: EmbeddingRequest, api_key: str, base_url: str | None = None
    ) -> EmbeddingResponse:
        """Execute an embedding request."""
