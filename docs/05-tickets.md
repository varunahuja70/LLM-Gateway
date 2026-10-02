# 05 - Tickets (build order)

Reads: all earlier docs. Build in order. Each ticket ends with its **done-when** check. Run lint, type check and tests before moving on. Commit after every ticket with the message `ticket NN: <title>`.

Rules for every ticket: follow `03-security.md`; add tests with the code; no secrets in code; update `docs/versions.lock.md` whenever a dependency is added.

---

## T01 - Project setup
**Depends on:** none
**Build:** Repo skeleton from the folder structure in `02-architecture.md`. Backend with uv, `pyproject.toml`, ruff and mypy strict config, pytest config. Frontend with the latest stable Next.js (TypeScript strict), Tailwind v4, shadcn/ui init, ESLint, Prettier, Vitest. `Makefile`, `.gitignore`, `.env.example`, `LICENSE` (MIT unless the owner chose otherwise), `.github/workflows/ci.yml` (lint, type check, tests, `pip-audit`, `npm audit`, gitleaks), `.github/dependabot.yml`. Create `docs/versions.lock.md` listing every pinned version with the command used to get it.
**Files:** repo root, `backend/`, `frontend/`, `.github/`
**Done when:** `make lint` and `make test` pass on the empty skeleton; CI file is valid.

## T02 - Docker Compose and config
**Depends on:** T01
**Build:** `docker-compose.yml` (caddy, backend, frontend, postgres, redis), dev override, Dockerfiles (multi-stage, non-root), `Caddyfile` routing `/v1/*` and `/admin/*` to the backend, the rest to the frontend, security headers. `backend/app/config.py` with pydantic-settings; app refuses to start on missing or weak `GATEWAY_MASTER_KEY`.
**Files:** compose files, Dockerfiles, `Caddyfile`, `config.py`, `main.py`, `api/admin/health.py`
**Done when:** `docker compose up` brings everything up; `/healthz` and `/readyz` respond; startup fails with a clear message when the master key is missing.

## T03 - Database models and migrations
**Depends on:** T02
**Build:** SQLAlchemy 2.0 async models for every table in `02-architecture.md` (including `audit_event` and `saved_micro_usd`). Alembic setup and the first migration. UUIDv7 id helper. Indexes as specified.
**Files:** `db/`, `migrations/`
**Done when:** `alembic upgrade head` and `alembic downgrade base` both work on a clean database; model tests pass.

## T04 - Crypto, security helpers and logging redaction
**Depends on:** T03
**Build:** `core/crypto.py` (AES-256-GCM with associated data, key versions), `core/security.py` (key generation, SHA-256 hashing, Argon2id, constant-time compare, session tokens), `core/ssrf.py` (URL validation as in `03-security.md`), `logging_setup.py` with structlog and the redaction filter.
**Files:** `core/crypto.py`, `core/security.py`, `core/ssrf.py`, `logging_setup.py`
**Done when:** security tests 3 and 6 from `03-security.md` and the redaction test pass.

## T05 - Owner setup, login and sessions
**Depends on:** T04
**Build:** `/admin/setup`, login, logout, me, change-password; session table logic, cookie flags, CSRF and Origin checks, login rate limit, audit events. FastAPI dependencies `require_owner` and `require_csrf`.
**Files:** `api/admin/auth.py`, `deps.py`, `services/audit.py`
**Done when:** security tests 4, 5 and 10 pass.

## T06 - Projects, gateway keys and project config API
**Depends on:** T05
**Build:** CRUD for projects, keys (create, list, revoke, rotate, show once), project config get/put with validation. Gateway key auth dependency with Redis cache of key lookups (60 s) and immediate invalidation on revoke.
**Files:** `api/admin/projects.py`, `keys.py`, `schemas/`, `core/security.py` additions
**Done when:** tests for key lifecycle pass; revoked key stops working immediately.

## T07 - Providers, credentials and price table
**Depends on:** T06
**Build:** Provider credential CRUD (encrypt on save, `key_last4` only on read), connection test endpoint, price table CRUD and JSON import, `data/prices.seed.json` and `seed_prices.py` (run at first start). Read each provider's official pricing page and correct the seed file; keep `source_url` and `verified_on`.
**Files:** `api/admin/providers.py`, `prices.py`, `core/pricing.py`, `data/prices.seed.json`
**Done when:** a stored key is never returned by any endpoint; cost calculation unit tests pass, including unknown model returning `None`.

## T08 - Provider adapters
**Depends on:** T07
**Build:** `providers/base.py` interface (chat, stream chat, embeddings, normalized usage and errors). Adapters: `mock` (deterministic, can fail on demand), `openai`, `openai_compatible`, `anthropic`, `google`. Read each provider's current official API reference before coding. Shared httpx client with pooling and timeouts. Usage extraction for streams (inject `include_usage` for OpenAI-style; read usage events for Anthropic and Google). tiktoken fallback with `usage_estimated`.
**Files:** `providers/*`
**Done when:** respx-based tests cover non-streaming, streaming, error mapping, and missing-usage fallback for every adapter.

## T09 - Gateway chat endpoint (core path)
**Depends on:** T08
**Build:** `POST /v1/chat/completions` with key auth, model resolution, call, streaming passthrough in the OpenAI SSE format, standard headers, OpenAI-shaped errors, body size limit, `max_tokens` cap. `GET /v1/models`. In-memory log queue and batch writer to `request_log` (`services/request_logger.py`) with graceful flush on shutdown. Cost calculation attached to each record.
**Files:** `api/gateway/chat.py`, `models.py`, `core/routing.py`, `services/request_logger.py`
**Done when:** a call through the mock provider (streaming and not) returns correct output, appears in `request_log` within 2 seconds with right tokens and cost; official OpenAI Python SDK works against the gateway in a test.

