import hashlib
import json
import time
import uuid
from collections.abc import AsyncIterator
from typing import Any

import redis.asyncio as aioredis

from app.config import get_settings

# In-memory cache fallback for testing/dev when Redis is unavailable
_in_memory_cache: dict[str, tuple[dict[str, Any], float]] = {}


def clear_cache_for_testing() -> None:
    """Clear in-memory cache entries for tests."""
    _in_memory_cache.clear()


def compute_chat_cache_key(
    project_id: uuid.UUID,
    model: str,
    payload_dict: dict[str, Any],
) -> str:
    """Compute deterministic SHA-256 cache key for chat completion request.

    Includes:
    - project_id (guarantees cross-project isolation)
    - endpoint: "chat"
    - resolved model
    - canonical JSON of messages, tools, tool_choice, and generation params
    """
    canonical_body = {
        "messages": payload_dict.get("messages", []),
        "temperature": payload_dict.get("temperature"),
        "top_p": payload_dict.get("top_p"),
        "max_tokens": payload_dict.get("max_tokens") or payload_dict.get("max_completion_tokens"),
        "tools": payload_dict.get("tools"),
        "tool_choice": payload_dict.get("tool_choice"),
        "stop": payload_dict.get("stop"),
        "presence_penalty": payload_dict.get("presence_penalty"),
        "frequency_penalty": payload_dict.get("frequency_penalty"),
    }
    canonical_json = json.dumps(canonical_body, sort_keys=True, separators=(",", ":"))
    key_src = f"{project_id}:chat:{model}:{canonical_json}"
    return hashlib.sha256(key_src.encode("utf-8")).hexdigest()


def compute_embedding_cache_key(
    project_id: uuid.UUID,
    model: str,
    payload_dict: dict[str, Any],
) -> str:
    """Compute deterministic SHA-256 cache key for embedding request.

    Includes:
    - project_id (guarantees cross-project isolation)
    - endpoint: "embeddings"
    - resolved model
    - canonical JSON of input, dimensions, and encoding format
    """
    canonical_body = {
        "input": payload_dict.get("input"),
        "dimensions": payload_dict.get("dimensions"),
        "encoding_format": payload_dict.get("encoding_format", "float"),
    }
    canonical_json = json.dumps(canonical_body, sort_keys=True, separators=(",", ":"))
    key_src = f"{project_id}:embeddings:{model}:{canonical_json}"
    return hashlib.sha256(key_src.encode("utf-8")).hexdigest()


async def get_cached_response(
    project_id: uuid.UUID,
    cache_key: str,
) -> dict[str, Any] | None:
    """Retrieve cached response if present and not expired."""
    redis_key = f"cache:{project_id}:{cache_key}"
    settings = get_settings()

    if settings.ENV != "test":
        try:
            r = aioredis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=0.1,
                socket_timeout=0.1,
            )
            raw = await r.get(redis_key)
            await r.close()
            if raw:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    return parsed
        except Exception:
            pass

    # In-memory fallback
    now = time.time()
    entry = _in_memory_cache.get(redis_key)
    if entry:
        data, expires_at = entry
        if now < expires_at:
            return data
        _in_memory_cache.pop(redis_key, None)

    return None


async def set_cached_response(
    project_id: uuid.UUID,
    cache_key: str,
    data: dict[str, Any],
    ttl_seconds: int = 3600,
) -> None:
    """Store response in cache with given TTL."""
    if ttl_seconds <= 0:
        return

    redis_key = f"cache:{project_id}:{cache_key}"
    settings = get_settings()
    now = time.time()

    if settings.ENV != "test":
        try:
            r = aioredis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=0.1,
                socket_timeout=0.1,
            )
            await r.set(redis_key, json.dumps(data), ex=ttl_seconds)
            await r.close()
            return
        except Exception:
            pass

    # In-memory fallback
    _in_memory_cache[redis_key] = (data, now + ttl_seconds)


async def replay_cached_stream(
    cached_data: dict[str, Any],
) -> AsyncIterator[str]:
    """Replay an assembled chat completion response as an SSE stream."""
    req_id = cached_data.get("id", f"chatcmpl-cached-{int(time.time() * 1000)}")
    model = cached_data.get("model", "cached-model")
    created = cached_data.get("created", int(time.time()))
    choices = cached_data.get("choices", [])
    usage = cached_data.get("usage", {})

    content = ""
    finish_reason = "stop"
    if choices:
        c0 = choices[0]
        finish_reason = c0.get("finish_reason", "stop")
        msg = c0.get("message", {})
        if isinstance(msg, dict):
            content = msg.get("content") or ""

    # 1. Role chunk
    role_chunk = {
        "id": req_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [
            {
                "index": 0,
                "delta": {"role": "assistant"},
                "finish_reason": None,
            }
        ],
    }
    yield f"data: {json.dumps(role_chunk)}\n\n"

    # 2. Content chunk(s)
    words = content.split(" ")
    for i, word in enumerate(words):
        chunk_text = word if i == 0 else f" {word}"
        content_chunk = {
            "id": req_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "delta": {"content": chunk_text},
                    "finish_reason": None,
                }
            ],
        }
        yield f"data: {json.dumps(content_chunk)}\n\n"

    # 3. Final chunk with finish reason and usage
    final_chunk: dict[str, Any] = {
        "id": req_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [
            {
                "index": 0,
                "delta": {},
                "finish_reason": finish_reason,
            }
        ],
    }
    if usage:
        final_chunk["usage"] = usage

    yield f"data: {json.dumps(final_chunk)}\n\n"
    yield "data: [DONE]\n\n"
