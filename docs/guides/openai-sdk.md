# Connecting the OpenAI SDK to LLM Gateway

The LLM Gateway exposes a fully OpenAI-compatible `/v1/chat/completions` API endpoint. You can integrate it with any OpenAI SDK (Python, TypeScript/JavaScript, Go, Java, or raw HTTP client) by updating two parameters:

1. `base_url`: Point to the gateway instance (e.g., `http://localhost/v1` or `https://gateway.internal/v1`).
2. `api_key`: Use your project's issued Gateway API key (`lgw_...`).

---

## 1. Python SDK

Install the official OpenAI Python package:
```bash
pip install openai
```

### Sync Client Example
```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost/v1",
    api_key="lgw_your_gateway_key_here",
)

response = client.chat.completions.create(
    model="openai/gpt-4o",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Summarize the benefits of self-hosted API gateways."},
    ],
    temperature=0.7,
)

print(response.choices[0].message.content)
print(f"Tokens: {response.usage.total_tokens}")
```

### Async Streaming Client Example
```python
import asyncio
from openai import AsyncOpenAI

client = AsyncOpenAI(
    base_url="http://localhost/v1",
    api_key="lgw_your_gateway_key_here",
)

async def stream_chat():
    stream = await client.chat.completions.create(
        model="openai/gpt-4o-mini",
        messages=[{"role": "user", "content": "Write a haiku about distributed tracing."}],
        stream=True,
    )
    async for chunk in stream:
        delta = chunk.choices[0].delta.content or ""
        print(delta, end="", flush=True)
    print()

asyncio.run(stream_chat())
```

---

## 2. TypeScript / Node.js SDK

Install the official OpenAI npm package:
```bash
pnpm add openai
```

```typescript
import OpenAI from "openai";

const client = new OpenAI({
  baseURL: "http://localhost/v1",
  apiKey: process.env.GATEWAY_API_KEY || "lgw_your_gateway_key_here",
});

async function main() {
  const completion = await client.chat.completions.create({
    model: "openai/gpt-4o",
    messages: [{ role: "user", content: "What is the capital of France?" }],
  });

  console.log(completion.choices[0].message.content);
}

main();
```

---

## 3. Gateway Specific Features & Custom Headers

You can control gateway features using standard HTTP headers or parameters:

- **User Attribution**:
  Pass `X-Gateway-User: user_12345` or set `user: "user_12345"` in the payload to track usage and cost per end-user.
- **Cache Bypass**:
  Pass `X-Gateway-Cache: bypass` to force a live provider request even if caching is enabled for the project.
- **Response Headers Returned**:
  - `X-Gateway-Request-Id`: Unique UUID for request tracking and feedback correlation.
  - `X-Gateway-Model-Used`: Canonical model actually executed (e.g., `openai/gpt-4o`).
  - `X-Gateway-Cache`: `hit`, `miss`, or `bypass`.
  - `X-Gateway-Fallback`: `none` or the original model if fallback occurred.

---

## 4. Submitting Quality Feedback

To submit human thumbs up/down feedback or corrections for a request:

```python
import httpx

httpx.post(
    "http://localhost/v1/feedback",
    headers={"Authorization": "Bearer lgw_your_gateway_key_here"},
    json={
        "request_id": response.id, # or X-Gateway-Request-Id
        "score": 1, # 1 for thumbs up, -1 for thumbs down
        "notes": "Fast and concise answer",
        "tag": "accuracy",
    }
)
```
