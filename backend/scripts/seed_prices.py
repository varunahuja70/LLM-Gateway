import asyncio
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.provider import ModelPrice
from app.db.session import get_engine, get_sessionmaker

SEED_FILE_PATH = Path(__file__).resolve().parent.parent / "data" / "prices.seed.json"


async def seed_prices(session: AsyncSession) -> int:
    """Load prices from prices.seed.json into model_price table.

    Returns the number of prices inserted or updated.
    """
    if not SEED_FILE_PATH.exists():
        raise FileNotFoundError(f"Seed file not found at {SEED_FILE_PATH}")

    with open(SEED_FILE_PATH, encoding="utf-8") as f:
        data: list[dict[str, Any]] = json.load(f)

    count = 0
    for item in data:
        provider = str(item["provider"]).lower().strip()
        model = str(item["model"]).strip()
        stmt = select(ModelPrice).where(ModelPrice.provider == provider, ModelPrice.model == model)
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()

        verified_on_val: date
        if isinstance(item["verified_on"], str):
            verified_on_val = datetime.strptime(item["verified_on"], "%Y-%m-%d").date()
        else:
            verified_on_val = item["verified_on"]

        if existing:
            # If it's a seed row, update it with seed file values
            if existing.is_seed:
                existing.input_micro_usd_per_mtok = int(item["input_micro_usd_per_mtok"])
                existing.output_micro_usd_per_mtok = int(item["output_micro_usd_per_mtok"])
                existing.cached_input_micro_usd_per_mtok = (
                    int(item["cached_input_micro_usd_per_mtok"])
                    if item.get("cached_input_micro_usd_per_mtok") is not None
                    else None
                )
                existing.source_url = str(item["source_url"])
                existing.verified_on = verified_on_val
                count += 1
        else:
            new_row = ModelPrice(
                provider=provider,
                model=model,
                input_micro_usd_per_mtok=int(item["input_micro_usd_per_mtok"]),
                output_micro_usd_per_mtok=int(item["output_micro_usd_per_mtok"]),
                cached_input_micro_usd_per_mtok=(
                    int(item["cached_input_micro_usd_per_mtok"])
                    if item.get("cached_input_micro_usd_per_mtok") is not None
                    else None
                ),
                source_url=str(item["source_url"]),
                verified_on=verified_on_val,
                is_seed=True,
            )
            session.add(new_row)
            count += 1

    await session.commit()
    return count


async def main() -> None:
    session_factory = get_sessionmaker()
    async with session_factory() as session:
        n = await seed_prices(session)
        print(f"Seeded {n} model prices successfully.")
    await get_engine().dispose()


if __name__ == "__main__":
    asyncio.run(main())
