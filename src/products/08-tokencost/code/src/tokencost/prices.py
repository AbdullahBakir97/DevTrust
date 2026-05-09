"""Per-model price table and cost calculator.

Prices are recorded in **micro-USD per million tokens** -- the common
unit vendors quote. We store input and output prices separately because
output tokens are typically 3-5x more expensive.

This table is intentionally small. v0.0.1 covers the models DevTrust's
own products use. Operators with other models pass `add_model()` at
runtime; v0.0.2 will let them ship a YAML override.

Prices recorded May 2026. We don't auto-update -- the canonical record
is the operator's own JSONL log, where each row's `cost_micros` was
denormalized at call time and won't drift even if vendors change rates.
"""

from __future__ import annotations

from dataclasses import dataclass

# 1 USD = 1,000,000 micro-USD. Mirrors models.MICROS_PER_USD.
_MICROS_PER_USD = 1_000_000


@dataclass(frozen=True)
class ModelPrice:
    """Per-million-tokens price for one model."""

    provider: str
    model: str
    input_micros_per_mtok: int
    output_micros_per_mtok: int

    def cost_micros(self, input_tokens: int, output_tokens: int) -> int:
        """Compute the cost of one call in micro-USD."""
        # Integer arithmetic throughout so we never truncate fractional cents.
        # cost_micros = (input_tokens * input_micros_per_mtok) // 1_000_000 +
        #               (output_tokens * output_micros_per_mtok) // 1_000_000
        return (input_tokens * self.input_micros_per_mtok) // 1_000_000 + (
            output_tokens * self.output_micros_per_mtok
        ) // 1_000_000


# Curated v0.0.1 set. Add models with `add_model()` at runtime if needed.
_PRICES: dict[tuple[str, str], ModelPrice] = {
    # Anthropic Claude (May 2026 rates from anthropic.com/pricing)
    ("anthropic", "claude-opus-4-6"): ModelPrice(
        provider="anthropic",
        model="claude-opus-4-6",
        input_micros_per_mtok=15 * _MICROS_PER_USD,
        output_micros_per_mtok=75 * _MICROS_PER_USD,
    ),
    ("anthropic", "claude-sonnet-4-6"): ModelPrice(
        provider="anthropic",
        model="claude-sonnet-4-6",
        input_micros_per_mtok=3 * _MICROS_PER_USD,
        output_micros_per_mtok=15 * _MICROS_PER_USD,
    ),
    ("anthropic", "claude-haiku-4-5"): ModelPrice(
        provider="anthropic",
        model="claude-haiku-4-5",
        input_micros_per_mtok=_MICROS_PER_USD,
        output_micros_per_mtok=5 * _MICROS_PER_USD,
    ),
    # OpenAI (May 2026 rates)
    ("openai", "gpt-5"): ModelPrice(
        provider="openai",
        model="gpt-5",
        input_micros_per_mtok=10 * _MICROS_PER_USD,
        output_micros_per_mtok=30 * _MICROS_PER_USD,
    ),
    ("openai", "gpt-5-mini"): ModelPrice(
        provider="openai",
        model="gpt-5-mini",
        input_micros_per_mtok=2 * _MICROS_PER_USD,
        output_micros_per_mtok=8 * _MICROS_PER_USD,
    ),
}


def get_price(provider: str, model: str) -> ModelPrice | None:
    """Look up a price by (provider, model). Returns None if unknown."""
    return _PRICES.get((provider, model))


def add_model(price: ModelPrice) -> None:
    """Register or override a model price at runtime. Operator escape hatch."""
    _PRICES[(price.provider, price.model)] = price


def known_models() -> list[ModelPrice]:
    """Sorted list of all currently-registered models."""
    return sorted(_PRICES.values(), key=lambda p: (p.provider, p.model))


def estimate_cost_micros(
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
) -> int | None:
    """Convenience helper used by `tokencost record`. None if model unknown."""
    price = get_price(provider, model)
    if price is None:
        return None
    return price.cost_micros(input_tokens, output_tokens)
