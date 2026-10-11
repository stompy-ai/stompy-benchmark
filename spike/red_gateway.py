"""Revoke gateway budget decisions in disposable copies; exact named RED."""

import json
import shutil
import tempfile
from pathlib import Path

from spike.red_proof import ROOT, execute


def main():
    cases = [
        (
            "ignore_prior_spend",
            "self.ceiling - self.charged - self.liability",
            "self.ceiling - self.liability",
            "test_reservation_prevents_concurrent_overspend",
        ),
        (
            "continue_after_unknown_billing",
            "if self.unknown:",
            "if False:",
            "test_unknown_billing_never_becomes_free",
        ),
    ]
    proof = []
    with tempfile.TemporaryDirectory(prefix="2699-budget-red-") as tmp:
        root = Path(tmp)
        for folder in ("spike", "tests"):
            shutil.copytree(
                ROOT / folder,
                root / folder,
                ignore=shutil.ignore_patterns("__pycache__"),
            )
        target = root / "spike/gateway_budget.py"
        original = target.read_text()
        test = "tests/spike/test_gateway_budget.py"
        code, failed, errors, passed = execute(root, root / "green.xml", test)
        assert code == 0 and not failed and not errors
        for name, old, new, expected in cases:
            assert original.count(old) == 1
            target.write_text(original.replace(old, new))
            shutil.rmtree(root / "spike/__pycache__", ignore_errors=True)
            code, failed, errors, passed = execute(root, root / (name + ".xml"), test)
            assert code == 1 and failed == {expected} and not errors, (
                code,
                failed,
                errors,
            )
            assert "test_token_ceiling_is_independent_of_dollars" in passed
            proof.append(
                {
                    "revert": name,
                    "exit_code": code,
                    "failures": sorted(failed),
                    "controls": sorted(passed),
                }
            )
            target.write_text(original)
    print(json.dumps(proof, indent=2))


if __name__ == "__main__":
    main()
