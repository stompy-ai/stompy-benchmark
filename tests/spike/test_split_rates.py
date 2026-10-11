import pytest

from spike.gateway_budget import Budget


def test_settlement_prices_actual_cache_categories():
    budget = Budget(4.5, 15000000)
    _, reserved, tokens = budget.reserve(100000, 1000)
    budget.settle(
        reserved,
        tokens,
        {
            "input_tokens": 1000,
            "output_tokens": 1000,
            "cache_read_input_tokens": 90000,
            "cache_creation_input_tokens": 9000,
            "cache_creation": {
                "ephemeral_5m_input_tokens": 8000,
                "ephemeral_1h_input_tokens": 1000,
            },
        },
    )
    assert budget.charged == 81000
    assert not budget.unknown


def test_reservation_applies_one_point_five_safety():
    budget = Budget(4.5, 15000000)
    output, reserved, _ = budget.reserve(10000, 1000)
    assert output == 1000
    assert reserved == 112500


def test_fractional_cache_read_rounds_up_once_per_request():
    budget = Budget(1, 100000)
    _, reserved, tokens = budget.reserve(3, 1)
    budget.settle(
        reserved,
        tokens,
        {
            "input_tokens": 0,
            "output_tokens": 1,
            "cache_read_input_tokens": 3,
        },
    )
    assert budget.charged == 16


def test_unknown_usage_preserves_charge_and_refuses_next_request():
    budget = Budget(1, 100000)
    _, reserved, tokens = budget.reserve(100, 100)
    budget.settle(reserved, tokens, None)
    assert budget.unknown and budget.charged == reserved
    with pytest.raises(ValueError):
        budget.reserve(1, 1)
