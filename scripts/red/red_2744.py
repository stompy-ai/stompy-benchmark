"""Exact named exit-1 behavioral reverts; imports/signatures stay intact."""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
CONTROL = "test_unknown_usage_still_stops_without_refund"
CASES = [
    (
        "refusal_invalidates",
        "runner.py",
        'if row["gateway"].get("refusal_reason"):',
        "if False:",
        "test_gateway_refusal_invalidates_even_success_terminal",
    ),
    (
        "shared_instruction",
        "run.py",
        "+ VERIFICATION",
        '+ ""',
        "test_focused_verification_identical_for_both_arms",
    ),
    (
        "wall_backstop",
        "runner.py",
        "timeout: int = 1800",
        "timeout: int = 900",
        "test_timeout_backstop_is_1800_and_cell_dollars_unchanged",
    ),
    (
        "ledger_top_up",
        "spend.py",
        "CEILING = 30.0",
        "CEILING = 25.0",
        "test_thirty_dollar_top_up_preserves_all_prior_attempts",
    ),
    (
        "owned_forecast",
        "gateway_budget.py",
        "self.cache_forecast = CacheForecast()",
        "self.cache_forecast = None",
        "test_budget_owns_an_isolated_cache_forecast",
    ),
    (
        "known_token_breach",
        "gateway_budget.py",
        "if self.tokens > self.token_ceiling:\n            self.refusal_reason",
        "if self.tokens > self.token_ceiling:\n            self.unknown = True\n            self.refusal_reason",
        "test_known_token_breach_is_not_unknown_billing",
    ),
    (
        "retryable_status",
        "gateway_server.py",
        "                402,",
        "                429,",
        "test_local_dollar_refusal_is_nonretryable_and_audited",
    ),
    (
        "named_timeout",
        "runner.py",
        "if killed and kill_after is None:",
        "if False:",
        "test_named_timeout_survives_missing_terminal",
    ),
    (
        "independent_causes",
        "invalidation.py",
        "for value in (previous, reason):",
        "for value in (previous,):",
        "test_budget_reason_and_build_drift_both_survive",
    ),
    (
        "token_diagnostic",
        "gateway_budget.py",
        'self.refuse("token ceiling exceeded")',
        'self.refuse("dollar budget exhausted")',
        "test_token_admission_refusal_distinct_from_dollars",
    ),
    (
        "report_causes",
        "report.py",
        '"; ".join(r.get("reasons", []))',
        '""',
        "test_report_renders_all_independent_reasons",
    ),
]


def execute(root: Path, test: str) -> tuple:
    xml = root / "proof.xml"
    refusal = test == "test_gateway_refusal_invalidates_even_success_terminal"
    prefix = "tests/spike/" + (
        "test_runner_refusal.py::" if refusal else "test_2744_envelope.py::"
    )
    control = "test_clean_terminal_remains_valid" if refusal else CONTROL
    run = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            prefix + test,
            prefix + control,
            "-q",
            "--junitxml=" + str(xml),
        ],
        cwd=root,
        capture_output=True,
        text=True,
    )
    cases = list(ET.parse(xml).iter("testcase"))
    failed = {t.get("name") for t in cases if t.find("failure") is not None}
    errors = {t.get("name") for t in cases if t.find("error") is not None}
    passed = {
        t.get("name")
        for t in cases
        if all(t.find(k) is None for k in ("failure", "error", "skipped"))
    }
    return run.returncode, failed, errors, passed


def main() -> None:
    proof = []
    with tempfile.TemporaryDirectory(prefix="2744-red-") as tmp:
        root = Path(tmp)
        for folder in ("spike", "tests", "tasks"):
            shutil.copytree(
                ROOT / folder,
                root / folder,
                ignore=shutil.ignore_patterns("__pycache__"),
            )
        for name, file, old, new, test in CASES:
            green = execute(root, test)
            assert green[0] == 0 and not green[1] and not green[2], (name, green)
            target = root / "spike" / file
            original = target.read_text()
            assert original.count(old) == 1, (name, "anchor drift")
            target.write_text(original.replace(old, new))
            shutil.rmtree(root / "spike/__pycache__", ignore_errors=True)
            code, failed, errors, passed = execute(root, test)
            assert code == 1 and failed == {test} and not errors, (
                name,
                code,
                failed,
                errors,
            )
            control = (
                "test_clean_terminal_remains_valid"
                if test == "test_gateway_refusal_invalidates_even_success_terminal"
                else CONTROL
            )
            assert control in passed, (name, "control failed")
            proof.append(
                dict(
                    revert=name,
                    exit_code=code,
                    failures=sorted(failed),
                    controls=[control],
                )
            )
            target.write_text(original)
            shutil.rmtree(root / "spike/__pycache__", ignore_errors=True)
    print(json.dumps(proof, indent=2))


if __name__ == "__main__":
    main()
