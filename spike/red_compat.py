"""Reproduce the two live CLI/API incompatibilities by behavioral revert."""

import json
import shutil
import tempfile
from pathlib import Path

from spike.red_proof import ROOT, execute


def main():
    cases = [
        (
            "adaptive_display",
            'if thinking.get("type") == "adaptive"',
            'if False and thinking.get("type") == "adaptive"',
            "test_cli_adaptive_display_is_normalized_before_counting",
        ),
        (
            "server_context_editing",
            'body.pop("context_management", None)',
            'body.get("context_management", None)',
            "test_unsupported_server_context_editing_is_removed",
        ),
    ]
    evidence = []
    with tempfile.TemporaryDirectory(prefix="2699-compat-red-") as temp:
        root = Path(temp)
        for folder in ("spike", "tests"):
            shutil.copytree(
                ROOT / folder,
                root / folder,
                ignore=shutil.ignore_patterns("__pycache__"),
            )
        target = root / "spike/gateway_server.py"
        original = target.read_text()
        test = "tests/spike/test_gateway_server.py"
        code, failures, errors, passed = execute(root, root / "green.xml", test)
        assert code == 0 and not failures and not errors
        for name, old, new, expected in cases:
            assert original.count(old) == 1
            target.write_text(original.replace(old, new))
            shutil.rmtree(root / "spike/__pycache__", ignore_errors=True)
            code, failures, errors, passed = execute(root, root / (name + ".xml"), test)
            assert code == 1 and failures == {expected} and not errors
            assert "test_upstream_rebuilds_headers_with_provider_key_only" in passed
            assert (
                "test_provider_failure_retains_reservation_and_stops_next_billable_call"
                in passed
            )
            evidence.append(
                {
                    "revert": name,
                    "exit_code": code,
                    "failures": sorted(failures),
                    "controls": sorted(passed),
                }
            )
            target.write_text(original)
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
