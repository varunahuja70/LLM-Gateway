import pytest
import respx
from httpx import Response

from app.providers.anthropic import AnthropicAdapter
from app.providers.base import (
    ChatRequest,
    EmbeddingRequest,
    ProviderAuthError,
    ProviderOverloadedError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)
from app.providers.google import GoogleGeminiAdapter
from app.providers.mock import MockProviderAdapter
from app.providers.openai import OpenAIAdapter
from app.providers.openai_compatible import OpenAICompatibleAdapter
from app.providers.registry import get_adapter


# -----------------------------------------------------------------------------
# 1. Mock Provider Tests
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_mock_provider_chat_and_stream() -> None:
    adapter = MockProviderAdapter()

    req = ChatRequest(
        model="mock-model",
        messages=[{"role": "user", "content": "What is the capital of France?"}],
    )

    # 1. Non-streaming
    res = await adapter.chat(req, api_key="mock-key")
    assert res.choices[0].message["role"] == "assistant"
    assert "Mock response to:" in res.choices[0].message["content"]
    assert res.usage.prompt_tokens > 0
    assert res.usage.completion_tokens > 0
    assert not res.usage.usage_estimated

    # 2. Streaming
    req_stream = ChatRequest(
        model="mock-model",
        messages=[{"role": "user", "content": "Hello stream"}],
        stream=True,
    )
    chunks = []
    async for chunk in adapter.stream_chat(req_stream, api_key="mock-key"):
        chunks.append(chunk)

    assert len(chunks) >= 3
    assert chunks[0].choices[0].delta.role == "assistant"
    # Final chunk has usage
    assert chunks[-1].usage is not None
    assert chunks[-1].choices[0].finish_reason == "stop"


@pytest.mark.asyncio
async def test_mock_provider_fail_on_demand() -> None:
    adapter = MockProviderAdapter()

    # 500 error
    with pytest.raises(ProviderOverloadedError):
        await adapter.chat(
            ChatRequest(
                model="mock",
                messages=[{"role": "user", "content": "test"}],
                extra_headers={"X-Mock-Fail": "500"},
            ),
            api_key="mock",
        )

    # 429 rate limit
    with pytest.raises(ProviderRateLimitError):
        await adapter.chat(
            ChatRequest(
                model="mock",
                messages=[{"role": "user", "content": "test"}],
                extra_headers={"X-Mock-Fail": "429"},
            ),
            api_key="mock",
        )

    # timeout
    with pytest.raises(ProviderTimeoutError):
        await adapter.chat(
            ChatRequest(
                model="mock",
                messages=[{"role": "user", "content": "test"}],
                extra_headers={"X-Mock-Fail": "timeout"},
            ),
            api_key="mock",
        )


@pytest.mark.asyncio
async def test_mock_provider_embeddings() -> None:
    adapter = MockProviderAdapter()
    res = await adapter.embeddings(
        EmbeddingRequest(model="mock-embed", input=["Hello world", "Foo bar"]),
        api_key="mock",
    )
    assert len(res.data) == 2
    assert len(res.data[0].embedding) == 1536
    assert res.usage.prompt_tokens > 0


# -----------------------------------------------------------------------------
# 2. OpenAI Provider Tests
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
@respx.mock
async def test_openai_adapter_non_streaming_and_usage() -> None:
    adapter = OpenAIAdapter()
    respx.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=Response(
            200,
            json={
                "id": "chatcmpl-123",
                "model": "gpt-5-mini",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "Hello there!"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 15,
                    "completion_tokens": 5,
                    "total_tokens": 20,
                    "prompt_tokens_details": {"cached_tokens": 8},
                },
            },
        )
    )

    req = ChatRequest(model="gpt-5-mini", messages=[{"role": "user", "content": "Hello"}])
    res = await adapter.chat(req, api_key="sk-test-key")

    assert res.id == "chatcmpl-123"
    assert res.choices[0].message["content"] == "Hello there!"
    assert res.usage.prompt_tokens == 15
    assert res.usage.completion_tokens == 5
    assert res.usage.cached_prompt_tokens == 8
    assert not res.usage.usage_estimated


