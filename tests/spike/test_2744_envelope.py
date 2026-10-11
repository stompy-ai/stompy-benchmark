import inspect
import json
import subprocess
import sys

import pytest

from spike import run as harness, runner
from spike.gateway_budget import Budget
from spike.spend import reserve
from test_orchestration import setup
from test_gateway_server import proxy


def test_focused_verification_identical_for_both_arms(monkeypatch, tmp_path):
    args = setup(monkeypatch, tmp_path)
    prompts = []

    def cell(work, output, condition, prompt, **kw):
        prompts.append((condition, prompt))
        return {"outcome": "OK", "delegated_calls": 1, "cost_usd": 0.01}

    monkeypatch.setattr(harness, "run_cell", cell)
    monkeypatch.setattr(
        harness,
        "grade",
        lambda *a: {
            "outcome": "OK",
            "total_score": 5,
            "total_max": 5,
            "critical_passed": True,
            "checks": [],
        },
    )
    assert harness.run(args) == 0
    marker = "Focused verification (both conditions):"
    assert all(marker in p for _, p in prompts)
    instructions = [p.split(marker)[1] for _, p in prompts]
    assert len(set(instructions)) == 1
    assert "tests/unit/test_lifecycle_changelog.py" in instructions[0]
    assert "tests/unit/test_set_lifecycle_did_you_mean_1879.py" in instructions[0]
    assert "Do not run the full suite" in instructions[0]
    assert "hidden" not in instructions[0].lower()
    assert "test_critical_" not in instructions[0]
    assert prompts[0][0] == "stompy"


def test_timeout_backstop_is_1800_and_cell_dollars_unchanged():
    params = inspect.signature(runner.run_cell).parameters
    assert params["timeout"].default == 1800
    assert params["budget"].default == 4.5


def test_thirty_dollar_top_up_preserves_all_prior_attempts(tmp_path):
    p = tmp_path / "ledger.json"
    prior = {
        "historical": {"upper_bound_usd": 9.216615, "state": "settled_upper_bound"}
    }
    p.write_text(json.dumps(prior))
    for n in range(4):
        reserve(str(n), 4.5, p)
    assert json.loads(p.read_text())["historical"] == prior["historical"]
    with pytest.raises(ValueError, match="ceiling"):
        reserve("over", 3, p)


def test_budget_owns_an_isolated_cache_forecast():
    a, b = Budget(4.5, 1000), Budget(4.5, 1000)
    assert getattr(a, "cache_forecast", None) is not None
    assert a.cache_forecast is not b.cache_forecast


def test_known_token_breach_is_not_unknown_billing():
    b = Budget(1, 11)
    _, r, t = b.reserve(10, 1)
    b.settle(r, t, {"input_tokens": 12, "output_tokens": 1})
    assert b.unknown is False
    assert b.snapshot().get("refusal_reason") == "token ceiling exceeded"
    assert b.charged == 51 and b.liability == 0
    with pytest.raises(ValueError, match="token ceiling"):
        b.reserve(1, 1)


def test_local_dollar_refusal_is_nonretryable_and_audited(proxy, monkeypatch):
    from spike import gateway_server as server

    post, calls, tmp = proxy
    monkeypatch.setattr(server, "BUDGET", Budget(0.000001, 10000))
    status, body = post({"model": server.MODEL, "messages": [], "max_tokens": 1})
    assert status == 402
    assert body["error"]["code"] == "local_budget_refusal"
    assert body["error"]["message"] == "dollar budget exhausted"
    assert (
        json.loads((tmp / "gateway.json").read_text())["refusal_reason"]
        == "dollar budget exhausted"
    )
    assert not any(p == "/v1/messages" for p, _ in calls)


def test_named_timeout_survives_missing_terminal(monkeypatch, tmp_path):
    output = tmp_path / "agent"
    output.mkdir()
    home = output / "home"
    home.mkdir()
    (home / "launch-env-keys.json").write_text(
        json.dumps(
            [
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
        )
    )
    child = []
    real_popen = subprocess.Popen

    def popen(*args, **kwargs):
        p = real_popen(*args, **kwargs)
        child.append(p)
        return p

    monkeypatch.setattr(runner.subprocess, "Popen", popen)

    def docker(command, **kwargs):
        if command[1] == "kill":
            child[0].kill()

    monkeypatch.setattr(runner.subprocess, "run", docker)
    monkeypatch.setattr(
        runner,
        "gateway_evidence",
        lambda _: {"accepted_requests": 0, "billing_unknown": False},
    )
    row = runner._execute_cell(
        [sys.executable, "-c", "import time; time.sleep(60)"],
        tmp_path,
        output,
        home,
        "nomemory",
        "test",
        0.02,
        None,
        "test",
        runner.time.monotonic(),
    )
    assert row["outcome"] == "INVALID" and row["score"] is None
    assert row["reason"] == "cell timeout (0.02 s)"
    assert row["wall_seconds"] >= 0.02
    assert row["cost_usd"] is None


def test_budget_reason_and_build_drift_both_survive(monkeypatch, tmp_path):
    args = setup(monkeypatch, tmp_path)
    builds = iter(["a" * 40, "a" * 40, "b" * 40, "b" * 40])
    monkeypatch.setattr(harness, "server_build", lambda: next(builds))
    launched = []

    def cell(*a, **kw):
        launched.append(a[2])
        return {
            "outcome": "INVALID",
            "score": None,
            "reason": "dollar budget exhausted",
            "reasons": ["dollar budget exhausted"],
        }

    monkeypatch.setattr(harness, "run_cell", cell)
    monkeypatch.setattr(
        harness, "grade", lambda *a: pytest.fail("invalid submission graded")
    )
    assert harness.run(args) == 1
    row = json.loads((tmp_path / "test/report.json").read_text())["runs"][0]
    assert row.get("reasons") == [
        "dollar budget exhausted",
        "server build drift after cell",
    ]
    assert launched == ["stompy"] and row["score"] is None


def test_unknown_usage_still_stops_without_refund():
    b = Budget(1, 100)
    _, r, t = b.reserve(10, 1)
    b.settle(r, t, None)
    assert b.unknown and b.charged == r
    with pytest.raises(ValueError):
        b.reserve(1, 1)


def test_token_admission_refusal_distinct_from_dollars(proxy, monkeypatch):
    from spike import gateway_server as server

    post, calls, tmp = proxy
    monkeypatch.setattr(server, "BUDGET", Budget(4.5, 10))
    code, body = post({"model": server.MODEL, "messages": [], "max_tokens": 1})
    assert code == 402 and body["error"]["message"] == "token ceiling exceeded"
    assert server.BUDGET.unknown is False
    assert not any(p == "/v1/messages" for p, _ in calls)


def test_report_renders_all_independent_reasons(tmp_path):
    from spike.report import build_report, write_report

    row = {
        "condition": "stompy",
        "repeat": 1,
        "outcome": "INVALID",
        "reason": "cell timeout (1800 s)",
        "reasons": ["dollar budget exhausted", "cell timeout (1800 s)"],
    }
    report = build_report([row], repeats=2, before="a", after="a", hashes={})
    write_report(report, tmp_path)
    text = (tmp_path / "report.md").read_text()
    assert "dollar budget exhausted" in text and "cell timeout (1800 s)" in text
