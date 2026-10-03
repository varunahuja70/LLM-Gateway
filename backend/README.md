# LLM Gateway — Backend Service

The backend is a high-performance, asynchronous reverse proxy and analytics engine built with **FastAPI**, **SQLAlchemy** (asyncio), **Redis**, and **PostgreSQL**.

---

## Key Features

- **OpenAI-Compatible Gateway Endpoints**:
  - `POST /v1/chat/completions` (streaming SSE and non-streaming)
  - `POST /v1/embeddings`
  - Model aliasing, fallback chains, and cross-provider normalization (OpenAI, Anthropic, Google Gemini).
- **Cost & Token Tracking**:
  - Tracks input, output, and cached prompt tokens with micro-USD precision.
  - Model pricing catalog with cache hit savings accounting.
- **Budget & Rate Limiting**:
  - Redis-backed sliding-window rate limiting.
  - Project-level daily/monthly hard and soft budget limits.
- **Quality & Telemetry Signals**:
  - TTFT (Time to First Token), latency percentiles (p50, p90, p95, p99).
  - Empty response detection, truncation detection, and user feedback capture (`/v1/feedback`).
- **Resilience & Caching**:
  - Response caching with semantic TTL.
  - Pre-first-token fallback switching to secondary providers.
  - Mid-stream error handling formatted according to OpenAI SSE specifications.
- **Admin Management API**:
  - Project configuration, gateway key provisioning (SHA-256 hashed), provider key vault (AES-256-GCM encrypted), and webhook alerts with HMAC-SHA256 signatures.

---

## Tech Stack

- **Runtime**: Python 3.13+
- **Framework**: FastAPI, Starlette
- **Database**: PostgreSQL with `asyncpg` (SQLAlchemy 2.0 async engine); SQLite (`aiosqlite`) supported for isolated test suites.
- **Cache & State**: Redis (`redis-py` async client)
- **Migrations**: Alembic
- **Package Manager**: `uv`

---

## Getting Started

### 1. Prerequisites
- Python 3.13 or higher
- Redis (optional for standalone unit tests, required for caching/rate-limiting)
- PostgreSQL (or SQLite for development)

### 2. Environment Setup

```bash
cp ../.env.example .env
```

Ensure `DATABASE_URL`, `REDIS_URL`, `MASTER_ENCRYPTION_KEY`, and `SESSION_SECRET` are configured.

### 3. Install Dependencies

Using `uv`:

```bash
uv sync --all-extras
```

### 4. Database Migrations & Price Seeding

```bash
uv run alembic upgrade head
```

Startup auto-seeds canonical model pricing if the catalog is empty.

### 5. Running the Development Server

```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Interactive API documentation is available at `http://localhost:8000/docs` (when `ENVIRONMENT=development`).

---

## Testing & Quality Assurance

Run the test suite:

```bash
# Run all tests
uv run python -m pytest

# Run unit tests only
uv run python -m pytest tests/unit

# Run integration tests
uv run python -m pytest tests/integration
```

Run code formatting and linters:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy app tests
```
