from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.admin.alerts import router as alerts_router
from app.api.admin.auth import router as auth_router
from app.api.admin.health import router as health_router
from app.api.admin.keys import router as keys_router
from app.api.admin.prices import router as prices_router
from app.api.admin.projects import router as projects_router
from app.api.admin.providers import router as providers_router
from app.api.gateway.chat import router as chat_router
from app.api.gateway.models import router as models_router
from app.config import get_settings
from app.core.errors import GatewayAPIException
from app.services.request_logger import request_logger
from app.workers.scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
    # Enforce configuration validation at startup
    settings = get_settings()
    # Explicit check for master key
    if not settings.GATEWAY_MASTER_KEY:
        raise RuntimeError("Startup aborted: GATEWAY_MASTER_KEY is required.")

    # Start background request logger worker
    request_logger.start()

    # Start background scheduler if not in test mode
    if settings.ENV != "test":
        start_scheduler()

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

    try:
        yield
    finally:
        if settings.ENV != "test":
            stop_scheduler()
        await request_logger.stop()


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

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        if request.url.path.startswith("/v1"):
            err_msg = "; ".join(
                f"{'.'.join(str(loc) for loc in err['loc'])}: {err['msg']}" for err in exc.errors()
            )
            return JSONResponse(
                status_code=400,
                content={
                    "error": {
                        "message": err_msg,
                        "type": "invalid_request_error",
                        "code": "invalid_parameter",
                    }
                },
            )
        return JSONResponse(status_code=422, content={"detail": exc.errors()})

    # Health and readiness routes
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(projects_router)
    app.include_router(keys_router)
    app.include_router(providers_router)
    app.include_router(prices_router)
    app.include_router(alerts_router)

    # Gateway API routes
    app.include_router(chat_router)
    app.include_router(models_router)

    return app


app = create_app()
