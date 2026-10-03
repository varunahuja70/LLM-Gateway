from dataclasses import dataclass
from typing import Any

import httpx

from app.providers.base import (
    ProviderBadRequestError,
    ProviderError,
    ProviderOverloadedError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)


@dataclass
class FallbackExecutionMeta:
    """Metadata regarding fallback execution."""

    primary_provider: str
    primary_model: str
    final_provider: str
    final_model: str
    fallback_used: bool = False
    fallback_from: str | None = None
    fallback_reason: str | None = None
    attempts: int = 1


def build_fallback_chain(
    primary_provider: str,
    primary_model: str,
    fallback_chain: list[dict[str, Any]] | None,
    max_fallbacks: int = 2,
    is_embedding: bool = False,
) -> list[tuple[str, str]]:
    """Build an ordered list of (provider, model) candidates to attempt.

    Rules:
    - Primary candidate always goes first.
    - Subsequent entries come from fallback_chain, deduplicated.
    - If is_embedding is True, fallback is allowed only inside the same provider.
    - Chain length does not exceed 1 + max_fallbacks.
    """
    candidates: list[tuple[str, str]] = [(primary_provider.lower(), primary_model)]
    seen = {(primary_provider.lower(), primary_model)}

    if fallback_chain and max_fallbacks > 0:
        for entry in fallback_chain:
            p = str(entry.get("provider", "")).strip().lower()
            m = str(entry.get("model", "")).strip()
            if not p or not m:
                continue

            # Spec: Embeddings fallback only inside the same provider
            if is_embedding and p != primary_provider.lower():
                continue

            candidate = (p, m)
            if candidate not in seen:
                seen.add(candidate)
                candidates.append(candidate)
                if len(candidates) >= 1 + max_fallbacks:
                    break

    return candidates


def is_fallback_trigger(exc: Exception) -> tuple[bool, str]:
    """Check if an exception triggers fallback to the next model.

    Triggers:
    - Timeout (ProviderTimeoutError, httpx.TimeoutException)
    - HTTP 429 Rate limit (ProviderRateLimitError, HTTP 429)
    - HTTP 5xx Server errors (500, 502, 503, 504, etc.)
    - Provider overloaded errors
    - Connection / Network errors

    NEVER triggers:
    - HTTP 400 Bad Request
    - HTTP 401 / 403 Auth errors
    - Other 4xx client errors
    """
    # 400 Bad Request or 4xx (except 429) never triggers fallback
    if isinstance(exc, ProviderBadRequestError):
        return False, "bad_request_400"

    if isinstance(exc, (ProviderTimeoutError, httpx.TimeoutException, TimeoutError)):
        return True, "timeout"

    if isinstance(exc, ProviderRateLimitError):
        return True, "rate_limited_429"

    if isinstance(exc, ProviderOverloadedError):
        return True, "provider_overloaded"

    if isinstance(exc, (httpx.NetworkError, httpx.ConnectError, httpx.RemoteProtocolError)):
        return True, "connection_error"

    if isinstance(exc, httpx.HTTPStatusError):
        status_code = exc.response.status_code
        if status_code == 429:
            return True, "rate_limited_429"
        if status_code >= 500:
            return True, f"status_{status_code}"
        return False, f"client_error_{status_code}"

    if isinstance(exc, ProviderError):
        if 400 <= exc.status_code < 500 and exc.status_code != 429:
            return False, f"client_error_{exc.status_code}"
        if exc.status_code >= 500:
            return True, f"status_{exc.status_code}"

    # Generic string check for "overloaded"
    err_str = str(exc).lower()
    if "overloaded" in err_str:
        return True, "provider_overloaded"

    return False, "unhandled_error"
