import redis.asyncio as aioredis
from fastapi import APIRouter, Response, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz")
async def readyz(response: Response) -> dict[str, str]:
    settings = get_settings()
    checks: dict[str, str] = {}
    is_ready = True

    # Check DB
    try:
        engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        await engine.dispose()
        checks["db"] = "ok"
    except Exception as e:
        checks["db"] = f"error: {e}"
        is_ready = False

    # Check Redis
    try:
        r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        pong = await r.ping()
        await r.close()
        if pong:
            checks["redis"] = "ok"
        else:
            checks["redis"] = "failed ping"
            is_ready = False
    except Exception as e:
        checks["redis"] = f"error: {e}"
        is_ready = False

    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        checks["status"] = "degraded"
    else:
        checks["status"] = "ok"

    return checks


@router.get("/metrics")
async def metrics() -> Response:
    """Internal Prometheus metrics endpoint."""
    from app.core.metrics import get_metrics_output

    content, media_type = get_metrics_output()
    return Response(content=content, media_type=media_type)
