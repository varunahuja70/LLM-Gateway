.PHONY: help dev test test-backend test-frontend lint lint-backend lint-frontend migrate seed clean

help:
	@echo "Available commands:"
	@echo "  make dev          - Start full stack in development mode"
	@echo "  make test         - Run backend and frontend tests"
	@echo "  make test-backend - Run backend pytest"
	@echo "  make test-frontend- Run frontend vitest"
	@echo "  make lint         - Run ruff, mypy, eslint, and tsc"
	@echo "  make lint-backend - Run ruff and mypy"
	@echo "  make lint-frontend- Run eslint and tsc"
	@echo "  make migrate      - Run Alembic database migrations"
	@echo "  make seed         - Load demo data"
	@echo "  make clean        - Clean cache and temporary files"

dev:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up

test: test-backend test-frontend

test-backend:
	cd backend && uv run pytest

test-frontend:
	cd frontend && pnpm run test:run

lint: lint-backend lint-frontend

lint-backend:
	cd backend && uv run ruff check .
	cd backend && uv run ruff format --check .
	cd backend && uv run mypy app tests

lint-frontend:
	cd frontend && pnpm run lint
	cd frontend && pnpm exec tsc --noEmit

migrate:
	cd backend && uv run alembic upgrade head

seed:
	cd backend && uv run python -m scripts.seed_demo

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
