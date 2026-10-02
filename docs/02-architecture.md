# 02 - Architecture

Reads: `01-prd.md`. Every choice below exists to satisfy a behaviour in the PRD.

## 1. Principles

1. **The gateway must never be the reason an app is slow or down.** Logging, alerts and stats happen off the request path.
2. **Money is stored as integers** (micro-USD, 1 USD = 1,000,000) so there is no floating point drift.
3. **Unknown price = unknown cost**, never zero. Calls to unpriced models are logged with `cost = NULL` and flagged in the dashboard.
4. **Secrets are never readable after saving.** Provider keys are encrypted at rest. Gateway keys are stored only as hashes.
5. **One way to do each thing.** One database, one cache, one HTTP client, one migration tool.

## 2. Stack

Versions marked **verified** were checked on 2026-10-03 from the sources listed in section 8. Versions marked **pin at setup** were not verified here: the build agent must install the latest stable release, run the version command shown, and record the result in `docs/versions.lock.md`. Never copy a version from memory.

| Layer | Choice | Version | Why |
|---|---|---|---|
| Language (backend) | Python | 3.13 (3.14 also supported by the main libraries; use 3.13 unless every dependency installs cleanly on 3.14) | Matches the owner's existing skills; strong async ecosystem |
| Web framework | FastAPI | **verified** 0.136.x (0.136.3 seen, 2026-05-23). Pin at setup: `uv add fastapi` | Async, typed, auto-generated API docs |
| ASGI server | Uvicorn (with `uvloop` and `httptools` extras) | pin at setup | Standard FastAPI server, fast |
| Validation / settings | Pydantic v2 + pydantic-settings | **verified** 2.12+ line. Pin at setup | Typed config and request models |
| ORM | SQLAlchemy 2.0 (async) | **verified** 2.0.x stable. Do NOT use 2.1 (still beta at last check) | Mature async ORM |
| DB driver | asyncpg | pin at setup | Fastest async Postgres driver |
| Migrations | Alembic | pin at setup | Standard with SQLAlchemy |
| Database | PostgreSQL | **verified** 18.x (18.3 seen) | Reliable, good for time-series style queries with proper indexes |
| Cache / counters / rate limit | Redis (official image, latest stable 8.x at setup; Valkey is an acceptable drop-in) | pin at setup | Atomic counters, TTL, Lua scripts |
| HTTP client to providers | httpx (async, HTTP/2, connection pooling) | pin at setup | Streaming support, timeouts |
| Password hashing | argon2-cffi | pin at setup | Argon2id is the current recommended password hash |
| Encryption | cryptography (AES-256-GCM) | pin at setup | Audited library |
| Logging | structlog (JSON output) | pin at setup | Structured logs, easy redaction |
| Metrics | prometheus-client (`/metrics`) | pin at setup | Shows observability skills; free to scrape |
| Scheduler | APScheduler (async) running inside the app process | pin at setup | Retention, rollups, budget reset; avoids a separate worker for V1 |
| Tokens (estimate fallback) | tiktoken | pin at setup | Used only when a provider returns no usage |
| Python tooling | uv (packages), ruff (lint + format), mypy (strict) | pin at setup | Fast, modern |
| Backend tests | pytest, pytest-asyncio, respx (mock provider HTTP), httpx test client, coverage | pin at setup | |
| Frontend framework | Next.js (App Router, TypeScript strict) | **verified** 16.x line (16.3.6 with React 19.3.0 reported Sept 2026). Pin at setup: `npm view next version` | Matches owner's stack |
| UI | React 19.x, Tailwind CSS v4, shadcn/ui, lucide-react | pin at setup | Premium minimal look, accessible primitives |
| Charts | Recharts | pin at setup | Simple, works with React 19 |
| Data fetching | TanStack Query | pin at setup | Caching and refetch for dashboards |
| Frontend tests | Vitest + Testing Library, Playwright (one smoke flow) | pin at setup | |
| Node tooling | Node LTS (current at setup), pnpm | pin at setup | |
| Reverse proxy | Caddy 2 | pin at setup | Automatic HTTPS, tiny config |
| Packaging | Docker (multi-stage, non-root) + Docker Compose | pin at setup | One-command start |
| CI | GitHub Actions | n/a | Lint, type check, tests, image build, dependency audit |

## 3. System overview