## T10 - Rate limit, budget enforcement and alerts
**Depends on:** T09
**Build:** Redis Lua sliding-window rate limiter; budget counters (daily and monthly, UTC), threshold crossing with unique `budget_alert` rows, block-at-limit behaviour with `Retry-After`, signed webhook delivery with retries, webhook test endpoint, reconcile job. Scheduler setup (`workers/scheduler.py`).
**Files:** `core/rate_limit.py`, `core/budget.py`, `services/alerts.py`, `services/webhook.py`, `workers/scheduler.py`
**Done when:** tests prove: limit enforced under concurrency, each threshold fires exactly once, block works and resumes at next period, webhook signature verifies, SSRF-blocked webhook URL is rejected.

## T11 - Fallback
**Depends on:** T09
**Build:** `core/fallback.py`: chain building, triggers (timeout, 429, 5xx, overloaded), max fallbacks, no fallback after first streamed byte, fallback fields in the log, `X-Gateway-Fallback` header. Embeddings fallback only inside the same provider.
**Files:** `core/fallback.py`, `api/gateway/chat.py` updates, `api/gateway/embeddings.py`
**Done when:** with the mock provider set to fail (`X-Mock-Fail`), the app still gets an answer from the next model and the log records provider, reason and original model; 400-class provider errors do not trigger fallback.

## T12 - Cache
**Depends on:** T09
**Build:** `core/cache.py`: key as specified, TTL, per-project toggle, bypass header, streaming replay, `saved_micro_usd`, cache hit logged with zero spend. Embeddings caching too.
**Files:** `core/cache.py`, gateway updates
**Done when:** repeat call is served from cache and is much faster; cache isolation test (security test 7) passes; stats can sum savings.

## T13 - Feedback and quality signals
**Depends on:** T09
**Build:** `POST /v1/feedback`; compute `empty_or_truncated` at log time (empty content or `finish_reason` of length); user tag header handling.
**Files:** `api/gateway/feedback.py`, logger updates
**Done when:** feedback only works on the caller's own requests; wrong project gets `404`.

## T14 - Requests and stats API
**Depends on:** T13, T12, T11
**Build:** `/admin/requests` (filters, cursor pagination, detail) and `/admin/stats/*` (overview, timeseries with buckets, per-model quality, per-project) using SQL aggregates and `percentile_cont`. Add needed indexes. Retention job and "delete project data" action.
**Files:** `api/admin/requests.py`, `stats.py`, `services/stats.py`, `services/retention.py`
**Done when:** stats match a hand-computed fixture dataset exactly; retention removes only old rows (and their content rows).

## T15 - Prometheus metrics, structured logging, demo seed
**Depends on:** T14
**Build:** `/metrics` (request count, latency histogram, provider errors, queue depth, cache hits, budget blocks), internal-only. `scripts/seed_demo.py` (2 projects, 7 days of realistic history, a few fallbacks, errors, alerts), demo mode flag and `DemoBanner` data.
**Files:** `main.py` middleware, `scripts/seed_demo.py`
**Done when:** `make seed` fills the database; metrics endpoint is not reachable through Caddy.

## T16 - Frontend foundation
**Depends on:** T05
**Build:** App shell, sidebar/top bar, theme tokens from `04-frontend.md`, API client (CSRF, error handling, generated types from OpenAPI), TanStack Query setup, auth guard, `/setup` and `/login` screens, shared components (`KpiCard`, `EmptyState`, `ErrorState`, `ConfirmDialog`, `SecretRevealDialog`, `CodeSnippet`).
**Files:** `frontend/src/...`
**Done when:** you can set up the owner, log in, log out; CSP headers set; axe accessibility check has no serious issues on these screens.

## T17 - Overview, projects and project detail screens
**Depends on:** T16, T14
**Build:** Overview, projects list, project detail with Usage, Keys, Config (including fallback chain editor and budget bar), and Quick start tabs.
**Done when:** every state (loading, empty, error, success) is implemented and manually checked; creating a key shows the secret once.

## T18 - Request explorer, models and alerts screens
**Depends on:** T17
**Build:** Request explorer with filters and detail sheet, Models comparison, Alerts page.
**Done when:** filters and pagination work against demo data; table view toggle exists for charts.

## T19 - Settings screens
**Depends on:** T17
**Build:** Providers (add, test, disable), Prices (editable, seed flag, import), Retention, Account.
**Done when:** adding a provider key works and the key is never displayed again; unpriced models show the warning in the dashboard.

## T20 - Hardening, load test and end-to-end checks
**Depends on:** T15, T18, T19
**Build:** Run every security test from `03-security.md` section 11 and fix gaps. Load test with a script (Locust or k6 via container) against the mock provider, measuring gateway overhead and writing the result to `docs/benchmarks.md` (target: p95 overhead under 50 ms). Playwright smoke flow.
**Done when:** all tests pass in CI; benchmark file exists with real measured numbers (never invented).

## T21 - Documentation and open-source packaging
**Depends on:** T20
**Build:** `README.md` (what it is, screenshots taken from the demo, 5-minute quick start, architecture diagram, configuration table, security notes, limits and trade-offs), `CONTRIBUTING.md`, `SECURITY.md` (how to report issues), `CODE_OF_CONDUCT.md`, issue and PR templates, `docs/` cleanup, release notes for v0.1.0, `docs/guides/` with: connect the OpenAI SDK, connect the Anthropic-style apps through the OpenAI format, and run with local models.
**Done when:** a fresh clone reaches a working demo dashboard following only the README, in under 10 minutes.
