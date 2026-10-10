"""Behavioral RED proofs: exact exit 1, named failures and surviving controls.

Run with the same Python that runs the green suite: python -m spike.red_proof.
Only disposable copies are mutated; no test double changes per variant.
"""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
CASES = [
    (
        "environment_leak",
        '    return {\n        "HOME":',
        '    return {**source,\n        "HOME":',
        {"test_operator_credentials_are_scrubbed"},
    ),
    (
        "accept_killed_process",
        "    if exit_code != 0:",
        "    if False:",
        {"test_killed_cell_is_invalid_even_with_partial_score"},
    ),
    (
        "allow_operator_connector",
        '                if condition != "stompy" or server != "stompy":',
        "                if False:",
        {"test_stray_mcp_server_in_teammate_is_invalid"},
    ),
]
CONTROLS = {
    "test_success_control",
    "test_complete_matrix_control",
    "test_lead_and_teammate_histograms_and_no_double_count",
}


def execute(root, xml):
    process = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/spike/test_integrity.py",
            "-q",
            "--junitxml=" + str(xml),
        ],
        cwd=root,
        capture_output=True,
        text=True,
    )
    tree = ET.parse(xml)
    failed = {
        t.get("name") for t in tree.iter("testcase") if t.find("failure") is not None
    }
    errors = {
        t.get("name") for t in tree.iter("testcase") if t.find("error") is not None
    }
    passed = {
        t.get("name")
        for t in tree.iter("testcase")
        if all(t.find(k) is None for k in ("failure", "error", "skipped"))
    }
    return process.returncode, failed, errors, passed


def main():
    proof = []
    with tempfile.TemporaryDirectory(prefix="stompy-2699-red-") as temp:
        root = Path(temp)
        for directory in ("spike", "tests"):
            shutil.copytree(
                ROOT / directory,
                root / directory,
                ignore=shutil.ignore_patterns("__pycache__"),
            )
        green = execute(root, root / "green.xml")
        assert green[0] == 0 and not green[1] and not green[2], green
        source = root / "spike/integrity.py"
        original = source.read_text()
        for name, old, new, expected in CASES:
            assert original.count(old) == 1, (name, "revert anchor drift")
            source.write_text(original.replace(old, new))
            # Avoid timestamp/size bytecode reuse across rapidly changed variants.
            shutil.rmtree(root / "spike/__pycache__", ignore_errors=True)
            code, failed, errors, passed = execute(root, root / (name + ".xml"))
            assert code == 1 and failed == expected and not errors, (
                name,
                code,
                failed,
                errors,
            )
            assert CONTROLS <= passed, (name, "control failure")
            proof.append(
                {
                    "revert": name,
                    "exit_code": code,
                    "failures": sorted(failed),
                    "controls": sorted(CONTROLS),
                }
            )
            source.write_text(original)
    print(json.dumps({"green": len(green[3]), "red": proof}, indent=2))


if __name__ == "__main__":
    main()
