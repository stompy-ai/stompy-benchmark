import pytest

from spike.gateway_budget import Budget


def test_reservation_prevents_concurrent_overspend():
    budget = Budget(0.10, 1000000)
    _, charge, tokens = budget.reserve(10000, 4096)
    assert charge <= 100000
    with pytest.raises(ValueError):
        budget.reserve(10000, 4096)
    budget.settle(charge, tokens, {"input_tokens": 10000, "output_tokens": 1})
    assert budget.charged == 30015


def test_unknown_billing_never_becomes_free():
    budget = Budget(1, 1000000)
    _, charge, tokens = budget.reserve(10, 100)
    budget.settle(charge, tokens, None)
    assert budget.charged == charge and budget.unknown
    with pytest.raises(ValueError):
        budget.reserve(1, 1)


def test_token_ceiling_is_independent_of_dollars():
    budget = Budget(100, 100)
    output, _, _ = budget.reserve(99, 5000)
    assert output == 1
    with pytest.raises(ValueError):
        budget.reserve(1, 1)
