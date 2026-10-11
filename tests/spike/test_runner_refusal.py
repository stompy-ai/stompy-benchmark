import json
import sys

from spike import runner


def run_local(monkeypatch, tmp_path, reason=None, terminal=True):
    output = tmp_path / "agent"
    output.mkdir()
    home = output / "home"
    home.mkdir()
    keys = [
        "HOME",
        "CLAUDE_CONFIG_DIR",
        "PATH",
        "LANG",
        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC",
        "PYTHONDONTWRITEBYTECODE",
        "ENABLE_TOOL_SEARCH",
        "API_TIMEOUT_MS",
        "ANTHROPIC_BASE_URL",
        "ANTHROPIC_AUTH_TOKEN",
        "ANTHROPIC_DEFAULT_HAIKU_MODEL",
        "CLAUDE_CODE_SUBAGENT_MODEL",
    ]
    (home / "launch-env-keys.json").write_text(json.dumps(keys))
    event = {
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "total_cost_usd": 0.01,
        "usage": {},
        "num_turns": 1,
    }
    code = "print(" + repr(json.dumps(event)) + ")" if terminal else "pass"
    monkeypatch.setattr(runner.subprocess, "run", lambda *a, **kw: None)
    monkeypatch.setattr(
        runner,
        "gateway_evidence",
        lambda _: {"billing_unknown": False, "refusal_reason": reason},
    )
    return runner._execute_cell(
        [sys.executable, "-c", code],
        tmp_path,
        output,
        home,
        "nomemory",
        "test",
        5,
        None,
        "test",
        runner.time.monotonic(),
    )


def test_gateway_refusal_invalidates_even_success_terminal(monkeypatch, tmp_path):
    row = run_local(monkeypatch, tmp_path, "token ceiling exceeded")
    assert row["outcome"] == "INVALID" and row["score"] is None
    assert row["reason"] == "token ceiling exceeded"
    assert row["cost_usd"] == 0.01


def test_clean_terminal_remains_valid(monkeypatch, tmp_path):
    assert run_local(monkeypatch, tmp_path)["outcome"] == "OK"


def test_unexplained_missing_terminal_keeps_its_reason(monkeypatch, tmp_path):
    row = run_local(monkeypatch, tmp_path, terminal=False)
    assert row["outcome"] == "INVALID" and row["reason"] == "missing terminal result"
