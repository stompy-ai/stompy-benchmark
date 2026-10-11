"""Real Docker isolation control using a dummy stdin key; zero provider calls."""

import json
import subprocess
import tempfile
import time
from pathlib import Path

from spike.gateway import PYTHON_IMAGE


def main():
    root = Path(__file__).resolve().parent
    suffix = str(time.time_ns())
    proxy = "proxy-control-" + suffix
    agent = "agent-control-" + suffix
    dummy = "dummy-provider-control-not-a-real-key"
    with tempfile.TemporaryDirectory(prefix="2699-proxy-control-") as tmp:
        output = Path(tmp)
        home = output / "home"
        home.mkdir()
        home.chmod(0o777)
        evidence = output / "evidence"
        evidence.mkdir()
        proc = subprocess.Popen(
            [
                "docker",
                "run",
                "--rm",
                "-i",
                "--name",
                proxy,
                "--read-only",
                "--cap-drop",
                "ALL",
                "--security-opt",
                "no-new-privileges",
                "-e",
                "BENCH_GATEWAY_BUDGET=0.01",
                "-e",
                "BENCH_GATEWAY_TOKENS=10",
                "-v",
                str(root) + ":/gateway:ro",
                "-v",
                str(evidence) + ":/evidence",
                "--workdir",
                "/gateway",
                "--entrypoint",
                "python",
                PYTHON_IMAGE,
                "gateway_server.py",
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            proc.stdin.write((dummy + "\n").encode())
            proc.stdin.close()
            for _ in range(40):
                ready = subprocess.run(
                    [
                        "docker",
                        "exec",
                        proxy,
                        "python",
                        "-c",
                        "import urllib.request; urllib.request.urlopen('http://127.0.0.1:18777/health').read()",
                    ],
                    capture_output=True,
                )
                if ready.returncode == 0:
                    break
                time.sleep(0.25)
            else:
                raise AssertionError("dummy gateway did not start")
            result = subprocess.run(
                [
                    "docker",
                    "run",
                    "--name",
                    agent,
                    "--network",
                    "container:" + proxy,
                    "--cap-drop",
                    "ALL",
                    "--read-only",
                    "--tmpfs",
                    "/tmp:rw,size=16m",
                    "-e",
                    "ANTHROPIC_BASE_URL=http://127.0.0.1:18777",
                    "-e",
                    "ANTHROPIC_AUTH_TOKEN=local-gateway-only",
                    "-v",
                    str(home) + ":/home/benchmark",
                    "stompy-2699-agent:spike",
                    "--version",
                ],
                capture_output=True,
                text=True,
            )
            assert result.returncode == 0, result.stderr
            configs = json.loads(
                subprocess.check_output(["docker", "inspect", proxy, agent], text=True)
            )
            assert all(dummy not in json.dumps(c) for c in configs)
            assert all(
                "ANTHROPIC_API_KEY=" not in e and "OP_SERVICE_ACCOUNT_TOKEN=" not in e
                for c in configs
                for e in c["Config"]["Env"]
            )
            assert (
                len(configs[1]["Mounts"]) == 1
                and configs[1]["Mounts"][0]["Destination"] == "/home/benchmark"
            )
            keys = json.loads((home / "launch-env-keys.json").read_text())
            assert (
                "ANTHROPIC_API_KEY" not in keys
                and "CLAUDE_CODE_OAUTH_TOKEN" not in keys
            )
            ledger = json.loads((evidence / "gateway.json").read_text())
            assert ledger["requests"] == 0
            print(
                json.dumps(
                    {
                        "agent_version": result.stdout.strip(),
                        "launch_env_keys": keys,
                        "provider_key_in_docker_config": False,
                        "agent_mounts": ["/home/benchmark"],
                        "provider_requests": 0,
                        "gateway_loopback_ready": True,
                    },
                    indent=2,
                )
            )
        finally:
            subprocess.run(["docker", "rm", "-f", agent, proxy], capture_output=True)
            proc.wait(timeout=10)


if __name__ == "__main__":
    main()
