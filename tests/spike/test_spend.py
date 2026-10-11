import json

import pytest

from spike.spend import reserve, settle


def test_all_attempts_share_the_twenty_dollar_ceiling(tmp_path):
    p = tmp_path / "ledger.json"
    for n in range(4):
        reserve(str(n), 4.5, p)
    reserve("smoke", 1.25, p)
    reserve("kill", 0.25, p)
    with pytest.raises(ValueError, match="ceiling"):
        reserve("extra", 1, p)
    assert sum(x["upper_bound_usd"] for x in json.loads(p.read_text()).values()) == 19.5


def test_unknown_attempt_never_releases_its_reservation(tmp_path):
    p = tmp_path / "ledger.json"
    reserve("a", 4.5, p)
    settle("a", {"billing_unknown": True, "charged_upper_bound_usd": 0}, p)
    assert json.loads(p.read_text())["a"]["upper_bound_usd"] == 4.5
    with pytest.raises(ValueError, match="reuse"):
        reserve("a", 0.1, p)


def test_corrupt_ledger_cannot_reset_spend(tmp_path):
    p = tmp_path / "ledger.json"
    p.write_text("")
    with pytest.raises(json.JSONDecodeError):
        reserve("a", 1, p)
