"""Own the private gateway lifecycle without receiving its provider credential."""

import hashlib
import json
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path

PYTHON_IMAGE = "sha256:3ad37ccd1797321f4bda14f483941a4f7a2b9eca454847b22652e59f5baab8c9"


@contextmanager
def gateway(output: Path, budget: float):
    root = Path(__file__).resolve().parent
    evidence = output / "gateway"
    evidence.mkdir(parents=True, exist_ok=False)
    name = (
        "gateway2699-" + hashlib.sha256(str(output.resolve()).encode()).hexdigest()[:16]
    )
    command = [
        "bash",
        str(root / "start_gateway.sh"),
        name,
        str(root),
        str(evidence.resolve()),
        str(budget),
        "1000000",
        PYTHON_IMAGE,
    ]
    # No credential enters this process or the grader/publisher environment.
    with (evidence / "startup.log").open("w") as log:
        process = subprocess.Popen(command, stdout=log, stderr=log)
        try:
            for _ in range(60):
                if process.poll() is not None:
                    raise ValueError("private gateway failed to start")
                probe = subprocess.run(
                    [
                        "docker",
                        "exec",
                        name,
                        "python",
                        "-c",
                        "import urllib.request; urllib.request.urlopen('http://127.0.0.1:18777/health', timeout=1).read()",
                    ],
                    capture_output=True,
                )
                if probe.returncode == 0:
                    break
                time.sleep(0.5)
            else:
                raise ValueError("private gateway readiness timed out")
            yield {
                "container": name,
                "url": "http://127.0.0.1:18777",
                "evidence": evidence,
            }
        finally:
            subprocess.run(["docker", "rm", "-f", name], capture_output=True)
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


def evidence(output: Path):
    data = json.loads((output / "gateway/gateway.json").read_text())
    if data["charged_upper_bound_usd"] > data["ceiling_usd"]:
        raise ValueError("gateway budget invariant violated")
    return data
