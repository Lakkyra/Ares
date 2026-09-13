"""LLM model pricing table and cost calculation utilities."""

# Pricing rates per 1,000,000 tokens (USD)
MODEL_PRICING: dict[str, tuple[float, float]] = {
    # model_name: (prompt_cost_per_million, completion_cost_per_million)
    "claude-3-5-sonnet-20241022": (3.00, 15.00),
    "claude-3-5-sonnet-latest": (3.00, 15.00),
    "claude-3-5-haiku-20241022": (1.00, 5.00),
    "claude-3-opus-20240229": (15.00, 75.00),
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "o1-preview": (15.00, 60.00),
    "o1-mini": (3.00, 12.00),
}

DEFAULT_PRICING = (2.50, 10.00)  # Standard fallback estimate


def calculate_token_cost(
    model_name: str,
    prompt_tokens: int,
    completion_tokens: int,
) -> float:
    """Calculate estimated cost in USD for a given token usage.

    Args:
        model_name: Name of the LLM model used.
        prompt_tokens: Number of input/prompt tokens.
        completion_tokens: Number of output/completion tokens.

    Returns:
        Estimated cost in USD rounded to 6 decimal places.
    """
    model_key = model_name.lower()
    prompt_rate, completion_rate = DEFAULT_PRICING

    for key, rates in MODEL_PRICING.items():
        if key in model_key or model_key in key:
            prompt_rate, completion_rate = rates
            break

    prompt_cost = (prompt_tokens / 1_000_000.0) * prompt_rate
    completion_cost = (completion_tokens / 1_000_000.0) * completion_rate
    total_cost = prompt_cost + completion_cost
    return round(total_cost, 6)
