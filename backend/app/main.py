from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.admin.auth import router as auth_router
from app.api.admin.health import router as health_router
from app.config import get_settings


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
    # Enforce configuration validation at startup
    settings = get_settings()
    # Explicit check for master key
    if not settings.GATEWAY_MASTER_KEY:
        raise RuntimeError("Startup aborted: GATEWAY_MASTER_KEY is required.")
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    is_dev = settings.ENV == "development"

    app = FastAPI(
        title="LLM Gateway",
        description="Self-hosted LLM Gateway, Cost & Quality Tracker",
        version="0.1.0",
        docs_url="/admin/docs" if is_dev else None,
        redoc_url="/admin/redoc" if is_dev else None,
        openapi_url="/admin/openapi.json" if is_dev else None,
        lifespan=lifespan,
    )

    # Health and readiness routes
    app.include_router(health_router)
    app.include_router(auth_router)

    return app


app = create_app()