@pytest.mark.asyncio
@respx.mock
async def test_openai_adapter_streaming() -> None:
    adapter = OpenAIAdapter()
    stream_content = (
        'data: {"id":"c-1","choices":[{"index":0,"delta":{"role":"assistant"},"finish_reason":null}]}\n\n'
        'data: {"id":"c-1","choices":[{"index":0,"delta":{"content":"Hi"},"finish_reason":null}]}\n\n'
        'data: {"id":"c-1","choices":[{"index":0,"delta":{},"finish_reason":"stop"}],"usage":{"prompt_tokens":10,"completion_tokens":2,"total_tokens":12}}\n\n'
        "data: [DONE]\n\n"
    )
    respx.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=Response(200, text=stream_content)
    )

    req = ChatRequest(
        model="gpt-5-mini", messages=[{"role": "user", "content": "Hello"}], stream=True
    )
    chunks = []
    async for chunk in adapter.stream_chat(req, api_key="sk-test-key"):
        chunks.append(chunk)

    assert len(chunks) == 3
    assert chunks[1].choices[0].delta.content == "Hi"
    assert chunks[2].choices[0].finish_reason == "stop"
    assert chunks[2].usage is not None
    assert chunks[2].usage.total_tokens == 12


@pytest.mark.asyncio
@respx.mock
async def test_openai_adapter_error_mapping_and_missing_usage_fallback() -> None:
    adapter = OpenAIAdapter()

    # 401 Auth error
    respx.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=Response(401, json={"error": {"message": "Invalid API key"}})
    )
    with pytest.raises(ProviderAuthError):
        await adapter.chat(
            ChatRequest(model="gpt-5", messages=[{"role": "user", "content": "hi"}]),
            api_key="bad-key",
        )

    # 429 Rate limit
    respx.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=Response(429, json={"error": {"message": "Rate limit exceeded"}})
    )
    with pytest.raises(ProviderRateLimitError):
        await adapter.chat(
            ChatRequest(model="gpt-5", messages=[{"role": "user", "content": "hi"}]),
            api_key="test-key",
        )

    # Missing usage fallback: estimates with tiktoken
    respx.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=Response(
            200,
            json={
                "id": "c-nousage",
                "model": "gpt-5",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "Response text here"},
                        "finish_reason": "stop",
                    }
                ],
                # No usage key provided!
            },
        )
    )
    res_no_usage = await adapter.chat(
        ChatRequest(model="gpt-5", messages=[{"role": "user", "content": "Prompt text here"}]),
        api_key="test-key",
    )
    assert res_no_usage.usage.usage_estimated is True
    assert res_no_usage.usage.prompt_tokens > 0
    assert res_no_usage.usage.completion_tokens > 0


# -----------------------------------------------------------------------------
# 3. OpenAI-Compatible Provider Tests
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
@respx.mock
async def test_openai_compatible_adapter_custom_base_url() -> None:
    adapter = OpenAICompatibleAdapter()
    custom_url = "https://my-vllm-cluster.internal/v1"

    respx.post(f"{custom_url}/chat/completions").mock(
        return_value=Response(
            200,
            json={
                "id": "vllm-1",
                "model": "llama-3-70b",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "vLLM answer"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 8, "completion_tokens": 4, "total_tokens": 12},
            },
        )
    )

    req = ChatRequest(model="llama-3-70b", messages=[{"role": "user", "content": "test"}])
    res = await adapter.chat(req, api_key="any-key", base_url=custom_url)
    assert res.choices[0].message["content"] == "vLLM answer"
    assert res.usage.total_tokens == 12


# -----------------------------------------------------------------------------
# 4. Anthropic Provider Tests
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
@respx.mock
async def test_anthropic_adapter_chat_and_stream() -> None:
    adapter = AnthropicAdapter()

    # 1. Non-streaming
    respx.post("https://api.anthropic.com/v1/messages").mock(
        return_value=Response(
            200,
            json={
                "id": "msg_01",
                "type": "message",
                "role": "assistant",
                "content": [{"type": "text", "text": "Claude says hello"}],
                "model": "claude-haiku-4-5",
                "stop_reason": "end_turn",
                "usage": {
                    "input_tokens": 25,
                    "output_tokens": 10,
                    "cache_read_input_tokens": 12,
                },
            },
        )
    )

    req = ChatRequest(
        model="claude-haiku-4-5",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello Claude"},
        ],
    )
    res = await adapter.chat(req, api_key="sk-ant-test-key")

    assert res.choices[0].message["content"] == "Claude says hello"
    assert res.choices[0].finish_reason == "stop"
    assert res.usage.prompt_tokens == 25
    assert res.usage.completion_tokens == 10
    assert res.usage.cached_prompt_tokens == 12

    # 2. Streaming
    stream_lines = (
        'data: {"type":"message_start","message":{"id":"msg_stream_1","usage":{"input_tokens":15,"cache_read_input_tokens":5}}}\n\n'
        'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"Hi"}}\n\n'
        'data: {"type":"message_delta","delta":{"stop_reason":"end_turn"},"usage":{"output_tokens":4}}\n\n'
    )
    respx.post("https://api.anthropic.com/v1/messages").mock(
        return_value=Response(200, text=stream_lines)
    )

    req_stream = ChatRequest(
        model="claude-haiku-4-5",
        messages=[{"role": "user", "content": "hi"}],
        stream=True,
    )
    chunks = []
    async for chunk in adapter.stream_chat(req_stream, api_key="sk-ant-test-key"):
        chunks.append(chunk)

    assert len(chunks) == 3
    assert chunks[1].choices[0].delta.content == "Hi"
    assert chunks[2].choices[0].finish_reason == "stop"
    assert chunks[2].usage is not None
    assert chunks[2].usage.completion_tokens == 4
    assert chunks[2].usage.cached_prompt_tokens == 5


