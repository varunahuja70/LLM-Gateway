from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.admin.auth import router as auth_router
from app.api.admin.health import router as health_router
from app.api.admin.keys import router as keys_router
from app.api.admin.prices import router as prices_router
from app.api.admin.projects import router as projects_router
from app.api.admin.providers import router as providers_router
from app.config import get_settings
from app.core.errors import GatewayAPIException


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
    # Enforce configuration validation at startup
    settings = get_settings()
    # Explicit check for master key
    if not settings.GATEWAY_MASTER_KEY:
        raise RuntimeError("Startup aborted: GATEWAY_MASTER_KEY is required.")

    # Auto-seed default model prices on first startup if table is empty
    try:
        from sqlalchemy import select

        from app.db.models.provider import ModelPrice
        from app.db.session import get_sessionmaker
        from scripts.seed_prices import seed_prices

        session_factory = get_sessionmaker()
        async with session_factory() as session:
            res = await session.execute(select(ModelPrice).limit(1))
            if res.scalar_one_or_none() is None:
                await seed_prices(session)
    except Exception:
        pass

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

    @app.exception_handler(GatewayAPIException)
    async def gateway_api_exception_handler(
        _request: Request, exc: GatewayAPIException
    ) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=exc.detail, headers=exc.headers)

    # Health and readiness routes
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(projects_router)
    app.include_router(keys_router)
    app.include_router(providers_router)
    app.include_router(prices_router)

    return app


app = create_app()
