"""Reproduce the premature cached-history stop without any provider calls."""

import json
import shutil
import tempfile
from pathlib import Path

from spike.red_proof import ROOT, execute


def main():
    with tempfile.TemporaryDirectory(prefix="2699-token-red-") as tmp:
        root = Path(tmp)
        for directory in ("spike", "tests"):
            shutil.copytree(
                ROOT / directory,
                root / directory,
                ignore=shutil.ignore_patterns("__pycache__"),
            )
        test = "tests/spike/test_gateway_token_budget.py"
        code, failed, errors, passed = execute(root, root / "green.xml", test)
        assert code == 0 and not failed and not errors
        source = root / "spike/gateway.py"
        original = source.read_text()
        old = "str(int(budget * 1_000_000) // min(RATES[MODEL].values()))"
        assert original.count(old) == 1
        source.write_text(original.replace(old, '"1000000"'))
        shutil.rmtree(root / "spike/__pycache__", ignore_errors=True)
        code, failed, errors, passed = execute(root, root / "red.xml", test)
        expected = (
            "test_cached_history_can_exceed_one_million_tokens_within_dollar_budget"
        )
        assert code == 1 and failed == {expected} and not errors
        assert "test_gateway_dollar_reservation_still_refuses_overspend" in passed
        print(
            json.dumps(
                {
                    "exit_code": code,
                    "failures": sorted(failed),
                    "controls": sorted(passed),
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
