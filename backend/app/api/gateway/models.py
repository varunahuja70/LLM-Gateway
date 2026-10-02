from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.project import GatewayKey, Project
from app.db.models.provider import ModelPrice, ProviderCredential
from app.db.session import get_db_session
from app.deps import require_gateway_key
from app.schemas.chat import ModelListResponse, ModelObject

router = APIRouter(prefix="/v1", tags=["gateway-models"])


@router.get("/models", response_model=ModelListResponse)
async def list_models(
    _auth_data: tuple[Project, GatewayKey] = Depends(require_gateway_key),
    db: AsyncSession = Depends(get_db_session),
) -> ModelListResponse:
    """List models available to the authenticated project."""
    # 1. Fetch active providers
    cred_stmt = select(ProviderCredential.provider).where(ProviderCredential.disabled_at.is_(None))
    res_creds = await db.execute(cred_stmt)
    active_providers = set(res_creds.scalars().all())
    active_providers.add("mock")  # Mock provider is always available

    # 2. Fetch configured models from model_price table
    price_stmt = select(ModelPrice).order_by(ModelPrice.provider, ModelPrice.model)
    res_prices = await db.execute(price_stmt)
    prices = res_prices.scalars().all()

    models: list[ModelObject] = []
    seen: set[str] = set()

    for p in prices:
        # Include if provider is active or mock
        if p.provider in active_providers or p.provider == "mock":
            full_id = f"{p.provider}/{p.model}"
            if full_id not in seen:
                seen.add(full_id)
                models.append(
                    ModelObject(
                        id=full_id,
                        object="model",
                        created=1700000000,
                        owned_by=p.provider,
                    )
                )

    # Always ensure mock model is available
    if "mock/mock-model" not in seen:
        models.insert(
            0,
            ModelObject(
                id="mock/mock-model",
                object="model",
                created=1700000000,
                owned_by="mock",
            ),
        )

    return ModelListResponse(object="list", data=models)
