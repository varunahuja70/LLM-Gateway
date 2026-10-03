# Running Local Models with LLM Gateway (Ollama / vLLM / LocalAI)

LLM Gateway supports running fully local, privacy-first open-weight models (Llama 3, Mistral, Qwen, DeepSeek) through Ollama, vLLM, or LocalAI alongside commercial providers.

This allows hybrid architectures where cheap/sensitive tasks run locally with 0 cloud cost, falling back to commercial providers when needed.

---

## 1. Setting Up Ollama

If using Ollama locally:
1. Start Ollama:
   ```bash
   ollama run llama3.2
   ```
2. Verify Ollama is listening (default `http://localhost:11434` or Docker host `http://host.docker.internal:11434`).

---

## 2. Registering Local Provider in Gateway

1. Open **Settings -> Providers** in the Gateway Dashboard (`http://localhost/settings`).
2. Click **Add Provider Credential**.
3. Select **OpenAI-Compatible / Ollama / Local** as the provider type.
4. Set:
   - **Provider Name**: `ollama` (or `vllm`)
   - **Base URL**: `http://host.docker.internal:11434/v1` (if running in Docker) or `http://localhost:11434/v1` (native).
   - **API Key**: `ollama` (dummy key string; Ollama does not require auth).
5. Click **Test Connection** to confirm connectivity.

---

## 3. Configuring Local Model Pricing

Because local models incur no per-token API fees:
1. Navigate to **Settings -> Prices** in the Dashboard.
2. Click **Add Model Price**.
3. Set:
   - **Provider**: `ollama`
   - **Model**: `llama3.2`
   - **Input Price per Mtok**: `0` micro-USD
   - **Output Price per Mtok**: `0` micro-USD
   - **Source URL**: `http://localhost` (or self-hosted note)

*(Note: For local models, setting price to 0 µUSD accurately logs $0.00 cloud spend on your dashboard!)*

---

## 4. Invoking Local Models

Call your local model through the gateway using the standard client:

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost/v1",
    api_key="lgw_your_gateway_key_here",
)

response = client.chat.completions.create(
    model="ollama/llama3.2",
    messages=[
        {"role": "user", "content": "Explain vector databases in two bullet points."}
    ],
)

print(response.choices[0].message.content)
```

---

## 5. Hybrid Fallback (Local-First Architecture)

You can configure your project with a **Local-First Fallback Chain**:
1. Primary: `ollama/llama3.2` (Free, zero-egress local inference)
2. First Fallback: `openai/gpt-4o-mini` (Fast, low-cost commercial fallback)
3. Second Fallback: `anthropic/claude-3-5-haiku` (High-availability secondary)

If your local server is under heavy load, out of VRAM, or offline, the gateway automatically catches the connection error and routes traffic to the cloud fallback without failing user requests.
