"""Pinned Sonnet 4.6 standard/global rates; integer accounting rounds up.

Source: https://platform.claude.com/docs/en/about-claude/pricing (2026-10-11).
Dollar/MTok is numerically microdollars/token. Decimal avoids fractional drift.
Missing cache-write TTL detail is bounded at the 1-hour rate, never guessed free.
"""

from decimal import Decimal, ROUND_CEILING

MODEL = "claude-sonnet-4-6"
RATES = {
    MODEL: {
        "input": Decimal("3"),
        "output": Decimal("15"),
        "cache_write": Decimal("6"),
        "cache_write_5m": Decimal("3.75"),
        "cache_write_1h": Decimal("6"),
        "cache_read": Decimal("0.30"),
    }
}
SAFETY = Decimal("1.5")
FIELDS = (
    "input_tokens",
    "output_tokens",
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
)


def count(value: object) -> int:
    if type(value) is not int or value < 0:
        raise ValueError("invalid token count")
    return value


def rounded(value: Decimal) -> int:
    return int(value.to_integral_value(rounding=ROUND_CEILING))


def usage_cost(usage: dict) -> Decimal:
    if (
        not isinstance(usage, dict)
        or not {"input_tokens", "output_tokens"} <= usage.keys()
    ):
        raise ValueError("missing usage")
    values = {k: count(usage.get(k, 0)) for k in FIELDS}
    rates = RATES[MODEL]
    writes = values["cache_creation_input_tokens"]
    detail = usage.get("cache_creation")
    write_cost = writes * rates["cache_write"]
    if detail is not None:
        if not isinstance(detail, dict):
            raise ValueError("invalid cache creation detail")
        five = count(detail.get("ephemeral_5m_input_tokens", 0))
        hour = count(detail.get("ephemeral_1h_input_tokens", 0))
        if five + hour != writes:
            raise ValueError("cache creation totals disagree")
        write_cost = five * rates["cache_write_5m"] + hour * rates["cache_write_1h"]
    return (
        values["input_tokens"] * rates["input"]
        + values["output_tokens"] * rates["output"]
        + values["cache_read_input_tokens"] * rates["cache_read"]
        + write_cost
    )
