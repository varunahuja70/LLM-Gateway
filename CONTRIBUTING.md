# Contributing to LLM Gateway

Thank you for your interest in contributing to LLM Gateway! This document explains our development workflow, standards, and how to submit changes.

---

## 1. Code of Conduct

All contributors and participants agree to abide by the [Code of Conduct](CODE_OF_CONDUCT.md). Please report any unacceptable behavior according to our reporting procedures.

---

## 2. Core Architectural Rules

1. **Specifications are Source of Truth**:
   The specifications under `docs/` define the design, security invariants, and interfaces. If code and docs disagree, discuss in an issue first. Do not silently change data models or core architectures.
2. **Security Invariants**:
   - Never log secrets, passwords, or keys. Redaction filters must always be preserved.
   - Never store money as floats or approximate values; store integer micro-USD (`$1.00 = 1,000,000`).
   - Unknown prices must remain `NULL` (never substitute zero).
   - SSRF protection must remain active on all user-supplied URLs.
3. **Strict Type Safety**:
   - Backend: Python 3.13+, strictly typed, validated via `mypy --strict`.
   - Frontend: TypeScript strict mode, zero `any` allowed.

---

## 3. Development Setup

### Prerequisites
- Python 3.13+ and `uv`
- Node.js 24+ and `pnpm`
- Docker and Docker Compose

### Step-by-Step Setup
```bash
# 1. Clone repository
git clone https://github.com/varunahuja70/LLM-Gateway.git
cd LLM-Gateway

# 2. Start database and cache services
docker compose -f docker-compose.dev.yml up -d

# 3. Setup backend
cd backend
uv sync
uv run alembic upgrade head
uv run python scripts/seed_prices.py
cd ..

# 4. Setup frontend
cd frontend
pnpm install
cd ..

# 5. Start development servers
make dev
```

---

## 4. Testing & Verification

Every pull request must pass all backend and frontend linters and test suites before being merged:

```bash
# Run all tests
make test

# Run all linters and type-checkers
make lint
```

Specifically:
- Backend:
  ```bash
  cd backend
  uv run ruff check app tests
  uv run mypy app
  uv run pytest tests
  ```
- Frontend:
  ```bash
  cd frontend
  pnpm run type-check
  pnpm run lint
  pnpm run test:run
  ```

---

## 5. Commit & Pull Request Workflow

1. Create a feature branch: `git checkout -b feature/my-new-feature`
2. Write tests covering your changes.
3. Follow conventional commit messages: `ticket NN: <title>` or `feat: <summary>` / `fix: <summary>`.
4. Ensure `make lint` and `make test` pass locally.
5. Push to your fork and submit a Pull Request using the provided PR template.
