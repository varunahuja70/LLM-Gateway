# LLM Gateway + Cost and Quality Tracker

[![CI](https://github.com/your-org/llm-gateway/actions/workflows/ci.yml/badge.svg)](https://github.com/your-org/llm-gateway/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](backend/pyproject.toml)
[![Next.js 16](https://img.shields.io/badge/next.js-16.3-black.svg)](frontend/package.json)
[![Tailwind v4](https://img.shields.io/badge/tailwindcss-v4-06B6D4.svg)](frontend/package.json)

An open-source, self-hosted gateway between your applications and AI model providers. It acts as an OpenAI-compatible drop-in proxy while tracking latency, tokens, cost, and errors in real-time. Features multi-provider routing, budget enforcement, automatic fallback chains, exact-match caching, user feedback signals, and an admin dashboard.

---

## Architecture

```mermaid
flowchart LR
    Client["Client Apps / SDKs<br/>(OpenAI SDK, cURL, LangChain)"] -->|"/v1/chat/completions"| Caddy["Caddy Reverse Proxy<br/>(:80, :443)"]
    
    subgraph GatewayStack ["Self-Hosted Gateway Stack"]
        Caddy -->|"/v1/*"| API["FastAPI Gateway Engine<br/>(:8000)"]
        Caddy -->|"/*"| Dashboard["Next.js Admin UI<br/>(:3000)"]
        
        API --> Auth["Key Auth & SHA-256"]
        Auth --> Budget["Rate Limits & Budget Guard"]
        Budget --> Cache["Exact Match Cache<br/>(Redis)"]
        Cache --> Fallback["Fallback Router"]
        
        API -.->|Async Queue| Logger["Batch Logger Worker"]
        Logger --> PG[("PostgreSQL 18")]
        API <--> Redis[("Redis 8")]
    end
    
    Fallback -->|"HTTPS"| OpenAI["OpenAI API"]
    Fallback -->|"HTTPS"| Anthropic["Anthropic API"]
    Fallback -->|"HTTPS"| Gemini["Google Gemini API"]
    Fallback -->|"HTTPS"| Local["Local Models<br/>(Ollama / vLLM)"]
```

---

## Key Features

- **OpenAI-Compatible Proxy**: Drop-in replacement for OpenAI SDK (`/v1/chat/completions`, `/v1/models`). Point `base_url` to the gateway and prefix models with provider (`openai/gpt-4o`, `anthropic/claude-3-5-sonnet`, `gemini/gemini-1.5-pro`).
- **Precision Cost Tracking**: All money is computed and stored as integer micro-USD (`$1.00 = 1,000,000 µUSD`). Built-in seed price catalog with verifiable source URLs and date stamps. Unknown model prices remain `NULL` (never fabricated as 0).
- **Hard Budgets & Webhooks**: Configure daily and monthly budgets per project. Enforce hard blocking at limit (`429 Too Many Requests`) or trigger webhook alerts at configurable thresholds (e.g. 50%, 80%, 100%).
- **Automated Fallbacks**: Seamless failover on provider rate limits (429), server errors (500, 502, 503, 504), context length exceeded, or model decommission.
- **Exact-Match Response Caching**: Optional per-project Redis caching with customizable TTL and streaming replay.
- **Latency & Quality Telemetry**: Captures round-trip duration, Time to First Token (TTFT), token counts, and thumbs-up/down quality feedback signals with optional prompt correction tags.
- **Zero-Trust Security**:
  - Provider keys encrypted at rest using AES-256-GCM with associated authentication data (AAD).
  - Admin passwords hashed with Argon2id.
  - Automatic redaction filter scrubs API keys, bearer tokens, passwords, and authorization headers from all logs and error responses.
  - Built-in SSRF protection preventing webhook calls to private, loopback, or cloud metadata IP ranges (RFC 1918, RFC 3927, 169.254.169.254).
  - Sensitive metrics (`/metrics`) and docs (`/admin/docs`) are strictly kept internal.

---

## 5-Minute Quick Start

### Option 1: Docker Compose (Recommended)

1. **Clone the repository**:
   ```bash
   git clone https://github.com/your-org/llm-gateway.git
   cd llm-gateway
   ```

2. **Configure environment**:
   ```bash
   cp .env.example .env
   # Generate your 32-byte base64 master key:
   # python -c "import secrets, base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"
   ```

3. **Start all services**:
   ```bash
   docker compose up -d
   ```

4. **Initialize and Seed**:
   ```bash
   # Run migrations and load verified model prices
   docker compose exec backend uv run alembic upgrade head
   docker compose exec backend uv run python scripts/seed_prices.py
   
   # (Optional) Seed realistic demo data
   docker compose exec backend uv run python scripts/seed_demo.py
   ```

5. **Open Dashboard**:
   Visit [http://localhost](http://localhost) to set up the owner account or explore the dashboard.

---

### Option 2: Local Development

```bash
# Start Postgres & Redis dependencies
docker compose -f docker-compose.dev.yml up -d

# Run migrations and seed
make migrate
make seed

# Start backend and frontend with hot-reload
make dev
```

---

## Making Your First Request

### Using OpenAI Python SDK

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost/v1",
    api_key="lgw_your_gateway_key_here",
)

response = client.chat.completions.create(
    model="openai/gpt-4o-mini",
    messages=[{"role": "user", "content": "Explain quantum computing in one sentence."}],
)

print(response.choices[0].message.content)
```

### Using cURL

```bash
curl -X POST "http://localhost/v1/chat/completions" \
  -H "Authorization: Bearer lgw_your_gateway_key_here" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "openai/gpt-4o-mini",
    "messages": [{"role": "user", "content": "Hello gateway!"}]
  }'
```

---

## Configuration Reference

All settings are configured via environment variables or `.env`:

| Variable | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `DATABASE_URL` | string | `postgresql+asyncpg://...` | PostgreSQL async connection string |
| `REDIS_URL` | string | `redis://localhost:6379/0` | Redis connection URL |
| `GATEWAY_MASTER_KEY` | string | **Required** | 32-byte base64 string for AES-256-GCM encryption |
| `ENV` | string | `production` | Environment (`development`, `test`, `production`) |
| `PUBLIC_URL` | string | `http://localhost` | Public facing URL for CSRF and webhook validation |
| `SESSION_SECRET` | string | Auto-derived | Secret for signing session cookies |
| `RATE_LIMIT_GLOBAL_RPM`| int | `10000` | Global gateway rate limit cap |
| `LOG_LEVEL` | string | `INFO` | Structlog level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |

---

## Benchmarks & Performance

Measured against the zero-latency mock provider stack:
- **Throughput**: Sustained `68.0+ req/s` on single node
- **Gateway p50 Overhead**: `26.86 ms`
- **Gateway p95 Overhead**: **`41.71 ms`** (Under target `< 50 ms`)
- **Error Rate**: `0.00%`

See full benchmark methodology and breakdowns in [docs/benchmarks.md](docs/benchmarks.md).

---

## Guides & Documentation

- [Connecting the OpenAI SDK](docs/guides/openai-sdk.md)
- [Routing Anthropic Models](docs/guides/anthropic-migration.md)
- [Running with Local Models (Ollama / vLLM)](docs/guides/local-models.md)
- [Performance Benchmarks](docs/benchmarks.md)
- [Release Notes v0.1.0](docs/releases/v0.1.0.md)

---

## Contributing

We welcome community contributions! Please review [CONTRIBUTING.md](CONTRIBUTING.md) and [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) before opening a pull request.

---

## License

Released under the [MIT License](LICENSE).
