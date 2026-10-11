import pytest

from spike.gateway_budget import Budget


def warm(tokens):
    return {"input_tokens": 0, "output_tokens": 0, "cache_read_input_tokens": tokens}


def test_warm_reservation_is_split_priced_and_safety_factored():
    budget = Budget(4.5, 15000000)
    output, reserved, _ = budget.reserve(100000, 1000, warm(100000))
    assert output == 1000 and reserved == 67500
    assert budget.snapshot()["cold_miss_liability_usd"] == 0.855


def test_cache_miss_settles_known_usage_without_exceeding_ceiling():
    budget = Budget(1, 15000000)
    _, reserved, tokens = budget.reserve(100000, 1000, warm(100000))
    budget.settle(
        reserved,
        tokens,
        {
            "input_tokens": 0,
            "output_tokens": 1000,
            "cache_creation_input_tokens": 100000,
        },
    )
    assert budget.charged == 615000 and budget.liability == 0
    assert budget.cache_misses == 1 and not budget.unknown


def test_warm_guess_cannot_bypass_cold_miss_affordability():
    budget = Budget(0.1, 15000000)
    with pytest.raises(ValueError, match="budget exhausted"):
        budget.reserve(100000, 1000, warm(100000))
    assert budget.requests == 0


def test_pending_cold_liability_prevents_concurrent_overcommit():
    budget = Budget(1, 15000000)
    budget.reserve(100000, 1000, warm(100000))
    with pytest.raises(ValueError):
        budget.reserve(100000, 1000, warm(100000))


def test_refusal_refunds_both_split_and_cold_liability():
    budget = Budget(1, 15000000)
    _, reserved, tokens = budget.reserve(100000, 1000, warm(100000))
    budget.refund(reserved, tokens)
    assert budget.charged == budget.tokens == budget.liability == 0


@pytest.mark.parametrize(
    "usage",
    [
        {"input_tokens": False, "output_tokens": 1},
        {
            "input_tokens": 1,
            "output_tokens": 1,
            "cache_creation_input_tokens": 10,
            "cache_creation": {"ephemeral_5m_input_tokens": 9},
        },
        {"input_tokens": 10000000, "output_tokens": 1},
    ],
)
def test_bad_or_unbounded_usage_keeps_reservation_and_stops(usage):
    budget = Budget(1, 15000000)
    _, reserved, tokens = budget.reserve(100000, 1000, warm(100000))
    before = budget.snapshot()["charged_upper_bound_usd"]
    budget.settle(reserved, tokens, usage)
    assert budget.unknown
    assert budget.snapshot()["charged_upper_bound_usd"] == before
    with pytest.raises(ValueError):
        budget.reserve(1, 1)
