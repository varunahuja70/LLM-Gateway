# LLM Gateway - Full Spec Bundle

This single file contains every spec file. Each file starts with a marker line `<!-- FILE: path -->` and ends with `<!-- END FILE -->`. Split them into the paths shown.

<!-- FILE: CLAUDE.md -->
# LLM Gateway

Open-source, self-hosted gateway between apps and AI model providers. Logs tokens, latency, cost and errors per project. Adds budgets, alerts, model fallback and caching. Has a dashboard.

## Read first (the specs are the source of truth)
- `docs/01-prd.md` - what it does
- `docs/02-architecture.md` - stack, data model, API, folder map, seed prices, sources
- `docs/03-security.md` - security rules and required tests
- `docs/04-frontend.md` - screens, design tokens, states
- `docs/05-tickets.md` - build order (one ticket at a time)
- `docs/06-deployment.md` - env vars, deploy, backup, monitoring

If code and docs disagree, stop and ask. Do not silently change the stack, data model or folder layout.

## Stack
Backend: Python 3.13, FastAPI, SQLAlchemy 2.0 async + asyncpg, Alembic, Pydantic v2, httpx, Redis, PostgreSQL 18, structlog, prometheus-client, APScheduler. Tooling: uv, ruff, mypy strict, pytest.
Frontend: Next.js 16 (App Router, TypeScript strict), React 19, Tailwind v4, shadcn/ui, Recharts, TanStack Query, Vitest, Playwright. Tooling: pnpm.
Infra: Docker Compose, Caddy, GitHub Actions.
Exact versions: record in `docs/versions.lock.md`. Install the latest stable, never copy versions from memory.

## Folder map
`backend/app/{api,core,providers,db,schemas,services,workers}`, `backend/tests`, `backend/migrations`, `frontend/src/{app,components,lib,styles}`, `docs/`. Full tree in `docs/02-architecture.md` section 7.

## Commands
- `make dev` - start everything with hot reload
- `make test` - backend and frontend tests
- `make lint` - ruff, mypy, eslint, tsc
- `make migrate` - run Alembic migrations
- `make seed` - load demo data

## Always
- Work on one ticket from `docs/05-tickets.md` at a time, in order. Check its "done when" before moving on.
- Write tests with the code. Run `make lint` and `make test` before each commit.
- Commit after each ticket: `ticket NN: <title>`.
- Store money as integer micro-USD. Unknown model price means cost is NULL, never 0.
- Keep logging and stats off the request path (queue + batch writer).
- Use `provider/model` naming and OpenAI-shaped errors on the gateway API.
- Read the provider's official API docs before writing or changing an adapter.
- Update `docs/versions.lock.md` whenever a dependency is added or changed.
- Real numbers only in benchmarks and docs. Measure, never invent.

## Never
- Never log or return provider keys, gateway keys, passwords or cookies. Redaction filter must stay on.
- Never store prompts or responses unless the project has `log_content` on.
- Never build SQL with string formatting. Use the ORM or bound parameters.
- Never skip the security tests in `docs/03-security.md` section 11.
- Never add telemetry, analytics, external fonts or third-party scripts.
- Never commit `.env` or any real secret.
- Never add a dependency, service or feature that is not in the docs without asking.
- Never expose `/metrics`, `/admin/docs`, Postgres or Redis publicly.

<!-- END FILE -->

<!-- FILE: AGENTS.md -->
# LLM Gateway

Open-source, self-hosted gateway between apps and AI model providers. Logs tokens, latency, cost and errors per project. Adds budgets, alerts, model fallback and caching. Has a dashboard.

## Read first (the specs are the source of truth)
- `docs/01-prd.md` - what it does
- `docs/02-architecture.md` - stack, data model, API, folder map, seed prices, sources
- `docs/03-security.md` - security rules and required tests
- `docs/04-frontend.md` - screens, design tokens, states
- `docs/05-tickets.md` - build order (one ticket at a time)
- `docs/06-deployment.md` - env vars, deploy, backup, monitoring

If code and docs disagree, stop and ask. Do not silently change the stack, data model or folder layout.

