"""Trusted grader for Node/Vitest tasks: hidden oracle copied beside a read-only submission, no network."""

import json
import subprocess
from pathlib import Path

from spike.grader import parse_grade

SCRIPT = (
    "cp -r /submission /tmp/sub && mkdir -p /tmp/sub/tests && cp /oracle/*.test.ts /tmp/sub/tests/ "
    "&& cd /tmp/sub && ./node_modules/.bin/vitest run tests/handover.test.ts --reporter=junit --outputFile=/evidence/junit.xml"
)


def command(submission: Path, task: Path, output: Path, image: str, name: str) -> list:
    return [
        "docker", "run", "--rm", "--name", name,
        "--network", "none", "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
        "--memory", "2g", "--pids-limit", "256", "--tmpfs", "/tmp:rw,nosuid,exec,size=1g",
        "-v", f"{submission.resolve()}:/submission:ro",
        "-v", f"{(task / 'hidden-tests').resolve()}:/oracle:ro",
        "-v", f"{output.resolve()}:/evidence",
        "-e", "MERIDIAN_AUTH_SECRET=oracle-secret", "-e", "CI=1",
        "--entrypoint", "bash", image, "-lc", SCRIPT,
    ]


def grade_node(submission: Path, task: Path, output: Path, image: str, timeout: int = 300) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    expected = json.loads((task / "hidden-tests/expected.json").read_text())
    name = "grade2798-" + output.resolve().name[:16]
    with (output / "grader.log").open("w") as log:
        try:
            code = subprocess.run(command(submission, task, output, image, name),
                                  stdout=log, stderr=subprocess.STDOUT, timeout=timeout).returncode
        except subprocess.TimeoutExpired:
            code = 124
        finally:
            subprocess.run(["docker", "rm", "-f", name], capture_output=True)
    result = parse_grade(output / "junit.xml", code, expected)
    result["exit_code"] = code
    result["grader_image"] = image
    (output / "scores.json").write_text(json.dumps(result, indent=2) + "\n")
    return result
