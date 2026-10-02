import math
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.provider import ModelPrice


@dataclass
class PriceInfo:
    input_micro_usd_per_mtok: int
    output_micro_usd_per_mtok: int
    cached_input_micro_usd_per_mtok: int | None = None


def calculate_cost(
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cached_input_tokens: int = 0,
    price: PriceInfo | ModelPrice | None = None,
) -> int | None:
    """Calculate the cost of an LLM request in integer micro-USD.

    Rules:
    - If price is not known/found, returns None (never 0).
    - Money is stored as integer micro-USD ($1 = 1,000,000 micro-USD).
    - Ceiling rounding is applied to avoid under-billing fractions of micro-USD.
    - Cached input tokens use cached_input_micro_usd_per_mtok if available,
      falling back to the standard input price.
    """
    if not provider or not model or price is None:
        # Unknown model price MUST return None, never 0
        return None

    input_price = price.input_micro_usd_per_mtok
    output_price = price.output_micro_usd_per_mtok
    cached_price = (
        price.cached_input_micro_usd_per_mtok
        if price.cached_input_micro_usd_per_mtok is not None
        else input_price
    )

    cached_tokens = max(0, min(cached_input_tokens, input_tokens))
    regular_input_tokens = max(0, input_tokens - cached_tokens)
    out_tokens = max(0, output_tokens)

    # Calculate costs per token class with ceiling rounding (math.ceil)
    cost_regular_input = (
        math.ceil((regular_input_tokens * input_price) / 1_000_000)
        if regular_input_tokens > 0
        else 0
    )
    cost_cached_input = (
        math.ceil((cached_tokens * cached_price) / 1_000_000) if cached_tokens > 0 else 0
    )
    cost_output = math.ceil((out_tokens * output_price) / 1_000_000) if out_tokens > 0 else 0

    return int(cost_regular_input + cost_cached_input + cost_output)


async def get_price_for_model(db: AsyncSession, provider: str, model: str) -> ModelPrice | None:
    """Look up price row for provider and model."""
    stmt = select(ModelPrice).where(ModelPrice.provider == provider, ModelPrice.model == model)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()
