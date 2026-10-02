# Build Progress

| Ticket | Title | Status | Result / Notes |
|---|---|---|---|
| T01 | Project setup | Complete | Backend with uv (FastAPI, SQLAlchemy 2.0, asyncpg, Redis, structlog), strict ruff/mypy/pytest. Frontend with Next.js 16, Tailwind v4, shadcn/ui skeleton, Vitest. Root Makefile, CI workflow, .env.example, versions.lock.md. |
| T02 | Docker Compose and config | Complete | docker-compose.yml (caddy, backend, frontend, postgres, redis), dev override, Dockerfiles, Caddyfile routing and security headers, pydantic-settings config with master key validation, /healthz and /readyz endpoints. |
| T03 | Database models and migrations | Complete | SQLAlchemy 2.0 async models for all 12 tables, RFC 9562 UUIDv7 generator, Alembic async migrations setup with 0001_initial_schema, unit tests for models/constraints and migration upgrade/downgrade. |
