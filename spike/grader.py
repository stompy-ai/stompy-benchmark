"""Trusted Docker grader: immutable tests/deps, read-only submission, no network."""

import hashlib
import json
import subprocess
from pathlib import Path
from xml.etree import ElementTree as ET

GRADER_IMAGE = "sha256:b458acffeef6d5a6e10a1f7375e69d4d7c243697bff114b69f78f2e36e2b4772"
EXPECTED = {
    "test_transition_response_and_arguments": False,
    "test_invalid_state_is_422": False,
    "test_critical_viewer_cannot_transition": True,
    "test_critical_cross_project_key_refused": True,
    "test_missing_topic_maps_to_404": False,
    "test_idempotent_result_preserved": False,
    "test_contract_names_route_and_keeps_mcp": False,
    "test_critical_authentication_required": True,
}


def _critical(entry) -> bool:
    return entry if isinstance(entry, bool) else bool(entry["critical"])


def parse_grade(xml: Path, exit_code: int, expected: dict | None = None) -> dict:
    expected = EXPECTED if expected is None else expected
    total_max = sum(not _critical(e) for e in expected.values())
    invalid = {"outcome": "INVALID", "total_score": None, "total_max": total_max, "checks": []}
    if exit_code not in {0, 1} or not xml.exists():
        return {**invalid, "reason": "grader did not complete"}
    try:
        tests = list(ET.parse(xml).iter("testcase"))
    except ET.ParseError:
        return {**invalid, "reason": "invalid grader XML"}
    names = [t.get("name") for t in tests]
    if len(names) != len(expected) or set(names) != set(expected):
        return {**invalid, "reason": "grader test identity set mismatch"}
    if any(t.find("error") is not None or t.find("skipped") is not None for t in tests):
        return {**invalid, "reason": "grader errors/skips are not task scores"}
    checks = [
        {
            "name": t.get("name"),
            "critical": _critical(expected[t.get("name")]),
            "passed": t.find("failure") is None,
        }
        for t in tests
    ]
    passed = all(c["passed"] for c in checks)
    if (exit_code == 0) != passed:
        return {**invalid, "reason": "grader exit contradicts test report"}
    score = sum(c["passed"] for c in checks if not c["critical"])
    result = {
        "outcome": "OK" if passed else "TASK_FAIL",
        "total_score": score,
        "total_max": total_max,
        "critical_passed": all(c["passed"] for c in checks if c["critical"]),
        "checks": checks,
        "grader_image": GRADER_IMAGE,
    }
    decisions = {
        c["name"]: c["passed"] for c in checks
        if isinstance(expected[c["name"]], dict) and expected[c["name"]].get("decision")
    }
    if decisions:
        result["decisions"] = decisions
    return result


def grade(submission: Path, task: Path, output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    name = (
        "grade2699-" + hashlib.sha256(str(output.resolve()).encode()).hexdigest()[:16]
    )
    command = [
        "docker",
        "run",
        "--rm",
        "--name",
        name,
        "--network",
        "none",
        "--read-only",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--memory",
        "2g",
        "--pids-limit",
        "128",
        "--tmpfs",
        "/tmp:rw,nosuid,size=128m",
        "--workdir",
        "/oracle",
        "--entrypoint",
        "/usr/bin/env",
        "-v",
        f"{submission.resolve()}:/submission:ro",
        "-v",
        f'{(task/"hidden-tests").resolve()}:/oracle:ro',
        "-v",
        f"{output.resolve()}:/evidence",
        GRADER_IMAGE,
        "-i",
        "PATH=/usr/local/bin:/usr/bin:/bin",
        "PYTHONDONTWRITEBYTECODE=1",
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1",
        "DATABASE_URL=postgresql://test:test@127.0.0.1:1/test",
        "AUTH0_DOMAIN=test.auth0.com",
        "AUTH0_CLIENT_ID=test",
        "AUTH0_CLIENT_SECRET=test",
        "OPENROUTER_API_KEY=test",
        "python",
        "-I",
        "/oracle/bootstrap.py",
    ]
    with (output / "grader.log").open("w") as log:
        try:
            code = subprocess.run(
                command, stdout=log, stderr=subprocess.STDOUT, timeout=120
            ).returncode
        except subprocess.TimeoutExpired:
            code = 124
        finally:
            subprocess.run(["docker", "rm", "-f", name], capture_output=True)
    result = parse_grade(output / "junit.xml", code)
    result["exit_code"] = code
    (output / "scores.json").write_text(json.dumps(result, indent=2) + "\n")
    return result