```
App (any language)
   |  OpenAI-style request + project key
   v
Caddy (HTTPS) ──/v1/*──────────> Backend (FastAPI)
              ──/admin/*───────> Backend (FastAPI)
              ──/ everything else > Frontend (Next.js dashboard)

Backend request path (gateway):
  1. authenticate project key (hash lookup, Redis-cached for 60 s)
  2. rate limit (Redis)
  3. budget check (Redis counter)
  4. cache lookup (Redis)           -> hit: replay, log, return
  5. route to provider adapter (httpx, streaming)
  6. on failure: fallback chain
  7. return response to app immediately
  8. push a log record to an in-memory queue  (off the request path)

Background in the same process:
  - batch writer: queue -> Postgres (every 1 s or 200 records)
  - budget updater: INCRBY Redis counters, fire alerts on threshold crossing
  - retention job: delete old logs nightly
  - budget reconcile job: rebuild Redis counters from Postgres every 10 min
```

Trade-off: the queue lives in memory, so a hard crash can lose up to about one second of log records. The app's answer is never lost. On graceful shutdown the queue is flushed. This is documented in the README.

Trade-off: budget blocking is **approximate**. Cost is known only after a call finishes, so a few in-flight calls can overshoot the limit. The dashboard says so.

## 4. Data model

All IDs are UUIDv7 (time-ordered) unless noted. All timestamps are `timestamptz` in UTC.

**owner_user**: id, email (unique), password_hash, created_at. V1 allows exactly one row (enforced by a unique constraint on a constant column).

**session**: id (random 256-bit, stored hashed), owner_id, csrf_token_hash, created_at, last_seen_at, expires_at, user_agent, ip.

**project**: id, name (unique), slug (unique), description, created_at, archived_at.

**gateway_key**: id, project_id, name, prefix (first 8 chars, shown in UI), key_hash (SHA-256 of the full key), created_at, last_used_at, revoked_at, expires_at (nullable). Key format: `lgw_` + 43 URL-safe random chars (256 bits). The full key is shown once.

**provider_credential**: id, provider (`openai` | `anthropic` | `google` | `openai_compatible` | `mock`), name, base_url (nullable, used by `openai_compatible`), encrypted_key (bytea), key_version (int), key_last4, created_at, disabled_at.

**model_price**: id, provider, model, input_micro_usd_per_mtok (bigint), output_micro_usd_per_mtok (bigint), cached_input_micro_usd_per_mtok (bigint, nullable), source_url, verified_on (date), is_seed (bool), updated_at. Unique on (provider, model).

**project_config** (one row per project): project_id (pk), daily_budget_micro_usd (nullable), monthly_budget_micro_usd (nullable), warn_thresholds (int[], default `{50,80,100}`), block_at_limit (bool, default false), fallback_chain (jsonb: ordered list of `{provider, model}`), max_fallbacks (int, default 2), request_timeout_s (int, default 60), cache_enabled (bool, default false), cache_ttl_s (int, default 3600), rpm_limit (int, default 60), log_content (bool, default false), webhook_url (nullable), webhook_secret_encrypted (nullable), provider_credential_id (default credential per provider, jsonb map).

**request_log**: id (uuidv7), project_id, gateway_key_id, created_at, endpoint (`chat` | `embeddings`), provider, model_requested, model_used, status (`ok` | `error` | `blocked` | `rate_limited`), http_status, error_type (nullable), error_message_safe (nullable, scrubbed), input_tokens, output_tokens, cached_input_tokens, usage_estimated (bool), cost_micro_usd (bigint, nullable), latency_ms, ttft_ms (nullable), streamed (bool), cache_hit (bool), fallback_used (bool), fallback_from (nullable), fallback_reason (nullable), finish_reason (nullable), empty_or_truncated (bool), user_tag (nullable, from the `X-Gateway-User` request header, max 128 chars), feedback_score (smallint, nullable), request_hash (bytea).
Indexes: (project_id, created_at desc), (created_at), (model_used, created_at), (status, created_at). For large installs, partition by month (document it; not required for V1).

**request_content**: request_id (pk, fk), request_json (jsonb), response_json (jsonb). Only written when `log_content` is true. Deleted with the parent log row (cascade).

**budget_alert**: id, project_id, period (`daily` | `monthly`), period_start, threshold_percent, spend_micro_usd, budget_micro_usd, created_at, webhook_status (`pending` | `sent` | `failed` | `skipped`), webhook_attempts, last_error. Unique on (project_id, period, period_start, threshold_percent) so the same alert never fires twice.

