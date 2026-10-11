"""Pinned CLI local-refusal probe. Docker network NONE, no provider credential."""

import json
import subprocess
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AGENT = "sha256:d3076000923661ae5c3c0717661bff837e6ae42ff68f44e4137dda698e17ba48"
PYTHON = "sha256:3ad37ccd1797321f4bda14f483941a4f7a2b9eca454847b22652e59f5baab8c9"


def main() -> None:
    name = "2736-refusal-" + str(time.time_ns())
    with tempfile.TemporaryDirectory(prefix="2736-cli-") as tmp:
        root = Path(tmp)
        home = root / "home"
        home.mkdir()
        home.chmod(0o777)
        (home / ".mcp.json").write_text('{"mcpServers":{}}')
        evidence = root / "evidence"
        evidence.mkdir()
        try:
            subprocess.run(
                [
                    "docker",
                    "run",
                    "-d",
                    "--rm",
                    "--name",
                    name,
                    "--network",
                    "none",
                    "--read-only",
                    "--cap-drop",
                    "ALL",
                    "-v",
                    str(ROOT / "spike") + ":/gateway:ro",
                    "-v",
                    str(ROOT / "scripts/red/fixtures/budget_probe.py")
                    + ":/probe.py:ro",
                    "-v",
                    str(evidence) + ":/evidence",
                    "--entrypoint",
                    "python",
                    PYTHON,
                    "/probe.py",
                ],
                check=True,
                capture_output=True,
            )
            for _ in range(40):
                if (evidence / "gateway.json").exists():
                    break
                time.sleep(0.25)
            else:
                raise AssertionError("probe not ready")
            result = subprocess.run(
                [
                    "docker",
                    "run",
                    "--rm",
                    "--name",
                    name + "-agent",
                    "--network",
                    "container:" + name,
                    "--read-only",
                    "--cap-drop",
                    "ALL",
                    "--tmpfs",
                    "/tmp:rw,size=64m",
                    "-v",
                    str(home) + ":/home/benchmark",
                    "-e",
                    "ANTHROPIC_BASE_URL=http://127.0.0.1:18777",
                    "-e",
                    "ANTHROPIC_AUTH_TOKEN=local-gateway-only",
                    "-e",
                    "ANTHROPIC_DEFAULT_HAIKU_MODEL=claude-sonnet-4-6",
                    "-e",
                    "CLAUDE_CODE_SUBAGENT_MODEL=claude-sonnet-4-6",
                    AGENT,
                    "-p",
                    "Reply with OK.",
                    "--model",
                    "claude-sonnet-4-6",
                    "--output-format",
                    "stream-json",
                    "--verbose",
                    "--strict-mcp-config",
                    "--mcp-config",
                    "/home/benchmark/.mcp.json",
                    "--setting-sources",
                    "project",
                    "--max-turns",
                    "1",
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
            calls = json.loads((evidence / "calls.json").read_text())
            audit = json.loads((evidence / "gateway.json").read_text())
            assert result.returncode == 1, (result.returncode, result.stderr)
            assert (
                calls["message_attempts"] == 1 and calls["provider_calls"] == 0
            ), calls
            assert calls["attempts"][0]["retry_count"] == "0"
            assert audit["refusal_reason"] == "dollar budget exhausted"
            assert (
                audit["accepted_requests"] == 0
                and audit["charged_upper_bound_usd"] == 0
            )
            events = [
                json.loads(line) for line in result.stdout.splitlines() if line.strip()
            ]
            assert any(e.get("claude_code_version") == "2.1.296" for e in events)
            assert (
                events[-1]["api_error_status"] == 402 and events[-1]["is_error"] is True
            )
            print(
                json.dumps(
                    {
                        "cli_version": "2.1.296",
                        "agent_image": AGENT,
                        "exit_code": result.returncode,
                        **calls,
                        "http_status": 402,
                        "code": "local_budget_refusal",
                        "refusal_reason": audit["refusal_reason"],
                        "network": "none",
                        "credentials": "none",
                    },
                    indent=2,
                )
            )
        finally:
            subprocess.run(
                ["docker", "rm", "-f", name + "-agent", name], capture_output=True
            )


if __name__ == "__main__":
    main()