## Stack
Backend: Python 3.13, FastAPI, SQLAlchemy 2.0 async + asyncpg, Alembic, Pydantic v2, httpx, Redis, PostgreSQL 18, structlog, prometheus-client, APScheduler. Tooling: uv, ruff, mypy strict, pytest.
Frontend: Next.js 16 (App Router, TypeScript strict), React 19, Tailwind v4, shadcn/ui, Recharts, TanStack Query, Vitest, Playwright. Tooling: pnpm.
Infra: Docker Compose, Caddy, GitHub Actions.
Exact versions: record in `docs/versions.lock.md`. Install the latest stable, never copy versions from memory.

## Folder map
`backend/app/{api,core,providers,db,schemas,services,workers}`, `backend/tests`, `backend/migrations`, `frontend/src/{app,components,lib,styles}`, `docs/`. Full tree in `docs/02-architecture.md` section 7.

## Commands
- `make dev` - start everything with hot reload
- `make test` - backend and frontend tests
- `make lint` - ruff, mypy, eslint, tsc
- `make migrate` - run Alembic migrations
- `make seed` - load demo data

## Always
- Work on one ticket from `docs/05-tickets.md` at a time, in order. Check its "done when" before moving on.
- Write tests with the code. Run `make lint` and `make test` before each commit.
- Commit after each ticket: `ticket NN: <title>`.
- Store money as integer micro-USD. Unknown model price means cost is NULL, never 0.
- Keep logging and stats off the request path (queue + batch writer).
- Use `provider/model` naming and OpenAI-shaped errors on the gateway API.
- Read the provider's official API docs before writing or changing an adapter.
- Update `docs/versions.lock.md` whenever a dependency is added or changed.
- Real numbers only in benchmarks and docs. Measure, never invent.

## Never
- Never log or return provider keys, gateway keys, passwords or cookies. Redaction filter must stay on.
- Never store prompts or responses unless the project has `log_content` on.
- Never build SQL with string formatting. Use the ORM or bound parameters.
- Never skip the security tests in `docs/03-security.md` section 11.
- Never add telemetry, analytics, external fonts or third-party scripts.
- Never commit `.env` or any real secret.
- Never add a dependency, service or feature that is not in the docs without asking.
- Never expose `/metrics`, `/admin/docs`, Postgres or Redis publicly.

<!-- END FILE -->

<!-- FILE: docs/01-prd.md -->
# 01 - Product Requirements (PRD)

Working name: **LLM Gateway**
Status: Draft for review
Track: Full (login, database, multiple projects). No payments.

> Rule for this document: behaviour only. No technology names here. The stack is chosen in `02-architecture.md`.

## One-liner

An open-source gateway that sits between an app and its AI model providers. It records the tokens, speed, cost and errors of every AI call, per project, and adds budget limits, automatic fallback and caching, with a dashboard to see it all.

## Problem

Developers who use AI models in several apps cannot easily answer simple questions:

- How much did each app spend this week?
- Which model is slow or failing?
- Why did the bill suddenly jump?
- What happens to my app when one provider goes down?

Today they read separate provider dashboards, write their own logging, and find out about overspending after the bill arrives.

## Target user

**Primary:** A solo developer, indie founder or small team running one or more apps that call AI model providers.

**Secondary:** Open-source contributors and engineers who want to read or extend a clean gateway codebase.

**Not for:** Large companies needing enterprise single sign-on, billing to end customers, or a hosted multi-company service. V1 is self-hosted by one owner.

## Core features (V1)

### 1. One entry point for AI calls
- The app sends its AI requests to the gateway instead of directly to the provider.
- The request format follows the common chat-completion format that most apps already use, so switching needs only a changed address and key.
- Streaming responses work the same as non-streaming ones.
- Supports at least three providers in V1 (for example OpenAI, Anthropic, Google Gemini).

### 2. Projects and keys
- The owner creates **projects** (one per app).
- Each project gets its own gateway key. Keys are shown once, can be revoked, and can be rotated.
- The owner adds provider keys once in the gateway. Apps never need to hold them. Stored provider keys are never shown again in full.

### 3. Logging of every call
For each request the gateway records: project, time, provider, model requested, model actually used, input tokens, output tokens, latency (total and time to first token for streams), cost, status, error type, whether it came from cache, and whether a fallback was used.
- Prompt and response text are **not stored by default**. The owner can switch on content logging per project.
- Old logs are removed automatically after a retention period the owner sets.