@pytest.mark.asyncio
@respx.mock
async def test_anthropic_adapter_error_mapping() -> None:
    adapter = AnthropicAdapter()

    respx.post("https://api.anthropic.com/v1/messages").mock(
        return_value=Response(
            529, json={"error": {"type": "overloaded_error", "message": "Overloaded"}}
        )
    )
    with pytest.raises(ProviderOverloadedError):
        await adapter.chat(
            ChatRequest(model="claude-haiku-4-5", messages=[{"role": "user", "content": "hi"}]),
            api_key="key",
        )


# -----------------------------------------------------------------------------
# 5. Google Gemini Provider Tests
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
@respx.mock
async def test_google_gemini_adapter_chat_and_stream() -> None:
    adapter = GoogleGeminiAdapter()

    # 1. Non-streaming
    respx.post(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=gemini-key"
    ).mock(
        return_value=Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {"parts": [{"text": "Gemini response"}], "role": "model"},
                        "finishReason": "STOP",
                        "index": 0,
                    }
                ],
                "usageMetadata": {
                    "promptTokenCount": 18,
                    "candidatesTokenCount": 6,
                    "totalTokenCount": 24,
                    "cachedContentTokenCount": 4,
                },
            },
        )
    )

    req = ChatRequest(
        model="gemini-2.5-flash",
        messages=[
            {"role": "system", "content": "Be concise."},
            {"role": "user", "content": "Explain gravity in one sentence."},
        ],
    )
    res = await adapter.chat(req, api_key="gemini-key")

    assert res.choices[0].message["content"] == "Gemini response"
    assert res.choices[0].finish_reason == "stop"
    assert res.usage.prompt_tokens == 18
    assert res.usage.completion_tokens == 6
    assert res.usage.cached_prompt_tokens == 4

    # 2. Streaming
    stream_sse = (
        'data: {"candidates":[{"content":{"parts":[{"text":"Gravity"}],"role":"model"}}]}\n\n'
        'data: {"candidates":[{"content":{"parts":[{"text":" pulls."}],"role":"model"},"finishReason":"STOP"}],"usageMetadata":{"promptTokenCount":12,"candidatesTokenCount":5,"totalTokenCount":17}}\n\n'
    )
    respx.post(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:streamGenerateContent?alt=sse&key=gemini-key"
    ).mock(return_value=Response(200, text=stream_sse))

    chunks = []
    async for chunk in adapter.stream_chat(
        ChatRequest(
            model="gemini-2.5-flash", messages=[{"role": "user", "content": "gravity"}], stream=True
        ),
        api_key="gemini-key",
    ):
        chunks.append(chunk)

    assert len(chunks) == 2
    assert chunks[0].choices[0].delta.content == "Gravity"
    assert chunks[1].choices[0].delta.content == " pulls."
    assert chunks[1].choices[0].finish_reason == "stop"
    assert chunks[1].usage is not None
    assert chunks[1].usage.total_tokens == 17


def test_registry_get_adapter() -> None:
    assert isinstance(get_adapter("mock"), MockProviderAdapter)
    assert isinstance(get_adapter("openai"), OpenAIAdapter)
    assert isinstance(get_adapter("openai_compatible"), OpenAICompatibleAdapter)
    assert isinstance(get_adapter("anthropic"), AnthropicAdapter)
    assert isinstance(get_adapter("google"), GoogleGeminiAdapter)
