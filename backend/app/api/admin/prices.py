import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import utc_now
from app.db.models.owner import OwnerUser, Session
from app.db.models.provider import ModelPrice
from app.db.session import get_db_session
from app.deps import require_csrf, require_owner
from app.schemas.auth import MessageResponse
from app.schemas.price import (
    ModelPriceCreate,
    ModelPriceImportRequest,
    ModelPriceResponse,
    ModelPriceUpdate,
)
from app.services.audit import log_audit_event

router = APIRouter(prefix="/admin/prices", tags=["prices"])


@router.get("", response_model=list[ModelPriceResponse])
async def list_prices(
    db: AsyncSession = Depends(get_db_session),
    _owner_auth: tuple[OwnerUser, Session] = Depends(require_owner),
) -> Any:
    """List all model prices ordered by provider and model."""
    stmt = select(ModelPrice).order_by(ModelPrice.provider.asc(), ModelPrice.model.asc())
    result = await db.execute(stmt)
    records = result.scalars().all()
    return [ModelPriceResponse.model_validate(r) for r in records]


@router.post("", response_model=ModelPriceResponse, dependencies=[Depends(require_csrf)])
async def create_price(
    req: ModelPriceCreate,
    db: AsyncSession = Depends(get_db_session),
    owner_auth: tuple[OwnerUser, Session] = Depends(require_owner),
) -> Any:
    """Create a new model price row."""
    owner, _ = owner_auth
    provider = req.provider.lower().strip()
    model = req.model.strip()

    stmt = select(ModelPrice).where(ModelPrice.provider == provider, ModelPrice.model == model)
    result = await db.execute(stmt)
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Price row for provider '{provider}' and model '{model}' already exists.",
        )

    record = ModelPrice(
        provider=provider,
        model=model,
        input_micro_usd_per_mtok=req.input_micro_usd_per_mtok,
        output_micro_usd_per_mtok=req.output_micro_usd_per_mtok,
        cached_input_micro_usd_per_mtok=req.cached_input_micro_usd_per_mtok,
        source_url=req.source_url.strip(),
        verified_on=req.verified_on,
        is_seed=False,
    )
    db.add(record)
    await db.flush()

    await log_audit_event(
        db,
        action="price_created",
        actor_type="owner",
        actor_id=owner.id,
        details={"price_id": str(record.id), "provider": provider, "model": model},
    )

    return ModelPriceResponse.model_validate(record)


@router.patch(
    "/{price_id}",
    response_model=ModelPriceResponse,
    dependencies=[Depends(require_csrf)],
)
async def update_price(
    price_id: uuid.UUID,
    req: ModelPriceUpdate,
    db: AsyncSession = Depends(get_db_session),
    owner_auth: tuple[OwnerUser, Session] = Depends(require_owner),
) -> Any:
    """Update a model price row."""
    owner, _ = owner_auth
    stmt = select(ModelPrice).where(ModelPrice.id == price_id)
    result = await db.execute(stmt)
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Price row not found.")

    if req.input_micro_usd_per_mtok is not None:
        record.input_micro_usd_per_mtok = req.input_micro_usd_per_mtok
        record.is_seed = False

    if req.output_micro_usd_per_mtok is not None:
        record.output_micro_usd_per_mtok = req.output_micro_usd_per_mtok
        record.is_seed = False

    if "cached_input_micro_usd_per_mtok" in req.model_fields_set:
        record.cached_input_micro_usd_per_mtok = req.cached_input_micro_usd_per_mtok
        record.is_seed = False

    if req.source_url is not None:
        record.source_url = req.source_url.strip()

    if req.verified_on is not None:
        record.verified_on = req.verified_on

    record.updated_at = utc_now()

    await log_audit_event(
        db,
        action="price_updated",
        actor_type="owner",
        actor_id=owner.id,
        details={"price_id": str(record.id), "provider": record.provider, "model": record.model},
    )

    return ModelPriceResponse.model_validate(record)


@router.delete("/{price_id}", response_model=MessageResponse, dependencies=[Depends(require_csrf)])
async def delete_price(
    price_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    owner_auth: tuple[OwnerUser, Session] = Depends(require_owner),
) -> Any:
    """Delete a model price row."""
    owner, _ = owner_auth
    stmt = select(ModelPrice).where(ModelPrice.id == price_id)
    result = await db.execute(stmt)
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Price row not found.")

    await db.delete(record)
    await log_audit_event(
        db,
        action="price_deleted",
        actor_type="owner",
        actor_id=owner.id,
        details={"price_id": str(price_id), "provider": record.provider, "model": record.model},
    )
    return MessageResponse(message="Model price deleted successfully.")


@router.post("/import", response_model=MessageResponse, dependencies=[Depends(require_csrf)])
async def import_prices(
    req: ModelPriceImportRequest,
    db: AsyncSession = Depends(get_db_session),
    owner_auth: tuple[OwnerUser, Session] = Depends(require_owner),
) -> Any:
    """Import and upsert a batch of model prices from JSON."""
    owner, _ = owner_auth
    count = 0

    for item in req.prices:
        provider = item.provider.lower().strip()
        model = item.model.strip()

        stmt = select(ModelPrice).where(ModelPrice.provider == provider, ModelPrice.model == model)
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            existing.input_micro_usd_per_mtok = item.input_micro_usd_per_mtok
            existing.output_micro_usd_per_mtok = item.output_micro_usd_per_mtok
            existing.cached_input_micro_usd_per_mtok = item.cached_input_micro_usd_per_mtok
            existing.source_url = item.source_url.strip()
            existing.verified_on = item.verified_on
            existing.is_seed = False
            existing.updated_at = utc_now()
        else:
            new_price = ModelPrice(
                provider=provider,
                model=model,
                input_micro_usd_per_mtok=item.input_micro_usd_per_mtok,
                output_micro_usd_per_mtok=item.output_micro_usd_per_mtok,
                cached_input_micro_usd_per_mtok=item.cached_input_micro_usd_per_mtok,
                source_url=item.source_url.strip(),
                verified_on=item.verified_on,
                is_seed=False,
            )
            db.add(new_price)
        count += 1

    await log_audit_event(
        db,
        action="prices_imported",
        actor_type="owner",
        actor_id=owner.id,
        details={"imported_count": count},
    )

    return MessageResponse(message=f"Successfully imported {count} model prices.")
