# Routing Anthropic Models Through OpenAI-Format Gateway

The LLM Gateway supports Anthropic Claude models (such as `claude-3-5-sonnet-20241022`, `claude-3-5-haiku-20241022`, and `claude-3-opus-20240229`) natively over the standard OpenAI `/v1/chat/completions` protocol.

This means applications, agent frameworks, or tooling written for OpenAI can instantly invoke Anthropic models with zero application code changes beyond specifying the model name.

---

## 1. Provider Setup in Dashboard

Before sending requests to Anthropic models:
1. Navigate to **Settings -> Providers** in the Gateway Dashboard (`http://localhost/settings`).
2. Click **Add Provider Credential**.
3. Select **Anthropic** from the dropdown.
4. Paste your Anthropic API Key (`sk-ant-...`). The gateway encrypts this key at rest using AES-256-GCM.
5. Click **Test Connection** to verify your credential directly with Anthropic's API.

---

## 2. Model Naming Convention

Always prefix models with `anthropic/` to route to the Anthropic adapter:

| Canonical Model Name | Description |
| :--- | :--- |
| `anthropic/claude-3-5-sonnet` | Claude 3.5 Sonnet (Latest stable) |
| `anthropic/claude-3-5-haiku` | High speed, cost-effective Claude 3.5 Haiku |
| `anthropic/claude-3-opus` | Deep reasoning Claude 3 Opus |

---

## 3. Example: Invoking Claude via OpenAI SDK

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost/v1",
    api_key="lgw_your_gateway_key_here",
)

# Call Claude using the OpenAI completions interface!
response = client.chat.completions.create(
    model="anthropic/claude-3-5-sonnet",
    messages=[
        {
            "role": "system",
            "content": "You are a senior systems engineer analyzing distributed deadlock scenarios.",
        },
        {
            "role": "user",
            "content": "How do chandy-misra-haas edge chasing algorithms detect deadlocks?",
        },
    ],
    max_tokens=500,
)

print(response.choices[0].message.content)
print(f"Input Tokens: {response.usage.prompt_tokens}")
print(f"Output Tokens: {response.usage.completion_tokens}")
```

---

## 4. Automatic Translation Features

The Anthropic adapter in LLM Gateway automatically handles:
- **System Message Extraction**: Converts OpenAI-format `{"role": "system", ...}` messages into top-level Anthropic `system` parameters.
- **Message Roles Alternation**: Formats user/assistant alternating structures required by Anthropic's Messages API.
- **Streaming SSE Translation**: Translates Anthropic's `content_block_delta` server-sent events into standard OpenAI `chat.completion.chunk` event streams.
- **Prompt Caching Support**: Tracks cached input tokens returned by Anthropic and computes accurate reduced pricing tiers.

---

## 5. Setting Up Fallback Chains

You can seamlessly fallback between OpenAI and Anthropic models without altering client application code.

In **Projects -> [Your Project] -> Config**:
```json
[
  {"provider": "anthropic", "model": "claude-3-5-sonnet"},
  {"provider": "openai", "model": "gpt-4o"},
  {"provider": "openai", "model": "gpt-4o-mini"}
]
```

If Anthropic returns a `429 Too Many Requests` or `529 Overloaded`, the gateway immediately falls back to `openai/gpt-4o`, preserving request latency and preventing client downtime.
