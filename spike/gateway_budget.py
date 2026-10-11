"""Split-rate reservations with 1.5x safety and a cold-cache liability guard."""

from decimal import Decimal
from threading import Lock

try:
    from .gateway_rates import FIELDS, MODEL, RATES, SAFETY, count, rounded, usage_cost
except ImportError:  # Gateway container invokes gateway_server.py directly.
    from gateway_rates import FIELDS, MODEL, RATES, SAFETY, count, rounded, usage_cost


class Budget:
    def __init__(self, ceiling_usd: float, token_ceiling: int):
        self.rates = RATES[MODEL]
        self.ceiling = int(Decimal(str(ceiling_usd)) * 1_000_000)
        self.token_ceiling = count(token_ceiling)
        self.charged = self.tokens = self.requests = 0
        self.accepted_requests = 0
        self.unknown = False
        self.lock = Lock()
        self.pending: list[tuple[int, int, int]] = []
        self.cache_misses = 0
        self.last_reservation: dict = {}

    @property
    def liability(self) -> int:
        return sum(cold - split for split, _, cold in self.pending)

    def reserve(
        self, input_tokens: int, requested_output: int, split: dict | None = None
    ) -> tuple[int, int, int]:
        if self.unknown:
            raise ValueError("previous request has unknown billing")
        count(input_tokens)
        count(requested_output)
        split = (
            dict(split)
            if split is not None
            else {
                "input_tokens": 0,
                "cache_creation_input_tokens": input_tokens,
            }
        )
        split["output_tokens"] = 0
        estimated_input = usage_cost(split)
        if sum(count(split.get(k, 0)) for k in FIELDS) != input_tokens:
            raise ValueError("input split does not match count")
        available = self.ceiling - self.charged - self.liability
        # Cache reads are forecasts, not provider guarantees. Leave enough for
        # a complete cache miss, including count-estimate safety, before calling.
        cold_input = input_tokens * self.rates["cache_write"]
        output = min(
            requested_output,
            4096,
            int((Decimal(available) / SAFETY - cold_input) // self.rates["output"]),
            self.token_ceiling - self.tokens - input_tokens,
        )
        if output < 1:
            raise ValueError("gateway budget exhausted")
        amount = rounded(SAFETY * (estimated_input + output * self.rates["output"]))
        cold = rounded(SAFETY * (cold_input + output * self.rates["output"]))
        if amount > cold or cold > available:
            raise ValueError("gateway budget exhausted")
        reserved_tokens = input_tokens + output
        self.pending.append((amount, reserved_tokens, cold))
        self.charged += amount
        self.tokens += reserved_tokens
        self.requests += 1
        self.last_reservation = {
            "input_split_estimate": split,
            "output_token_limit": output,
            "split_reservation_usd": amount / 1_000_000,
            "cold_miss_bound_usd": cold / 1_000_000,
        }
        return output, amount, reserved_tokens

    def _pending(self, reservation: int, reserved_tokens: int) -> tuple[int, int, int]:
        return next(
            row for row in self.pending if row[:2] == (reservation, reserved_tokens)
        )

    def refund(self, reservation: int, reserved_tokens: int) -> None:
        row = self._pending(reservation, reserved_tokens)
        self.pending.remove(row)
        self.charged -= reservation
        self.tokens -= reserved_tokens

    def settle(
        self, reservation: int, reserved_tokens: int, usage: dict | None
    ) -> None:
        try:
            row = self._pending(reservation, reserved_tokens)
            cost = rounded(usage_cost(usage))
            actual_tokens = sum(count(usage.get(k, 0)) for k in FIELDS)
        except (ValueError, TypeError, StopIteration):
            self.unknown = True
            return
        if (
            cost > row[2]
            or self.tokens - reserved_tokens + actual_tokens > self.token_ceiling
        ):
            self.unknown = True
            return
        self.cache_misses += cost > reservation
        self.pending.remove(row)
        self.charged += cost - reservation
        self.tokens += actual_tokens - reserved_tokens

    def snapshot(self) -> dict:
        return {
            "charged_upper_bound_usd": (self.charged + self.liability) / 1_000_000,
            "ceiling_usd": self.ceiling / 1_000_000,
            "tokens": self.tokens,
            "token_ceiling": self.token_ceiling,
            "requests": self.requests,
            "accepted_requests": self.accepted_requests,
            "billing_unknown": self.unknown,
            "pricing_policy": "sonnet-4-6-split-2026-10-11",
            "rates_usd_per_million": {k: str(v) for k, v in self.rates.items()},
            "reservation_safety_factor": str(SAFETY),
            "cache_estimate_overruns": self.cache_misses,
            "last_reservation": self.last_reservation,
            "cold_miss_liability_usd": self.liability / 1_000_000,
        }
