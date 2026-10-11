import json

import pytest

from spike.spend import reserve, settle


def test_top_up_preserves_prior_attempts_and_enforces_twenty_five(tmp_path):
    p = tmp_path / "ledger.json"
    prior = {
        "old-a": {"upper_bound_usd": 4.179291, "state": "settled_upper_bound"},
        "old-b": {"upper_bound_usd": 1.936021, "state": "settled_upper_bound"},
    }
    p.write_text(json.dumps(prior))
    for n in range(4):
        reserve(str(n), 4.5, p)
    with pytest.raises(ValueError, match="ceiling"):
        reserve("extra", 1, p)
    after = json.loads(p.read_text())
    assert {k: after[k] for k in prior} == prior
    assert sum(x["upper_bound_usd"] for x in after.values()) == pytest.approx(24.115312)


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
