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
