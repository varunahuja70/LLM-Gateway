# Versions Lock

All versions were pinned during setup by querying the package managers for current stable releases, following `docs/02-architecture.md` Section 2.

Last updated: 2026-10-03

## Backend (Python)

Tooling: `uv` package manager. Installed and verified with Python 3.13 / 3.14.

| Package | Version | Command / Source | Notes |
|---|---|---|---|
| fastapi | 0.142.2 | `uv add fastapi` | Web framework, OpenAPI support |
| uvicorn | 0.54.0 | `uv add "uvicorn[standard]"` | ASGI server |
| pydantic | 2.13.5 | `uv add pydantic` | Data validation |
| email-validator | 2.3.0 | `uv add "pydantic[email]"` | Email validation for Pydantic models |
| pydantic-settings | 2.15.0 | `uv add pydantic-settings` | Typed configuration |
| sqlalchemy | 2.0.54 | `uv add "sqlalchemy>=2.0.0,<2.1.0"` | Async ORM (pinned to 2.0.x; not 2.1 beta) |
| asyncpg | 0.31.0 | `uv add asyncpg` | PostgreSQL async driver |
| alembic | 1.20.0 | `uv add alembic` | Database migrations |
| redis | 8.1.0 | `uv add redis` | Async Redis client |
| httpx | 0.28.1 | `uv add "httpx[http2]"` | Async HTTP client for provider calls |
| argon2-cffi | 25.1.0 | `uv add argon2-cffi` | Password hashing (Argon2id) |
| cryptography | 50.0.2 | `uv add cryptography` | AES-256-GCM encryption |
| structlog | 26.1.0 | `uv add structlog` | Structured JSON logging |
| prometheus-client | 0.26.0 | `uv add prometheus-client` | Prometheus metrics exporter |
| apscheduler | 3.11.3 | `uv add "apscheduler<4.0.0"` | In-process background scheduler |
| tiktoken | 0.14.0 | `uv add tiktoken` | Token estimation fallback |
| ruff | 0.16.10 | `uv add --dev ruff` | Linter and code formatter |
| mypy | 2.4.0 | `uv add --dev mypy` | Strict type checking |
| pytest | 9.1.1 | `uv add --dev pytest` | Test runner |
| pytest-asyncio | 1.4.0 | `uv add --dev pytest-asyncio` | Async testing plugin |
| respx | 0.23.1 | `uv add --dev respx` | Mocking httpx provider calls |
| coverage | 7.16.2 | `uv add --dev coverage` | Test coverage reporting |
| aiosqlite | 0.22.1 | `uv add --dev aiosqlite` | Async SQLite driver for isolated local/unit testing |
| openai | 3.24.0 | `uv add --dev openai` | Official OpenAI Python SDK compatibility tests |
| pip-audit | 2.10.1 | `uv add --dev pip-audit` | Dependency vulnerability auditing |

## Frontend (Node / TypeScript)

Tooling: Node v24.7.0 LTS, `pnpm` 10.17.1.

| Package | Version | Command / Source | Notes |
|---|---|---|---|
| next | 16.3.8 | `pnpm create next-app` | React framework, App Router |
| react | 19.2.8 | `pnpm create next-app` | React 19 line |
| react-dom | 19.2.8 | `pnpm create next-app` | React DOM |
| typescript | 5.9.3 | `pnpm create next-app` | Strict TypeScript |
| tailwindcss | 4.3.3 | `pnpm create next-app` | CSS styling |
| @tailwindcss/postcss | 4.3.3 | `pnpm create next-app` | Tailwind v4 PostCSS plugin |
| @tanstack/react-query | 5.104.1 | `pnpm add @tanstack/react-query` | Server state management |
| recharts | 3.10.1 | `pnpm add recharts` | Dashboard charts |
| lucide-react | 1.50.0 | `pnpm add lucide-react` | Icons |
| clsx | 2.1.1 | `pnpm add clsx` | Class name utility |
| tailwind-merge | 3.7.0 | `pnpm add tailwind-merge` | Class conflict resolution |
| class-variance-authority | 0.7.1 | `pnpm add class-variance-authority` | Component variant styling |
| vitest | 5.0.3 | `pnpm add -D vitest` | Unit and component testing |
| @vitejs/plugin-react | 6.1.1 | `pnpm add -D @vitejs/plugin-react` | Vite React plugin for Vitest |
| @testing-library/react | 16.3.3 | `pnpm add -D @testing-library/react` | React component testing |
| @testing-library/jest-dom | 7.0.1 | `pnpm add -D @testing-library/jest-dom` | DOM matchers |
| jsdom | 30.1.1 | `pnpm add -D jsdom` | Test DOM environment |
| prettier | 3.9.9 | `pnpm add -D prettier` | Code formatter |
| prettier-plugin-tailwindcss | 0.8.1 | `pnpm add -D prettier-plugin-tailwindcss` | Tailwind class sorting |
| eslint | 9.39.5 | `pnpm create next-app` | Linter |
| eslint-config-next | 16.3.8 | `pnpm create next-app` | Next.js lint configuration |
| @playwright/test | 1.63.0 | `pnpm add -D @playwright/test` | End-to-end browser and smoke testing |

## Infrastructure

| Service | Version / Tag | Docker image | Notes |
|---|---|---|---|
| PostgreSQL | 18.x | `postgres:18-alpine` | Primary transactional database |
| Redis | 8.x | `redis:8-alpine` | Cache, counters, rate limits |
| Caddy | 2.x | `caddy:2-alpine` | Reverse proxy and automatic TLS |
