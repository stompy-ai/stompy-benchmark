"""Run one cell in a disposable container; collect lead AND subagent evidence."""

import hashlib
import json
import os
import subprocess
import time
from pathlib import Path

from spike.integrity import assess_run, tool_histograms, verify_delegates
from spike.mcp import STAGING

MODEL = "claude-sonnet-4-6"


def events(path: Path) -> list:
    result = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        result.append(json.loads(line))
    return result


def streams_in(home: Path, lead: Path) -> dict:
    streams = {"lead": events(lead)}
    for path in sorted(home.glob(".claude/projects/**/subagents/agent-*.jsonl")):
        streams[path.stem] = events(path)
    return streams


def prepare_home(home: Path, condition: str, key: str) -> None:
    home.mkdir(parents=True, exist_ok=False)
    (home / ".claude").mkdir()
    config = {"mcpServers": {}}
    if condition == "stompy":
        config["mcpServers"]["stompy"] = {
            "type": "http",
            "url": STAGING + "/mcp",
            "headers": {"Authorization": "Bearer " + key},
        }
    (home / ".mcp.json").write_text(json.dumps(config))
    for path in (home, home / ".claude"):
        path.chmod(0o777)
    (home / ".mcp.json").chmod(0o644)


def run_cell(
    work: Path,
    output: Path,
    condition: str,
    prompt: str,
    *,
    image: str,
    budget: float = 4.5,
    timeout: int = 900,
    kill_after: float | None = None,
) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    provider = {
        k: os.environ[k]
        for k in ("ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN")
        if os.environ.get(k)
    }
    if not provider:
        raise ValueError("Provider authentication missing")
    if len(provider) != 1:
        raise ValueError("Supply one explicit provider credential")
    if any("\n" in v or "\r" in v for v in provider.values()):
        raise ValueError("invalid provider credential")
    home = output / "home"
    prepare_home(home, condition, os.environ.get("STOMPY_BENCHMARK_API_KEY", ""))
    secret = output / "provider.env"
    secret.touch(mode=0o600)
    secret.write_text("".join(f"{k}={v}\n" for k, v in provider.items()))
    # Only the submission and a fresh home are mounted; never the harness,
    # hidden tests, operator home, host sockets, GitHub creds or backend .env.
    for path in [work, *work.rglob("*")]:
        if path.is_symlink():
            continue
        path.chmod(0o777 if path.is_dir() else 0o666)
    name = "bench2699-" + hashlib.sha256(str(output).encode()).hexdigest()[:16]
    command = [
        "docker",
        "run",
        "--rm",
        "--name",
        name,
        "--init",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--memory",
        "4g",
        "--cpus",
        "2",
        "--pids-limit",
        "256",
        "--read-only",
        "--tmpfs",
        "/tmp:rw,nosuid,size=256m",
        "--env-file",
        str(secret.resolve()),
        "-v",
        f"{work.resolve()}:/work",
        "-v",
        f"{home.resolve()}:/home/benchmark",
        image,
        "-p",
        prompt,
        "--model",
        MODEL,
        "--output-format",
        "stream-json",
        "--verbose",
        "--max-budget-usd",
        str(budget),
        "--max-turns",
        "70",
        "--permission-mode",
        "bypassPermissions",
        "--strict-mcp-config",
        "--mcp-config",
        "/home/benchmark/.mcp.json",
        "--setting-sources",
        "project",
    ]
    started = time.monotonic()
    killed = False
    try:
        with (output / "stream.ndjson").open("w") as stdout, (
            output / "stderr.log"
        ).open("w") as stderr:
            process = subprocess.Popen(command, stdout=stdout, stderr=stderr)
            deadline = started + (kill_after if kill_after is not None else timeout)
            while process.poll() is None:
                if time.monotonic() > deadline:
                    subprocess.run(["docker", "kill", name], capture_output=True)
                    killed = True
                    break
                time.sleep(0.25)
            try:
                code = process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                process.kill()
                code = process.wait()
    finally:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True)
        secret.unlink(missing_ok=True)
        (home / ".mcp.json").unlink(missing_ok=True)
    row = {
        "condition": condition,
        "model": MODEL,
        "runtime_image": image,
        "wall_seconds": round(time.monotonic() - started, 2),
        "exit_code": code,
        "deliberately_killed": kill_after is not None,
    }
    try:
        streams = streams_in(home, output / "stream.ndjson")
        row.update(assess_run(streams["lead"], -9 if killed else code))
        row["tool_histograms"] = tool_histograms(streams, condition)
        if not killed:
            row.update(verify_delegates(streams))
        env_keys = json.loads((home / "launch-env-keys.json").read_text())
        allowed = {
            "HOME",
            "CLAUDE_CONFIG_DIR",
            "PATH",
            "LANG",
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC",
            "PYTHONDONTWRITEBYTECODE",
            *provider,
        }
        if set(env_keys) != allowed:
            raise ValueError("unexpected launch environment")
        row["launch_env_keys"] = env_keys
        if condition == "stompy" and not sum(
            c.get("stompy", 0) for c in row["tool_histograms"].values()
        ):
            raise ValueError("memory cell never used the scoped MCP server")
    except (ValueError, OSError, KeyError, TypeError) as error:
        row.update(outcome="INVALID", score=None, reason=str(error))
    # Raw evidence remains local. Redact exact supplied credentials before
    # any artifact can be selected for publication; .mcp.json was removed.
    secrets = [*provider.values(), os.environ.get("STOMPY_BENCHMARK_API_KEY", "")]
    for path in output.rglob("*"):
        if path.is_file() and not path.is_symlink():
            try:
                text = path.read_text()
            except (UnicodeError, OSError):
                continue
            for value in secrets:
                if value:
                    text = text.replace(value, "[REDACTED]")
            path.write_text(text)
    (output / "normalized.json").write_text(json.dumps(row, indent=2) + "\n")
    return row
