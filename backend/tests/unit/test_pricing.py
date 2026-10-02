from app.core.pricing import PriceInfo, calculate_cost


def test_unknown_model_returns_none() -> None:
    """CRITICAL SPEC REQUIREMENT: Unknown model price means cost is NULL, never 0."""
    result = calculate_cost(
        provider="unknown_provider",
        model="nonexistent-model-xyz",
        input_tokens=1000,
        output_tokens=500,
        price=None,
    )
    assert result is None


def test_standard_cost_calculation_integer_micro_usd() -> None:
    """Test exact calculation in integer micro-USD for gpt-5-mini."""
    # gpt-5-mini: $0.25/Mtok in, $2.00/Mtok out
    # 250,000 micro-USD per Mtok in, 2,000,000 micro-USD per Mtok out
    price = PriceInfo(
        input_micro_usd_per_mtok=250_000,
        output_micro_usd_per_mtok=2_000_000,
        cached_input_micro_usd_per_mtok=25_000,
    )

    # 1,000 input tokens = 1000 * 250,000 / 1,000,000 = 250 micro-USD
    # 500 output tokens = 500 * 2,000,000 / 1,000,000 = 1000 micro-USD
    # Total = 1250 micro-USD ($0.00125)
    cost = calculate_cost(
        provider="openai",
        model="gpt-5-mini",
        input_tokens=1000,
        output_tokens=500,
        cached_input_tokens=0,
        price=price,
    )
    assert cost == 1250


def test_cached_input_tokens_use_discounted_rate() -> None:
    """Test that cached input tokens use cached_input_micro_usd_per_mtok."""
    price = PriceInfo(
        input_micro_usd_per_mtok=1_000_000,  # $1.00 / Mtok
        output_micro_usd_per_mtok=5_000_000,  # $5.00 / Mtok
        cached_input_micro_usd_per_mtok=100_000,  # $0.10 / Mtok (10x discount)
    )

    # 10,000 input tokens total, 8,000 cached, 2,000 regular
    # Regular input: 2000 * 1,000,000 / 1,000,000 = 2000 micro-USD
    # Cached input: 8000 * 100,000 / 1,000,000 = 800 micro-USD
    # Output: 1000 * 5,000,000 / 1,000,000 = 5000 micro-USD
    # Total = 2000 + 800 + 5000 = 7800 micro-USD
    cost = calculate_cost(
        provider="anthropic",
        model="claude-haiku-4-5",
        input_tokens=10000,
        output_tokens=1000,
        cached_input_tokens=8000,
        price=price,
    )
    assert cost == 7800


def test_ceiling_rounding_prevents_underbilling() -> None:
    """Fractional micro-USD costs round up using math.ceil."""
    # gpt-5: $1.25 / Mtok = 1,250,000 micro-USD per Mtok
    price = PriceInfo(
        input_micro_usd_per_mtok=1_250_000,
        output_micro_usd_per_mtok=10_000_000,
    )

    # 1 input token = 1 * 1,250,000 / 1,000,000 = 1.25 micro-USD -> rounds to 2
    cost = calculate_cost(
        provider="openai",
        model="gpt-5",
        input_tokens=1,
        output_tokens=0,
        cached_input_tokens=0,
        price=price,
    )
    assert cost == 2


def test_zero_tokens_priced_model_returns_zero() -> None:
    """0 tokens on a priced model returns 0 micro-USD, not None."""
    price = PriceInfo(
        input_micro_usd_per_mtok=1_000_000,
        output_micro_usd_per_mtok=2_000_000,
    )
    cost = calculate_cost(
        provider="mock",
        model="mock-model",
        input_tokens=0,
        output_tokens=0,
        price=price,
    )
    assert cost == 0