**app_setting**: key (pk), value (jsonb). Holds retention days (default 30), demo mode flag, notification defaults.

## 5. API surface

### 5.1 Gateway API (auth: `Authorization: Bearer lgw_...`)

| Method + path | Purpose |
|---|---|
| `POST /v1/chat/completions` | OpenAI-style chat. Supports `stream: true`. Model string is `provider/model` (for example `openai/gpt-5-mini`) or a project alias. |
| `POST /v1/embeddings` | OpenAI-style embeddings. No fallback chain across providers with different vector sizes: fallback only within the same provider. |
| `GET /v1/models` | Models this project may use (from price table and credentials). |
| `POST /v1/feedback` | Body `{request_id, score: 1 | -1}`. Only for requests that belong to the calling project. |

Response headers on every gateway call: `X-Gateway-Request-Id`, `X-Gateway-Cache: hit|miss|bypass`, `X-Gateway-Model-Used`, `X-Gateway-Fallback: none|<from-model>`.
Error bodies follow the OpenAI error shape (`{"error": {"message", "type", "code"}}`) so existing SDKs handle them. Budget block returns HTTP 402-style semantics via `429` with `code: "budget_exceeded"` (use 429 for SDK retry compatibility but include `Retry-After` set to seconds until the budget period resets). Rate limit returns `429` with `Retry-After`.

Request header `X-Gateway-Cache: bypass` skips cache for that call. Request header `X-Gateway-User: <tag>` stores an end-user tag.

### 5.2 Admin API (auth: session cookie + CSRF header on writes)

| Group | Endpoints |
|---|---|
| Setup / auth | `GET /admin/setup/status`, `POST /admin/setup` (works only when no owner exists), `POST /admin/auth/login`, `POST /admin/auth/logout`, `GET /admin/auth/me`, `POST /admin/auth/change-password` |
| Projects | `GET/POST /admin/projects`, `GET/PATCH/DELETE(archive) /admin/projects/{id}` |
| Keys | `GET/POST /admin/projects/{id}/keys`, `POST /admin/keys/{id}/revoke`, `POST /admin/keys/{id}/rotate` |
| Project config | `GET/PUT /admin/projects/{id}/config` |
| Providers | `GET/POST /admin/providers`, `PATCH/DELETE /admin/providers/{id}`, `POST /admin/providers/{id}/test` |
| Prices | `GET/POST /admin/prices`, `PATCH/DELETE /admin/prices/{id}`, `POST /admin/prices/import` (JSON) |
| Requests | `GET /admin/requests` (filters + cursor pagination), `GET /admin/requests/{id}` |
| Stats | `GET /admin/stats/overview`, `/stats/timeseries`, `/stats/models`, `/stats/projects/{id}` (all accept `from`, `to`, `bucket`) |
| Alerts | `GET /admin/alerts`, `POST /admin/projects/{id}/webhook/test` |
| Settings | `GET/PUT /admin/settings` |
| Ops | `GET /healthz` (process alive), `GET /readyz` (DB + Redis reachable), `GET /metrics` (restricted: only reachable from the internal network, not through the public proxy) |

OpenAPI docs are served at `/admin/docs` only when `ENV=development`.

## 6. Key behaviours

**Model resolution.** `provider/model` goes to that provider. If the project has a fallback chain, the first entry is the primary when the requested model is not given. The requested model always goes first, then the chain entries in order (skipping duplicates), up to `max_fallbacks`.

**Fallback triggers.** Timeout, connection error, HTTP 429, HTTP 5xx, and a provider "overloaded" error. Never on HTTP 400/401/403 from the provider caused by the app's own bad request (those are returned as is). For streams, fallback is possible only **before the first byte is sent** to the client. After that, errors are logged and the stream ends with an error event.

**Chat adapters.** OpenAI and `openai_compatible`: native chat-completions format, with `stream_options.include_usage = true` injected for streams. Anthropic: native Messages API, translated to and from the OpenAI shape (system messages, tool calls, finish reasons). Google: native Gemini REST API (`generateContent` and `streamGenerateContent`), translated the same way. **Before coding each adapter, read the provider's current official API reference** (links in section 8) and follow it, not memory. If a provider returns no usage, estimate with tiktoken and set `usage_estimated = true`.

**Cost.** `cost = input_tokens * input_price + output_tokens * output_price` in integer micro-USD, using the price row for `(provider, model_used)`. Cached input tokens use the cached price when present. Use integer math with ceiling rounding.

