# LLM Gateway

A high-performance, self-hosted LLM gateway and observability proxy. Drop-in compatible with the OpenAI API, featuring multi-provider routing, automated fallback chains, precision cost tracking in integer micro-USD, hard budget guards, exact-match caching, and an admin analytics dashboard.

[![CI](https://github.com/varunahuja70/LLM-Gateway/actions/workflows/ci.yml/badge.svg)](https://github.com/varunahuja70/LLM-Gateway/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.13+](https://img.shields.io/badge/python-3.13+-3776AB.svg?logo=python&logoColor=white)](backend/pyproject.toml)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg?logo=fastapi&logoColor=white)](backend/pyproject.toml)
[![Next.js 16](https://img.shields.io/badge/next.js-16.3-000000.svg?logo=nextdotjs&logoColor=white)](frontend/package.json)
[![PostgreSQL 18](https://img.shields.io/badge/postgresql-18-4169E1.svg?logo=postgresql&logoColor=white)](docker-compose.yml)

---

## Overview

LLM Gateway sits between your applications and upstream model providers (OpenAI, Anthropic, Google Gemini, and local OpenAI-compatible engines like Ollama and vLLM). It translates requests across provider protocols, tracks every token and millisecond, enforces financial budgets, and prevents downtime through automatic fallback routing.

All proxy overhead is kept minimal by delegating request logging, metric aggregation, and cost calculations to background worker queues, keeping the critical proxy path non-blocking.

---

## Key Features

- **OpenAI-Compatible Proxy**: Drop-in replacement for OpenAI SDKs (`/v1/chat/completions`, `/v1/embeddings`, `/v1/models`). Route requests by prefixing models with the target provider (`openai/gpt-4o`, `anthropic/claude-3-5-sonnet`, `gemini/gemini-1.5-flash`).
- **Precision Cost Accounting**: All financial data is calculated and stored in integer micro-USD (`$1.00 = 1,000,000 µUSD`) to avoid floating-point drift. Unpriced models record cost as `NULL` (never fabricated as zero).
- **Automated Fallback Chains**: Seamless failover on upstream rate limits (`429`), server errors (`500`, `502`, `503`, `504`), context window exhaustion, or service outages.
- **Budget Enforcement & Alerts**: Set daily and monthly hard budgets per project. Enforces rate limits (`429 Too Many Requests`) or dispatches webhook alerts at configurable thresholds (e.g., 50%, 80%, 100%).
- **Exact-Match Response Caching**: Redis-backed semantic exact caching with customizable per-project TTL and streaming response replay.
- **Quality & Performance Signals**: Tracks Time to First Token (TTFT), total latency, token usage, error classification, and thumbs-up/down quality feedback signals via `/v1/feedback`.
- **Zero-Trust Security**: AES-256-GCM encryption for provider credentials at rest, Argon2id password hashing, SHA-256 gateway key hashing, SSRF protection against private IP ranges, and automatic secret redaction in logs.

---

## Architecture

### System Architecture

```mermaid
flowchart TD
    Client["Client Applications<br/>(OpenAI SDK, cURL, LangChain)"] -->|"/v1/*"| Caddy["Caddy Reverse Proxy<br/>(:80, :443)"]
    Admin["Admin Browser"] -->|"/*"| Caddy

    subgraph CoreStack ["Self-Hosted Gateway Stack"]
        Caddy -->|"/v1/*, /healthz, /readyz"| API["FastAPI Gateway Engine<br/>(:8000)"]
        Caddy -->|"/* (UI Routes)"| Dashboard["Next.js Admin UI<br/>(:3000)"]

        API --> Auth["Key Auth<br/>(SHA-256 Hash Lookup)"]
        Auth --> Guard["Rate Limiter & Budget Guard"]
        Guard --> Cache["Exact-Match Cache<br/>(Redis TTL)"]
        Cache --> Router["Provider Router & Fallback Chain"]

        API -.->|Async Queue| Logger["Background Request Logger<br/>(Batch Worker)"]
        Logger --> DB[("PostgreSQL 18<br/>Logs, Config, Audits")]
        Guard <--> Redis[("Redis 8<br/>Sliding Window & Cache")]
    end

    Router -->|"HTTPS / REST"| OpenAI["OpenAI API"]
    Router -->|"HTTPS / REST"| Anthropic["Anthropic API"]
    Router -->|"HTTPS / REST"| Gemini["Google Gemini API"]
    Router -->|"HTTPS / REST"| Compatible["OpenAI-Compatible<br/>(Ollama / vLLM)"]
```

### Request Lifecycle

```mermaid
flowchart TD
    Start([Client Request: POST /v1/chat/completions]) --> Auth{Valid Gateway Key?}
    Auth -- No --> ErrAuth[401 Unauthorized]
    Auth -- Yes --> Limit{Rate Limit or Budget Exceeded?}
    Limit -- Yes --> ErrLimit[429 Too Many Requests]
    Limit -- No --> CacheCheck{Cache Enabled & Hit?}
    CacheCheck -- Hit --> LogCache[Queue Request Log: cache_hit=true]
    LogCache --> ReturnCache([Return Cached Response])
    CacheCheck -- Miss --> CallPrimary[Dispatch to Primary Provider]
    CallPrimary --> CheckStatus{Upstream Successful?}
    CheckStatus -- Error (429/5xx) --> FallbackCheck{Fallback Configured?}
    FallbackCheck -- Yes --> CallFallback[Dispatch to Fallback Model]
    FallbackCheck -- No --> ReturnErr[Propagate Upstream Error]
    CheckStatus -- Success --> Compute[Calculate Tokens, Cost, Latency & TTFT]
    CallFallback --> Compute
    Compute --> CacheWrite[Write to Cache if Enabled]
    CacheWrite --> EnqueueLog[Queue Log to Background Worker]
    EnqueueLog --> ReturnResponse([Stream or Return JSON Response])
```

---

## Tech Stack

| Layer | Technologies |
| :--- | :--- |
| **Backend** | Python 3.13+, FastAPI, SQLAlchemy 2.0 (async), Pydantic v2, Alembic, httpx, structlog, prometheus-client |
| **Frontend** | Next.js 16 (App Router), React 19, TypeScript (strict), Tailwind CSS v4, shadcn/ui, TanStack Query, Recharts |
| **Data & Cache** | PostgreSQL 18, Redis 8 (Lua sliding-window rate limiting & exact caching) |
| **Gateway Proxy** | Caddy 2 (reverse proxy, TLS termination, routing `/v1/*` to backend and `/*` to UI) |
| **Tooling** | uv (Python package manager), pnpm (Node.js package manager), Docker Compose, GitHub Actions |

---

## Quick Start

### 1. Clone and Configure

```bash
git clone https://github.com/varunahuja70/LLM-Gateway.git
cd LLM-Gateway

# Create local environment configuration
cp .env.example .env
```

### 2. Generate Master Key

The gateway requires a 32-byte cryptographically secure key for AES-256-GCM vault encryption. Generate a valid key using Python:

```bash
python -c "import secrets,base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"
```

Open `.env` and assign this generated base64 string to `GATEWAY_MASTER_KEY`:

```env
GATEWAY_MASTER_KEY=<generated-base64-key>
```

---

## Running Locally with Docker

Docker Compose runs the entire stack (Caddy, Backend, Frontend, PostgreSQL, and Redis) with a single command:

```bash
# 1. Start all containers in the background
docker compose up -d

# 2. Apply database migrations
docker compose exec backend uv run alembic upgrade head

# 3. Seed verified model catalog prices
docker compose exec backend uv run python scripts/seed_prices.py

# 4. (Optional) Seed realistic demo traffic and sample projects
docker compose exec backend uv run python scripts/seed_demo.py
```

- **Admin Dashboard**: Open [http://localhost](http://localhost) in your browser. Complete first-time owner account setup or log in.
- **Gateway Endpoint**: Ready to receive API requests at `http://localhost/v1`.

To stop the containers:

```bash
docker compose down
```

---

## Running Locally without Docker

For active local development without containerizing the app processes:

### Prerequisites

- Python 3.13+ with [uv](https://docs.astral.sh/uv/)
- Node.js 20+ with [pnpm](https://pnpm.io/)
- PostgreSQL 18 and Redis running locally (or via `docker compose -f docker-compose.dev.yml up -d`)

### Backend Setup

```bash
cd backend

# Install dependencies into virtualenv
uv sync

# Run database migrations
uv run alembic upgrade head

# Seed model prices
uv run python scripts/seed_prices.py

# Start FastAPI development server
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend Setup

```bash
cd frontend

# Install Node dependencies
pnpm install

# Start Next.js development server
pnpm dev
```

The frontend will run at `http://localhost:3000` and communicate with the backend at `http://localhost:8000`.

---

## Environment Configuration

Configure application settings in `.env` at the project root:

| Variable | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `GATEWAY_MASTER_KEY` | string | *Required* | Exactly 32 bytes base64 encoded for AES-256-GCM encryption |
| `DATABASE_URL` | string | `postgresql+asyncpg://...` | PostgreSQL async connection URI |
| `REDIS_URL` | string | `redis://localhost:6379/0` | Redis connection URI for caching and rate limiting |
| `ENV` | string | `development` | Deployment environment: `development`, `test`, or `production` |
| `PUBLIC_URL` | string | `http://localhost` | Public facing gateway URL (used for CORS and CSRF validation) |
| `SESSION_SECRET` | string | *Auto-derived* | Key used for signing owner session cookies |
| `RATE_LIMIT_GLOBAL_RPM` | int | `10000` | Global requests-per-minute threshold across the gateway |
| `LOG_LEVEL` | string | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |

---

## API Usage Example

### 1. Chat Completion via cURL

```bash
curl -X POST "http://localhost/v1/chat/completions" \
  -H "Authorization: Bearer lgw_your_gateway_key_here" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "openai/gpt-4o-mini",
    "messages": [
      {"role": "system", "content": "You are a concise technical assistant."},
      {"role": "user", "content": "What is an LLM gateway in one sentence?"}
    ],
    "temperature": 0.7
  }'
```

### 2. Streaming Chat Completion

Server-Sent Events (SSE) streaming is natively supported with real-time TTFT tracking:

```bash
curl -N -X POST "http://localhost/v1/chat/completions" \
  -H "Authorization: Bearer lgw_your_gateway_key_here" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "anthropic/claude-3-5-haiku",
    "messages": [{"role": "user", "content": "Count from 1 to 5."}],
    "stream": true
  }'
```

### 3. OpenAI Python SDK Integration

Point `base_url` to the gateway and provide your project key:

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost/v1",
    api_key="lgw_your_gateway_key_here",
)

response = client.chat.completions.create(
    model="gemini/gemini-1.5-flash",
    messages=[{"role": "user", "content": "Hello from the Python SDK!"}],
)

print(response.choices[0].message.content)
```

### 4. Submitting Quality Feedback

Capture end-user feedback to monitor application quality and prompt drift:

```bash
curl -X POST "http://localhost/v1/feedback" \
  -H "Authorization: Bearer lgw_your_gateway_key_here" \
  -H "Content-Type: application/json" \
  -d '{
    "request_id": "019438ab-cdef-7000-8000-000000000001",
    "score": 1,
    "note": "Accurate and fast response."
  }'
```

---

## Available API Endpoints

### Public Gateway Routes

All public gateway routes require a valid gateway key supplied via `Authorization: Bearer lgw_...`.

| Method | Endpoint | Purpose |
| :--- | :--- | :--- |
| `POST` | `/v1/chat/completions` | Create a chat completion (supports streaming, caching, fallback) |
| `POST` | `/v1/embeddings` | Generate vector embeddings |
| `POST` | `/v1/feedback` | Record quality feedback (score: `1` or `-1`, note, tag) for a request ID |
| `GET` | `/v1/models` | List all available models, aliases, and active providers |

### Admin & Management Routes

Admin endpoints require authenticated owner session cookies (established via `/admin/auth/login`) and CSRF tokens for state-modifying requests.

| Method | Endpoint | Purpose | Authentication |
| :--- | :--- | :--- | :--- |
| `GET` | `/admin/setup/status` | Check if initial owner user exists | None |
| `POST` | `/admin/setup` | Register first-time owner user | None (first run only) |
| `POST` | `/admin/auth/login` | Authenticate owner and set session cookie | None |
| `POST` | `/admin/auth/logout` | Invalidate current owner session | Owner Session |
| `GET` | `/admin/auth/me` | Fetch active owner profile | Owner Session |
| `GET`/`POST` | `/admin/projects` | List or create projects | Owner Session |
| `GET`/`PUT` | `/admin/projects/{id}` | Inspect or update project metadata | Owner Session |
| `GET`/`PUT` | `/admin/projects/{id}/config` | Manage project budgets, fallbacks, cache TTL | Owner Session |
| `GET`/`POST` | `/admin/projects/{id}/keys` | List or create project gateway keys | Owner Session |
| `DELETE` | `/admin/projects/{id}/keys/{key_id}` | Revoke a gateway key | Owner Session |
| `GET` | `/admin/stats/overview` | Global aggregated metrics (spend, tokens, latency, cache) | Owner Session |
| `GET` | `/admin/stats/timeseries` | Historical time-series metrics | Owner Session |
| `GET` | `/admin/stats/models` | Per-model usage, spend, and error distribution | Owner Session |
| `GET` | `/admin/requests` | Request log explorer with status and latency filters | Owner Session |
| `GET` | `/admin/requests/{id}` | Detailed trace and payload breakdown for single request | Owner Session |
| `GET`/`POST` | `/admin/providers` | Manage provider API credentials (encrypted in vault) | Owner Session |
| `GET`/`POST` | `/admin/prices` | View or override model price catalog | Owner Session |
| `POST` | `/admin/prices/seed` | Reset prices to official verified seed catalog | Owner Session |
| `GET` | `/admin/alerts` | List triggered budget alert events | Owner Session |
| `POST` | `/admin/alerts/test-webhook` | Test alert webhook endpoint (SSRF protected) | Owner Session |
| `GET`/`PUT` | `/admin/settings` | System-wide settings and data retention policies | Owner Session |

### Health & Observability Routes

| Method | Endpoint | Purpose | Access |
| :--- | :--- | :--- | :--- |
| `GET` | `/healthz` | Fast liveness probe (200 OK) | Public |
| `GET` | `/readyz` | Readiness probe (verifies database & Redis connectivity) | Public |
| `GET` | `/metrics` | Prometheus telemetry exporter | Internal (restricted by Caddy) |

---

## Admin Dashboard & Observability

The Next.js admin dashboard provides visual management of your LLM infrastructure:

- **Overview Dashboard**: High-level telemetry showing 24-hour spend, total tokens, p50 and p95 latency percentiles, error rate, and cache hit efficiency.
- **Project Configuration**: Define hard budget limits (daily/monthly), adjust rate limits (RPM), configure fallback model chains, and toggle exact caching.
- **Key Management**: Issue granular scoped gateway keys (`lgw_...`) with single-reveal security and immediate revocation capabilities.
- **Request Trace Explorer**: Inspect individual requests, status codes, latency breakdowns, prompt tokens, completion tokens, calculated cost in micro-USD, and cache status.
- **Provider Vault**: Securely input and test upstream provider API keys (OpenAI, Anthropic, Gemini, custom endpoints) without exposing keys in plaintext.
- **Model Catalog & Pricing**: Audit active pricing tables, inspect effective dates, and verify provider source URLs.

---

## Security Notes

1. **Vault Encryption**: Provider API keys and sensitive webhook secrets are encrypted at rest using AES-256-GCM with Authenticated Associated Data (AAD). The key is derived strictly from `GATEWAY_MASTER_KEY`.
2. **Key Hashing**: Client gateway keys (`lgw_<prefix>_<secret>`) are hashed using SHA-256 before storage. Plaintext keys are never stored in the database and are displayed only once upon creation.
3. **Owner Authentication**: Owner passwords are hashed using Argon2id. Sessions are tracked via HTTP-only, SameSite cookies with CSRF token verification on all mutation endpoints.
4. **SSRF Protection**: Webhook URLs and custom provider `base_url` values are validated against private, link-local, loopback, and cloud metadata IP blocks (e.g., `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `127.0.0.0/8`, `169.254.169.254`).
5. **Log Redaction**: Automatic structured log filters scrub bearer tokens, gateway keys, passwords, and authorization headers from stdout and log stores.
6. **Production Safeguards**: Always deploy behind HTTPS with valid TLS certificates, isolate database and Redis instances from public ingress, and supply a unique 32-byte master key.

---

## Testing and Code Quality

All quality checks and automated tests run in CI workflows on every pull request and push to `main`.

### Backend Quality Suite

Run from `backend/`:

```bash
# Code linting
uv run ruff check .

# Formatting check
uv run ruff format --check .

# Strict static type checking
uv run python -m mypy app tests

# Dependency vulnerability scanning
uv run pip-audit

# Pytest test suite (104 integration and security tests)
uv run python -m pytest
```

### Frontend Quality Suite

Run from `frontend/`:

```bash
# ESLint check
pnpm run lint

# TypeScript compilation
pnpm exec tsc --noEmit

# Vitest unit and component tests (27 tests)
pnpm run test:run

# Dependency security audit
pnpm audit --audit-level=high
```

---

## Project Structure

```text
LLM-Gateway/
├── .github/workflows/       # GitHub Actions CI/CD pipelines
├── backend/                 # FastAPI gateway and backend engine
│   ├── app/
│   │   ├── api/             # API routers (gateway public routes and admin routes)
│   │   ├── core/            # Security, rate limiting, error handlers, config
│   │   ├── db/              # SQLAlchemy models, sessions, base classes
│   │   ├── providers/       # Adapter layer (OpenAI, Anthropic, Gemini, mock)
│   │   ├── schemas/         # Pydantic request/response schemas
│   │   ├── services/        # Request logger, cost engine, fallback router
│   │   └── workers/         # Background scheduler and batch writers
│   ├── migrations/          # Alembic database migrations
│   ├── scripts/             # Database seeding scripts (prices, demo data)
│   ├── tests/               # Unit, integration, and security test suites
│   └── pyproject.toml       # Python dependencies and tool configurations
├── frontend/                # Next.js admin dashboard
│   ├── src/
│   │   ├── app/             # Next.js App Router pages and layout
│   │   ├── components/      # UI components (shadcn/ui, charts, navigation)
│   │   ├── hooks/           # Custom React hooks
│   │   └── lib/             # API client, TypeScript types, formatting helpers
│   ├── tests/               # Vitest unit and component test suites
│   └── package.json         # Frontend dependencies and scripts
├── docs/                    # Architecture guides, benchmarks, and releases
├── docker-compose.yml       # Production multi-service Docker configuration
├── docker-compose.dev.yml   # Local development Docker override
├── Caddyfile                # Reverse proxy routing and security headers
├── Makefile                 # Convenient developer automation shortcuts
└── README.md                # Project documentation
```

---

## Known Limitations & Status

- **Provider Adapters**: Fully implemented native adapters include OpenAI, Anthropic, and Google Gemini. Additional OpenAI-compatible engines (Ollama, vLLM, Groq, Together) are supported via custom `base_url` configuration. Native Mistral and Cohere adapters are planned for future releases.
- **Streaming Telemetry**: Streaming completions capture TTFT and total request duration. Token usage reporting during streaming relies on upstream provider stream chunks; if omitted by the provider, character-based token estimates are applied.
- **Rate Limiting Resilience**: Distributed rate limiting runs in Redis via atomic Lua scripts. If Redis is unavailable, the gateway automatically falls back to an in-memory sliding window limiter to prevent service interruption.

---

## Benchmarks

Synthetic proxy overhead measured using an in-memory zero-latency mock provider (isolating gateway routing, key validation, and telemetry overhead from upstream network transit):

| Metric | Target | Measured Result |
| :--- | :--- | :--- |
| **Gateway p50 Overhead** | < 30 ms | **26.86 ms** |
| **Gateway p95 Overhead** | < 50 ms | **41.71 ms** |
| **Throughput (single node)**| > 50 req/s | **68.0+ req/s** |
| **Proxy Error Rate** | 0.00% | **0.00%** |

*Note: Benchmarks reflect internal gateway processing overhead only, not external third-party LLM response times. For detailed reproduction instructions and full methodology, see [docs/benchmarks.md](docs/benchmarks.md).*

---

## Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) and our [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) before submitting a pull request.

1. Fork the repository.
2. Create a feature branch: `git checkout -b feature/my-feature`.
3. Ensure all tests and linters pass (`make lint` and `make test`).
4. Commit your changes: `git commit -m "feat: add my feature"`.
5. Open a pull request against `main`.

---

## License

This project is licensed under the [MIT License](LICENSE).