### 4. Cost calculation
- Cost is worked out from a price list per model.
- The price list ships with sensible defaults and the owner can edit it or add new models.
- Cost shown is an estimate and is labelled as such.

### 5. Budgets and alerts
- Each project can have a daily and a monthly budget.
- The owner sets warning levels (for example 50%, 80%, 100%).
- When a warning level is crossed, the owner is notified in the dashboard and by a webhook message.
- Each project chooses what happens at 100%: **only alert**, or **block new calls** until the period resets.

### 6. Model fallback
- Each project can define an ordered list of models to try.
- If the first model fails, times out or is rate limited, the gateway tries the next one automatically.
- The log shows which model finally answered and why the fallback happened.
- Each project sets a limit on how many fallbacks are allowed per request.

### 7. Caching
- When the same request arrives again, the gateway can return the saved answer without calling the provider.
- Caching is off by default and switched on per project, with a time-to-live the owner sets.
- The dashboard shows how many calls and how much money the cache saved.
- V1 matches only identical requests. Similar-meaning matching is a later feature.

### 8. Quality signals
- Quality is tracked with things the gateway can measure: error rate, fallback rate, latency percentiles, and empty or cut-off answers.
- The app can also send a simple **thumbs up / thumbs down** score for a past request. The dashboard shows score by model.

### 9. Rate limits
- Each project has a limit on requests per minute so one app cannot starve the others or run up cost by mistake.

### 10. Dashboard
Screens the owner can use:
- **Overview:** total spend, calls, error rate, average speed, savings from cache, trend over time.
- **Project page:** the same numbers for one project, plus budget progress.
- **Request explorer:** a searchable, filterable list of calls with a detail view.
- **Models:** compare models by cost, speed, errors and score.
- **Budgets and alerts:** set and view them.
- **Settings:** providers, price list, keys, retention, notification address.

### 11. Owner login
- The dashboard needs a login. V1 has one owner account created during first setup. Optional extra team members are a later feature.

### 12. Open-source packaging
- Starts with a single command on a fresh machine.
- Comes with sample data and a demo mode so a visitor can see a working dashboard without any provider key.
- Clear documentation, contribution guide and licence.

## Non-goals (V1)

- No billing or charging of end customers.
- No hosted multi-company (SaaS) version.
- No similar-meaning (semantic) cache.
- No prompt library or prompt versioning.
- No content filtering, personal-data redaction or guardrails.
- No team roles beyond the single owner.
- No image, audio or video model support. Text chat and embeddings only.

## Main user flows

**First setup**
1. Owner starts the gateway and opens the dashboard.
2. Owner creates the owner account.
3. Owner adds one or more provider keys.
4. Owner creates a project and copies its gateway key.
5. Owner changes the app to use the gateway address and key. First call appears in the dashboard within seconds.

**Normal call**
1. App sends a request with its project key.
2. Gateway checks key, rate limit and budget.
3. Gateway checks cache. If found, returns it and logs a cache hit.
4. Otherwise it calls the provider, streams the answer back, and logs the result.

**Provider failure**
1. Provider returns an error or times out.
2. Gateway moves to the next model in the project's list.
3. App still receives an answer. Log records the fallback and the reason.

**Budget crossed**
1. Spend passes a warning level.
2. Owner sees an alert in the dashboard and receives a webhook message.
3. At 100%, the project either keeps running (alert only) or new calls are refused with a clear message.

## Success criteria

- A new user goes from start to first logged call in under 10 minutes.
- The gateway adds very little delay: under 50 ms extra on a typical request, not counting the provider's own time.
- Logged tokens match the provider's reported usage on every successful call.
- Fallback works in a test where the first provider is made to fail.
- Budget block works: calls are refused after the limit and resume at the next period.
- No provider key or gateway key ever appears in logs, error messages or the dashboard.
- The project has working automated tests and a clean install guide that another developer can follow without help.

## Open questions

