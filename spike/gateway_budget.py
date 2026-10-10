"""Conservative Sonnet 4.6 budget, in integer microdollars; no free unknowns.

Rates: platform.claude.com/docs/en/about-claude/pricing (2026-10-10).
Reserve all input at the 1-hour cache-write rate ($6/M); output $15/M.
Disable premium/server tools and region/fast surcharges at the gateway boundary.
"""

from threading import Lock


class Budget:
    def __init__(self, ceiling_usd, token_ceiling):
        self.ceiling = int(ceiling_usd * 1_000_000)
        self.token_ceiling = token_ceiling
        self.charged = self.tokens = self.requests = 0
        self.accepted_requests = 0
        self.unknown = False
        self.lock = Lock()

    def reserve(self, input_tokens, requested_output):
        if self.unknown:
            raise ValueError("previous request has unknown billing")
        remaining = self.ceiling - self.charged - input_tokens * 6
        output = min(
            requested_output,
            4096,
            remaining // 15,
            self.token_ceiling - self.tokens - input_tokens,
        )
        if input_tokens < 0 or output < 1:
            raise ValueError("gateway budget exhausted")
        amount = input_tokens * 6 + output * 15
        self.charged += amount
        self.tokens += input_tokens + output
        self.requests += 1
        return output, amount, input_tokens + output

    def settle(self, reservation, reserved_tokens, usage):
        fields = (
            "input_tokens",
            "output_tokens",
            "cache_creation_input_tokens",
            "cache_read_input_tokens",
        )
        if (
            not isinstance(usage, dict)
            or any(
                not isinstance(usage.get(k, 0), int) or usage.get(k, 0) < 0
                for k in fields
            )
            or "input_tokens" not in usage
            or "output_tokens" not in usage
        ):
            self.unknown = True
            return
        # Round cached reads UP to $1/M rather than pretending precision.
        cost = usage["input_tokens"] * 3 + usage["output_tokens"] * 15
        cost += usage.get("cache_creation_input_tokens", 0) * 6
        cost += usage.get("cache_read_input_tokens", 0)
        if cost > reservation:
            self.unknown = True
            return
        self.charged += cost - reservation
        self.tokens += sum(usage.get(k, 0) for k in fields) - reserved_tokens

    def snapshot(self):
        return {
            "charged_upper_bound_usd": self.charged / 1_000_000,
            "ceiling_usd": self.ceiling / 1_000_000,
            "tokens": self.tokens,
            "token_ceiling": self.token_ceiling,
            "requests": self.requests,
            "accepted_requests": self.accepted_requests,
            "billing_unknown": self.unknown,
        }