**Cache key.** SHA-256 over: project id, endpoint, resolved model, canonical JSON of messages and generation parameters (sorted keys, no whitespace), and tool definitions. Includes the project id so projects never share cache entries. Streaming requests are cached too: the assembled answer is stored and replayed as a stream. A hit is logged with zero provider tokens counted as spent and `saved_cost_micro_usd` computed for the dashboard (store it as an extra column `saved_micro_usd` on `request_log`).

**Rate limit.** Per project, sliding window of 60 s in Redis using a Lua script (atomic). Limit comes from `rpm_limit`.

**Budget.** Redis counters `budget:{project}:{daily|monthly}:{period_start}` hold micro-USD spent. Updated after every call. Periods use UTC. When a threshold in `warn_thresholds` is crossed, insert one `budget_alert` row (unique constraint prevents duplicates) and send the webhook. If `block_at_limit` is true and spend is at or above the limit, new calls are refused until the period resets.

**Webhook.** POST JSON, signed with `X-Gateway-Signature: sha256=<hmac>` using the project's webhook secret. 3 attempts with exponential backoff. URL is validated against SSRF rules (see `03-security.md`).

**Quality signals.** Per model: error rate, fallback rate, p50/p95/p99 latency, average time to first token, empty/truncated rate, average feedback score. Percentiles use `percentile_cont` in SQL over the selected window.

**Demo mode.** A `mock` provider returns deterministic fake answers with realistic token counts and latencies, and can be told to fail on demand (header `X-Mock-Fail: 500|429|timeout`). `scripts/seed_demo.py` creates two sample projects with 7 days of generated history so the dashboard is full on first open. Demo mode never needs a real provider key. The mock provider is also the main tool for automated tests.

## 7. Folder structure

```
llm-gateway/
├── CLAUDE.md
├── AGENTS.md                      (same content as CLAUDE.md)
├── README.md
├── LICENSE
├── .env.example
├── docker-compose.yml             (production-like: caddy, backend, frontend, postgres, redis)
├── docker-compose.dev.yml         (dev overrides: hot reload, exposed ports)
├── Caddyfile
├── Makefile                       (make dev, test, lint, seed, migrate)
├── .github/workflows/ci.yml
├── .github/dependabot.yml
├── backend/
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── Dockerfile
│   ├── app/
│   │   ├── main.py                (app factory, lifespan, middleware)
│   │   ├── config.py              (pydantic-settings)
│   │   ├── deps.py                (FastAPI dependencies)
│   │   ├── logging_setup.py       (structlog + redaction)
│   │   ├── api/
│   │   │   ├── gateway/           (chat.py, embeddings.py, models.py, feedback.py)
│   │   │   └── admin/             (auth.py, projects.py, keys.py, providers.py, prices.py,
│   │   │                           requests.py, stats.py, alerts.py, settings.py, health.py)
│   │   ├── core/                  (security.py, crypto.py, rate_limit.py, budget.py, cache.py,
│   │   │                           pricing.py, routing.py, fallback.py, ssrf.py, errors.py)
│   │   ├── providers/             (base.py, openai.py, anthropic.py, google.py,
│   │   │                           openai_compatible.py, mock.py, registry.py)
│   │   ├── db/                    (base.py, session.py, models/*.py)
│   │   ├── schemas/               (pydantic request/response models)
│   │   ├── services/              (request_logger.py, alerts.py, retention.py, stats.py, webhook.py)
│   │   └── workers/               (scheduler.py)
│   ├── migrations/
│   ├── scripts/                   (seed_demo.py, seed_prices.py, bootstrap_owner.py)
│   ├── data/prices.seed.json
│   └── tests/                     (unit/, integration/, security/, load/)
├── frontend/
│   ├── package.json
│   ├── next.config.ts
│   ├── Dockerfile
│   ├── src/
│   │   ├── app/                   (App Router: (auth)/login, setup, (dash)/...)
│   │   ├── components/            (ui/ from shadcn, charts/, tables/, forms/)
│   │   ├── lib/                   (api client, formatters, query hooks)
│   │   └── styles/                (tokens.css)
│   └── tests/
└── docs/                          (this spec + architecture diagrams + versions.lock.md)
```

## 8. Seed price list