1. Which providers are mandatory for V1 besides the three listed?
2. Should the owner be able to add any provider that uses the common chat format (for example local or self-hosted models) in V1?
3. Is the webhook enough for alerts in V1, or is email also required?
4. Which open-source licence: MIT or Apache 2.0?
5. Final project name for the repository.

<!-- END FILE -->

<!-- FILE: docs/02-architecture.md -->
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

<!-- END FILE -->

<!-- FILE: docs/03-security.md -->
# 03 - Security

Reads: `01-prd.md`, `02-architecture.md`. Security is a V1 requirement, not a later phase. Every rule here must have a test (see tickets).

## 1. What we protect

1. Provider API keys (they cost real money if stolen).
2. Gateway keys (they let someone spend the owner's money through the gateway).
3. Prompt and response content (may hold private data).
4. The owner's dashboard session.
5. Availability: one noisy or malicious client must not take the gateway down.

## 2. Actors and permissions

| Actor | Auth | Can do |
|---|---|---|
| App (project key) | `Authorization: Bearer lgw_...` | Call `/v1/*` for its own project only. Send feedback for its own requests only. Cannot read logs, stats or config. |
| Owner | Session cookie + CSRF header | Everything under `/admin/*`. |
| Anonymous | none | `GET /healthz`, `GET /admin/setup/status`, `POST /admin/auth/login`, and `POST /admin/setup` only while no owner exists. |
| Internal monitor | network-level | `GET /metrics`, only from the internal Docker network. |

A gateway key is bound to one project. A request that names another project's data gets `404`, never `403`, so IDs cannot be probed.

## 3. Authentication

**Owner login**
- Passwords hashed with Argon2id (library defaults or stronger). Minimum 12 characters, checked against a short list of common passwords.
- First-run setup creates the owner. After one owner exists, the setup endpoint returns `404`.
- Login failures: rate limit 5 attempts per 15 minutes per IP and per account (Redis). Same error message for unknown email and wrong password. Constant-time comparison. A small delay on failure.
- Session: random 256-bit token in an `httpOnly`, `Secure`, `SameSite=Lax` cookie named `__Host-session`. Only the hash of the token is stored. Idle timeout 8 hours, absolute timeout 7 days. New session on login (no session fixation). Logout deletes the row. Changing the password revokes all sessions.
- CSRF: every state-changing admin request (POST, PUT, PATCH, DELETE) must carry `X-CSRF-Token` matching the session's token, and the `Origin` header must match the configured public URL.

**Gateway keys**
- 256 bits of randomness, format `lgw_` + token. Stored as SHA-256 hash only. Lookup by hash. Prefix (first 8 chars) kept for display.
- Shown once on creation or rotation. Revoke takes effect immediately (the Redis auth cache entry is deleted on revoke; cache TTL is at most 60 seconds as a safety net).
- Optional expiry date. `last_used_at` updated at most once per minute.

## 4. Secrets handling

- Provider keys are encrypted with AES-256-GCM before saving. A random 96-bit nonce per record. The record's id is used as associated data so ciphertexts cannot be swapped between rows.
- The master key comes from the environment variable `GATEWAY_MASTER_KEY` (32 random bytes, base64). The app refuses to start without it, or if it is weak or still the example value.
- `key_version` supports rotation: `scripts/rotate_master_key.py` re-encrypts all rows with a new key.
- Provider keys are decrypted only in memory at call time, and cached in memory for a short time (60 s max). They are never logged, never returned by any API (only `key_last4`), and never put in exception messages.
- `.env` is git-ignored. `.env.example` has no real values. CI runs a secret scanner (gitleaks) on every push.
- Webhook secrets are stored encrypted the same way.

## 5. Input validation and limits

- All request bodies are validated by Pydantic models with strict types, maximum string lengths and maximum list sizes.
- Maximum request body size on the gateway: 4 MB by default (configurable), enforced before parsing. Admin: 1 MB.
- Maximum `max_tokens`, `n`, and message count per project are configurable, with safe defaults, so one bad request cannot run up a huge bill.
- Query parameters for lists have page size caps (max 200) and use cursor pagination. Sort fields come from an allow-list.
- All database access uses the ORM or bound parameters. No string-built SQL anywhere. A test greps for raw SQL strings with formatting.
- Provider response bodies are treated as untrusted: size-capped, parsed defensively, and never reflected into HTML.
- Error messages returned to apps never include internal stack traces, provider keys, or raw provider payloads. Provider error text is passed through a scrubber that removes anything that looks like a key.

## 6. Network safety (SSRF)

Two places let the owner supply a URL: `openai_compatible` provider base URL, and the project webhook URL.
- Allow only `https` (and `http` only for `localhost` when the explicit setting `ALLOW_PRIVATE_PROVIDER_URLS=true` is on, meant for local models).
- Resolve the host and **block** loopback, private (RFC 1918), link-local (including 169.254.169.254 cloud metadata), multicast and reserved ranges, for both IPv4 and IPv6, unless the allow setting is on.
- Check again at connect time (DNS rebinding), and do not follow redirects for webhooks. Provider calls follow no redirects either.
- Timeouts on every outbound call: connect 5 s, total from project config (default 60 s). Webhooks: 5 s total, response body ignored.

## 7. Transport and browser hardening

- HTTPS only in production (Caddy, automatic certificates). HSTS enabled. HTTP redirects to HTTPS.
- Security headers on the dashboard: `Content-Security-Policy` (no inline scripts, nonce-based where needed), `X-Content-Type-Options: nosniff`, `Referrer-Policy: same-origin`, `Permissions-Policy` locked down, `frame-ancestors 'none'`.
- CORS: closed by default on both gateway and admin. A project may add allowed origins in settings only if browser apps call the gateway directly (not recommended; the docs say keep the key server-side).
- No secrets in URLs or query strings.
- The frontend never stores tokens in local storage. It relies on the httpOnly cookie.
- Admin responses carry `Cache-Control: no-store`.

## 8. Logging and privacy

- Prompt and response bodies are **not stored by default** (`log_content = false`).
- When content logging is on, the project page shows a clear warning, and content rows follow the same retention period as logs.
- A logging filter redacts: `Authorization` headers, any string starting with `lgw_`, `sk-`, `sk-ant-`, `AIza`, cookie values, and fields named `password`, `key`, `secret`, `token`. Tests prove redaction.
- `error_message_safe` in request logs is the scrubbed text only.
- Audit trail: a small `audit_event` table records owner actions (login, key created/revoked/rotated, provider added/removed, config changed, price changed) without secret values.
- Retention: default 30 days, configurable, enforced nightly. A "delete all data for a project" admin action exists.

## 9. Rate limiting and abuse cases

| Abuse case | Defence |
|---|---|
| Stolen gateway key spams the gateway | Per-project requests-per-minute limit; budget block; owner revokes key; `last_used_at` and logs show misuse |
| Attacker guesses gateway keys | 256-bit keys; failed auth rate limited per IP (Redis); same response for unknown and revoked keys |
| Login brute force | Per-IP and per-account limits, Argon2id cost, delay on failure |
| Huge prompts or `max_tokens` to burn money | Body size cap, per-project `max_tokens` cap, budget block |
| Cache poisoning between projects | Project id is part of the cache key |
| Cache returns another user's private answer | Cache is per project and off by default; UI warns that identical requests share answers inside a project |
| Webhook used to hit internal services | SSRF rules above, no redirects, signed payloads |
| Malicious provider response (huge or malformed) | Size caps, strict parsing, timeouts |
| Slow-loris style clients | Server timeouts in Uvicorn and Caddy |
| Dependency vulnerability | Dependabot, `pip-audit` and `npm audit` in CI (fail on high severity) |
| Log injection | Structured JSON logs; user-supplied strings are escaped by the logger |
| Header injection through `X-Gateway-User` | Length cap, allow-list of characters |
| Mass assignment on admin APIs | Explicit Pydantic input models, no passing raw dicts to the ORM |

## 10. Container and deployment security

- Containers run as a non-root user, with a read-only root filesystem where possible, and no extra capabilities.
- Postgres and Redis are not exposed on public ports. Redis requires a password.
- Only Caddy publishes ports 80 and 443.
- `/metrics` and `/admin/docs` are not reachable through the public proxy.
- Base images pinned by version and rebuilt regularly. An image vulnerability scan (Trivy) runs in CI.
- Backups: documented `pg_dump` routine in `06-deployment.md`. Backups hold encrypted provider keys, so they are useless without the master key. Store the master key separately.

## 11. Required security tests

1. Gateway: missing key, malformed key, revoked key, expired key, key of another project all fail correctly.
2. Gateway key and provider key never appear in logs, errors, API responses (scan test over captured logs and responses).
3. Provider key round trip: encrypt, store, decrypt works; tampered ciphertext fails; swapping ciphertext between rows fails.
4. Login: rate limit works; session cookie flags are right; CSRF missing or wrong fails; origin mismatch fails.
5. Setup endpoint returns `404` after the first owner exists.
6. SSRF: loopback, private ranges, metadata address, IPv6 variants, decimal and hex IP forms, and redirect to private IP are all blocked.
7. Cache isolation: same request in two projects never shares an entry.
8. Budget block and rate limit cannot be bypassed by changing header case or sending concurrent requests (concurrency test).
9. Request size limit and `max_tokens` cap enforced.
10. Admin endpoints return `401` without a session, and gateway keys never work on `/admin/*`.

<!-- END FILE -->

<!-- FILE: docs/04-frontend.md -->
# 04 - Frontend

Reads: `01-prd.md`, `02-architecture.md`. The dashboard is a Next.js app that talks to the admin API through the same origin (Caddy routes `/admin/*` to the backend), so the session cookie works without CORS.

## 1. Design direction

Premium, minimal, calm. The reference quality bar is Linear and Vercel dashboards. Dark theme first, light theme supported. Lots of whitespace, thin borders, one accent colour, restrained motion. Numbers are the hero: large, tabular, easy to scan. No decorative gradients, no emoji icons, no stock illustrations.

## 2. Design tokens (in `src/styles/tokens.css`, used through Tailwind v4 theme variables)

| Token | Dark | Light |
|---|---|---|
| background | `#0A0A0B` | `#FFFFFF` |
| surface | `#111113` | `#FAFAFA` |
| surface-raised | `#17171A` | `#FFFFFF` |
| border | `#26262B` | `#E7E7EA` |
| text | `#EDEDEF` | `#0B0B0C` |
| text-muted | `#8B8B93` | `#6B6B73` |
| accent | `#6E6AFF` | `#4F46E5` |
| success | `#3DD68C` | `#16A34A` |
| warning | `#F5A524` | `#D97706` |
| danger | `#F5555D` | `#DC2626` |

- Font: Inter for UI, JetBrains Mono for keys, IDs and code. Load both with `next/font` (self-hosted by Next, no external requests). All numbers use `font-variant-numeric: tabular-nums`.
- Type scale: 12 / 13 / 14 / 16 / 20 / 28 / 36 px. Radius: 8 px cards, 6 px inputs, full for pills. Spacing on a 4 px grid.
- Motion: 150 ms ease-out for hover and focus, 200 ms for panels. All motion respects `prefers-reduced-motion`.
- Chart colours come from a fixed 6-colour palette that works for colour-blind users; the series are also distinguished by legend labels, never by colour alone.

## 3. Screens

1. **First-run setup** (`/setup`): create owner (email, password with strength hint). Only reachable when no owner exists.
2. **Login** (`/login`).
3. **Overview** (`/`): date range picker (24h, 7d, 30d, custom). KPI row: total spend, calls, error rate, p95 latency, cache savings. A spend-over-time chart, a calls-and-errors chart, a "top projects" list, a "top models" list, and a recent alerts strip.
4. **Projects list** (`/projects`): table with spend (period), budget bar, calls, error rate. "New project" button.
5. **Project detail** (`/projects/[id]`): tabs: **Usage** (KPIs + charts), **Requests** (filtered list), **Keys** (create, revoke, rotate, show-once dialog), **Config** (budget, thresholds, block toggle, fallback chain editor with drag to reorder, cache, rate limit, content logging with warning, webhook), **Quick start** (copy-paste snippets for curl, Python and JavaScript pointing to the gateway).
6. **Request explorer** (`/requests`): filters (project, model, provider, status, cache hit, fallback used, date range, text search by request id or user tag), cursor-paginated table, row click opens a side panel with the full detail (timings, tokens, cost, fallback story, feedback, content if stored).
7. **Models** (`/models`): comparison table (cost per 1K calls, average tokens, p50/p95 latency, TTFT, error rate, fallback rate, feedback score) with sortable columns and a small bar visual per metric.
8. **Budgets and alerts** (`/alerts`): history of alerts with status of the webhook, and a per-project budget overview.
9. **Settings** (`/settings`): Providers (add, test connection, disable), Prices (editable table, seed rows flagged "seed price - verify", import JSON), Retention, Account (change password), About (version, demo-mode badge).

## 4. Component inventory

Built on shadcn/ui primitives: Button, Input, Select, Dialog, Sheet (side panel), Tabs, Table, Badge, Tooltip, Toast, Skeleton, DropdownMenu, Switch, Calendar and DateRangePicker, Command palette (optional).
Custom: `KpiCard`, `SpendChart`, `CallsChart`, `BudgetBar` (colour changes at warning thresholds), `ModelTable`, `RequestTable`, `RequestDetailSheet`, `FallbackChainEditor`, `SecretRevealDialog` (show once, copy button, "I saved it" checkbox before close), `EmptyState`, `ErrorState`, `ConfirmDialog` (type project name to confirm destructive actions), `CodeSnippet` (copy button), `DemoBanner`.

## 5. States (every screen and component must define all four)

| State | Behaviour |
|---|---|
| Loading | Skeleton shapes that match the final layout. No spinners for page-level loads. |
| Empty | Short sentence plus the single next action (for example "Create your first project"). On a fresh install with demo mode, offer a "Load demo data" button. |
| Error | Plain message, "Try again" button, request id shown in muted text for debugging. 401 redirects to login. |
| Success | Subtle toast for saves. Never block the screen. |

Money is shown in USD with 2 decimals above $1, up to 6 decimals below, and an "estimated" tooltip. Unknown cost shows "unpriced" with a link to the price settings. Latency shows ms below 1 s and seconds above.

## 6. Responsive behaviour

Desktop first, usable down to 360 px wide. Sidebar collapses to a top bar with a menu sheet below 768 px. Tables become horizontally scrollable inside their container (page never scrolls sideways). Charts resize to the container. Touch targets at least 44 px on mobile.

## 7. Accessibility floor

- WCAG 2.2 AA colour contrast in both themes.
- Full keyboard use: visible focus ring (2 px accent), logical tab order, dialogs trap focus and return it, Escape closes sheets and dialogs.
- All icons that carry meaning have text labels or `aria-label`. Charts have a text summary and a "view as table" toggle.
- Forms: labels tied to inputs, errors linked with `aria-describedby`, errors announced politely.
- Respect `prefers-reduced-motion` and `prefers-color-scheme` (with a manual theme switch stored in a cookie).

## 8. Frontend rules

- TypeScript strict. No `any`. API types generated from the backend OpenAPI schema (`openapi-typescript`) so the two cannot drift.
- All server data goes through TanStack Query hooks in `src/lib/queries`. No fetch calls inside components.
- CSRF token read from a non-httpOnly companion cookie or the `/admin/auth/me` response and sent as `X-CSRF-Token` by the API client.
- Secrets (new keys) live only in component state while the dialog is open. Never in URL, storage or query cache.
- No third-party scripts, analytics or external fonts. The strict CSP depends on this.
- Unit tests for formatters and the fallback chain editor. One Playwright smoke test: setup, login, create project, create key, send a mock call, see it in the explorer.

<!-- END FILE -->

<!-- FILE: docs/05-tickets.md -->
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

<!-- END FILE -->

<!-- FILE: docs/06-deployment.md -->
# 06 - Deployment

Reads: `02-architecture.md`, `03-security.md`.

## 1. Environments

| Environment | How | Notes |
|---|---|---|
| Local dev | `make dev` (compose dev override: hot reload, ports exposed on localhost) | Demo mode on by default; mock provider needs no keys |
| CI | GitHub Actions with Postgres and Redis service containers | Runs lint, types, tests, audits, image build |
| Production (self-hosted) | `docker compose up -d` on any Linux VM or home server | Caddy handles HTTPS. Suggested size: 1 vCPU, 1 GB RAM minimum, 2 GB comfortable. |

## 2. Environment variables (`.env.example` must list all, with no real values)

| Variable | Purpose | Notes |
|---|---|---|
| `ENV` | `development` or `production` | Docs and debug features only in development |
| `PUBLIC_URL` | Public base URL, used for CSRF origin check and cookie settings | Must be `https://...` in production |
| `GATEWAY_MASTER_KEY` | Encrypts provider keys | 32 random bytes, base64. Generate with `openssl rand -base64 32`. Back up separately from the database. |
| `DATABASE_URL` | Postgres connection (async driver) | |
| `POSTGRES_PASSWORD` | For the Postgres container | Strong random value |
| `REDIS_URL` | Redis connection | Includes password |
| `REDIS_PASSWORD` | For the Redis container | |
| `LOG_LEVEL` | `info` default | |
| `MAX_REQUEST_BYTES` | Gateway body cap | default 4 MB |
| `DEFAULT_RETENTION_DAYS` | default 30 | |
| `ALLOW_PRIVATE_PROVIDER_URLS` | default `false` | Set `true` only for local models |
| `DEMO_MODE` | `true` loads demo data on first start | Off in production |
| `DOMAIN` | Used by Caddy for automatic certificates | |

## 3. Deploy steps (first time)

1. Install Docker and Docker Compose on the server. Point the domain's DNS to the server.
2. Clone the repository. Copy `.env.example` to `.env` and fill every value (generate secrets, never reuse examples).
3. Run `docker compose pull` (or `docker compose build`) then `docker compose up -d`.
4. The backend runs `alembic upgrade head` on start (guarded by a lock so two replicas cannot migrate at once).
5. Open `https://<domain>/setup`, create the owner account.
6. Add a provider key in Settings, create a project, copy its key, and send a test call (the Quick start tab shows the command).

## 4. Updating

1. `git pull`, then `docker compose build`, then `docker compose up -d`.
2. Migrations run automatically. Read the release notes first. Take a backup before major version updates.
3. Check `/readyz` and the dashboard Overview.

## 5. Migrations

- Alembic only. Every schema change ships as a migration with both upgrade and downgrade, tested in CI on a clean database and on a database with demo data.
- Destructive changes use two releases: add the new thing and stop using the old one first, remove the old one in the next release.

## 6. Backup and restore

- Backup: a documented cron line using `pg_dump` into a compressed file, kept off the server, with a retention rule (for example daily for 7 days).
- Redis holds only cache and counters. It does not need backup. After a Redis loss, budget counters are rebuilt by the reconcile job within 10 minutes.
- Restore test: restore into a fresh Postgres and start the stack with the same master key. Document the exact commands and run them once during T21.
- The master key must be stored separately (password manager). Without it, stored provider keys cannot be decrypted and must be re-entered.

## 7. Rollback

1. Keep the previous image tag. Roll back by setting the previous tag and running `docker compose up -d`.
2. If the release included a migration, run the documented `alembic downgrade` step first only if the release notes say the downgrade is safe; otherwise restore the backup taken before the update.
3. Because destructive migrations are split across two releases, a one-version rollback is normally safe.

## 8. Monitoring

- `GET /healthz` (alive), `GET /readyz` (DB and Redis reachable). Compose healthchecks use them.
- `/metrics` for Prometheus (internal network only). Key signals: gateway error rate, p95 latency, provider error counts by provider, log queue depth (alert if it keeps growing), cache hit ratio, budget blocks, scheduler job failures.
- Structured JSON logs to stdout. Docs show how to ship them to any log tool.
- The dashboard itself is the product's monitoring for AI calls. Document an optional external uptime check against `/readyz`.
- Optional: a `docker-compose.monitoring.yml` with Prometheus and Grafana and a ready-made Grafana dashboard JSON (nice portfolio extra, not required for V1).

## 9. Release process

- Semantic versioning. Tag `vX.Y.Z`; GitHub Actions builds and publishes images to GitHub Container Registry and creates a release with notes from the changelog.
- Every release: CI green, `pip-audit` and `npm audit` clean at high severity, Trivy scan clean at high severity, benchmark file updated if the hot path changed.

<!-- END FILE -->
