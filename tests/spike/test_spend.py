import json
from pathlib import Path

import pytest

from spike.spend import reserve, settle


def test_top_up_preserves_prior_attempts_and_enforces_thirty(tmp_path):
    p = tmp_path / "ledger.json"
    prior = {
        "old-a": {"upper_bound_usd": 4.179291, "state": "settled_upper_bound"},
        "old-b": {"upper_bound_usd": 1.936021, "state": "settled_upper_bound"},
    }
    p.write_text(json.dumps(prior))
    for n in range(4):
        reserve(str(n), 4.5, p)
    reserve("extra", 4.5, p)
    with pytest.raises(ValueError, match="ceiling"):
        reserve("over", 2, p)
    after = json.loads(p.read_text())
    assert {k: after[k] for k in prior} == prior
    assert sum(x["upper_bound_usd"] for x in after.values()) == pytest.approx(28.615312)


def test_unknown_attempt_never_releases_its_reservation(tmp_path):
    p = tmp_path / "ledger.json"
    p.write_text("{}")
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


def test_ledger_lives_outside_temp_cleanup():
    from spike.spend import LEDGER

    assert not str(LEDGER).startswith(("/tmp", "/private/tmp", "/var"))
    assert LEDGER == Path.home() / ".config" / "stompy" / "benchmark-spend.json"


def test_missing_ledger_is_an_error_not_a_fresh_budget(tmp_path):
    with pytest.raises(FileNotFoundError, match="seed"):
        reserve("a", 1, tmp_path / "ledger.json")


def test_seed_creates_ledger_once_with_historical_upper_bound(tmp_path):
    from spike.spend import seed

    p = tmp_path / "ledger.json"
    seed(p, "historical_pre_2026-10-17", 18.061944)
    assert json.loads(p.read_text()) == {
        "historical_pre_2026-10-17": {
            "upper_bound_usd": 18.061944,
            "state": "settled_upper_bound",
        }
    }
    with pytest.raises(FileExistsError):
        seed(p, "again", 1)
    reserve("a", 4.5, p)
    reserve("b", 4.5, p)
    with pytest.raises(ValueError, match="ceiling"):
        reserve("c", 4.5, p)