File: `backend/data/prices.seed.json`. Loaded once at first start (rows marked `is_seed = true`). The owner can edit or add rows. Values in USD per 1 million tokens. **These are a convenience, not a guarantee.** They were taken from third-party price trackers on 2026-10-03 because the official pricing pages could not be opened by the research tool. Sources disagree for some models (see notes). The build agent must open each official page, compare, and correct the file before release. The UI shows "seed price - verify" next to seed rows until the owner edits or confirms them.

| Provider | Model id | Input | Output | Cached input | Note |
|---|---|---|---|---|---|
| openai | gpt-5 | 1.25 | 10.00 | 0.125 | consistent across sources |
| openai | gpt-5-mini | 0.25 | 2.00 | 0.025 | consistent |
| openai | gpt-5-nano | 0.05 | 0.40 | 0.005 | consistent |
| openai | gpt-5.4 | 2.50 | 15.00 | 0.25 | consistent |
| openai | gpt-5.5 | 5.00 | 30.00 | 0.50 | consistent |
| anthropic | claude-haiku-4-5 | 1.00 | 5.00 | 0.10 | consistent |
| anthropic | claude-sonnet-5 | 2.00 | 10.00 | 0.20 | newer sources say 2/10; older sources list the previous Sonnet at 3/15. Verify. |
| anthropic | claude-opus-5-5 | 4.00 | 20.00 | 0.20 | released 2026-09-22 per trackers; verify |
| google | gemini-2.5-pro | 1.25 | 10.00 | 0.125 | prompts over 200K tokens cost more; V1 uses the lower tier and notes this |
| google | gemini-2.5-flash | 0.30 | 2.50 | 0.03 | one tracker says Google signalled deprecation; verify availability |
| google | gemini-2.5-flash-lite | 0.10 | 0.40 | 0.01 | |

Newer Gemini 3.x and OpenAI 5.6 models exist but sources conflicted on names and prices. They are left out of the seed on purpose. The owner adds them in Settings.

## 9. Sources (checked 2026-10-03)

- FastAPI latest release 0.136.3, 2026-05-23: https://pepy.tech/project/fastapi
- Next.js 16.3.6 and React 19.3.0 (framework changelog, Sept 2026): https://www.achromatic.dev/changelog/september-2026-nextjs-react-update ; Next.js 16 stable line: https://releases.sh/vercel/nextjs.md
- SQLAlchemy 2.0.x stable, 2.1 in beta: https://www.sqlalchemy.org/blog
- PostgreSQL 18 (released Sept 2025, 18.3 maintenance release): https://www.postgresql.org/docs/release/18.3/
- Pydantic 2.12 and Python 3.14 support notes (dependency update logs): https://github.com/Randroids-Dojo/typescript-and-python-bootstrap/pull/79
- Claude pricing (third party, current as of Oct 2026): https://benchlm.ai/anthropic/api-pricing ; https://www.tminusai.com/blog/claude-api-pricing-monthly-cost-2026 . Official page to check: https://platform.claude.com/docs/en/about-claude/pricing
- OpenAI pricing (third party): https://benchlm.ai/openai/api-pricing ; https://pricepertoken.com/pricing-page/model/openai-gpt-5.4 . Official page to check: https://openai.com/api/pricing/
- Gemini pricing (third party): https://www.cloudzero.com/blog/gemini-pricing/ ; https://pricepertoken.com/pricing-page/model/google-gemini-2.5-flash . Official page to check: https://ai.google.dev/gemini-api/docs/pricing
- Provider API references the agent must read before writing adapters: https://platform.openai.com/docs/api-reference , https://docs.claude.com/en/api/messages , https://ai.google.dev/gemini-api/docs

## 10. Key decisions and trade-offs

| Decision | Chosen | Rejected | Reason |
|---|---|---|---|
| Language | Python/FastAPI | Go | Faster for the owner to read, extend and review; the I/O-bound workload fits async Python. Overhead target (<50 ms) is measured by a load test. |
| Provider layer | Own thin adapters | A big multi-provider library | Smaller dependency surface, easier to audit, shows engineering depth |
| Log write path | In-memory queue + batch insert | Write per request | Keeps request latency flat |
| Worker | Scheduler inside the app | Celery | One process to run; enough for V1 |
| Auth for dashboard | Server-side sessions, httpOnly cookie | JWT in local storage | Revocable, safer against XSS token theft |
| Money | Integer micro-USD | Float / Decimal | No drift; fast aggregation |
| Cache | Exact match | Semantic | Predictable and safe; semantic is V2 |
| Deployment | Docker Compose + Caddy | Kubernetes | Right size for a self-hosted open-source tool |
