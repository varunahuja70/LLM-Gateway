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
