"""Behavioral reverts retain imports/signatures and require named exit-1 failures."""

import json
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from spike.red_proof import ROOT, execute

CASES = [
    (
        "rounded_cache_rate",
        "gateway_rates.py",
        'Decimal("0.30")',
        'Decimal("1")',
        "test_split_rates.py",
        {
            "test_settlement_prices_actual_cache_categories",
            "test_fractional_cache_read_rounds_up_once_per_request",
        },
        {"test_unknown_usage_preserves_charge_and_refuses_next_request"},
    ),
    (
        "remove_safety",
        "gateway_rates.py",
        'SAFETY = Decimal("1.5")',
        'SAFETY = Decimal("1")',
        "test_split_rates.py",
        {"test_reservation_applies_one_point_five_safety"},
        {"test_settlement_prices_actual_cache_categories"},
    ),
    (
        "discard_confirmed_prefix",
        "gateway_cache.py",
        "cached = min(total, cached)",
        "cached = 0",
        "test_cache_forecast.py",
        {"test_only_confirmed_matching_prefix_receives_cache_read_estimate"},
        {"test_expired_cache_is_cold"},
    ),
    (
        "ignore_pending_liability",
        "gateway_budget.py",
        "self.ceiling - self.charged - self.liability",
        "self.ceiling - self.charged",
        "test_split_guard.py",
        {"test_pending_cold_liability_prevents_concurrent_overcommit"},
        {"test_warm_guess_cannot_bypass_cold_miss_affordability"},
    ),
    (
        "remove_top_up",
        "spend.py",
        "CEILING = 25.0",
        "CEILING = 20.0",
        "test_spend.py",
        {"test_top_up_preserves_prior_attempts_and_enforces_twenty_five"},
        {
            "test_unknown_attempt_never_releases_its_reservation",
            "test_corrupt_ledger_cannot_reset_spend",
        },
    ),
]


def main():
    proof = []
    with tempfile.TemporaryDirectory(prefix="2699-split-red-") as tmp:
        root = Path(tmp)
        for folder in ("spike", "tests"):
            shutil.copytree(
                ROOT / folder,
                root / folder,
                ignore=shutil.ignore_patterns("__pycache__"),
            )
        for name, file, old, new, test, expected, controls in CASES:
            target = root / "spike" / file
            original = target.read_text()
            test = "tests/spike/" + test
            green = execute(root, root / "green.xml", test)
            assert green[0] == 0 and not green[1] and not green[2], (name, green)
            assert original.count(old) == 1, (name, "anchor drift")
            target.write_text(original.replace(old, new))
            shutil.rmtree(root / "spike/__pycache__", ignore_errors=True)
            code, failed, errors, passed = execute(root, root / (name + ".xml"), test)
            assert code == 1 and failed == expected and not errors, (
                name,
                code,
                failed,
                errors,
            )
            assert controls <= passed, (name, "control failed")
            proof.append(
                dict(
                    revert=name,
                    exit_code=code,
                    failures=sorted(failed),
                    controls=sorted(controls),
                )
            )
            target.write_text(original)
            shutil.rmtree(root / "spike/__pycache__", ignore_errors=True)
    print(json.dumps(proof, indent=2))


if __name__ == "__main__":
    main()
