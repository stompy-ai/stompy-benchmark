"""STOMPY-2800: design-loop runner drives a task with a cheap model; output is DESIGN, never a verdict."""

import json

import pytest

from spike import design_agent, design_run


def test_tool_schema_exposes_stompy_tools_only_in_memory_arm():
    names = lambda condition: {t["function"]["name"] for t in design_agent.tools(condition)}
    assert {"bash", "read_file", "write_file", "done"} <= names("nomemory")
    assert not any(n.startswith("stompy_") for n in names("nomemory"))
    assert {"stompy_recall_context", "stompy_context_search", "stompy_lock_context"} <= names("stompy")


def test_confine_refuses_paths_outside_work(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    assert design_agent.confine(work, "src/a.py") == work / "src/a.py"
    for bad in ("../etc/passwd", "/etc/passwd", "src/../../x"):
        with pytest.raises(ValueError):
            design_agent.confine(work, bad)


def test_metrics_orientation_is_first_edit_or_test_run():
    events = [
        {"type": "assistant", "turn": 1, "t": 1.0, "usage": {"prompt_eval_count": 100, "eval_count": 10},
         "tool_calls": [{"id": "a", "name": "bash", "arguments": {"cmd": "ls"}}]},
        {"type": "tool_result", "id": "a", "name": "bash"},
        {"type": "assistant", "turn": 2, "t": 2.0, "usage": {"prompt_eval_count": 200, "eval_count": 20},
         "tool_calls": [{"id": "b", "name": "stompy_recall_context", "arguments": {"topic": "x"}}]},
        {"type": "tool_result", "id": "b", "name": "stompy_recall_context"},
        {"type": "assistant", "turn": 3, "t": 5.5, "usage": {"prompt_eval_count": 300, "eval_count": 30},
         "tool_calls": [{"id": "c", "name": "write_file", "arguments": {"path": "src/x.py", "content": ""}}]},
        {"type": "tool_result", "id": "c", "name": "write_file"},
        {"type": "result", "turns": 3, "stop_reason": "done"},
    ]
    m = design_agent.metrics(events)
    assert m["turns"] == 3
    assert m["tokens"] == {"prompt": 600, "completion": 60}
    assert m["tool_histogram"] == {"bash": 1, "stompy_recall_context": 1, "write_file": 1}
    assert m["memory_calls"] == 1
    assert m["orientation"] == {"turns": 3, "prompt_tokens": 600, "seconds": 5.5}


def test_metrics_orientation_none_when_never_productive():
    events = [
        {"type": "assistant", "turn": 1, "t": 1.0, "usage": {"prompt_eval_count": 1, "eval_count": 1},
         "tool_calls": [{"id": "a", "name": "bash", "arguments": {"cmd": "cat README.md"}}]},
        {"type": "result", "turns": 1, "stop_reason": "max_turns"},
    ]
    assert design_agent.metrics(events)["orientation"] is None


def test_pytest_in_bash_counts_as_productive():
    events = [
        {"type": "assistant", "turn": 1, "t": 3.0, "usage": {"prompt_eval_count": 5, "eval_count": 1},
         "tool_calls": [{"id": "a", "name": "bash", "arguments": {"cmd": "python3 -m pytest tests -q"}}]},
        {"type": "result", "turns": 1, "stop_reason": "done"},
    ]
    assert design_agent.metrics(events)["orientation"] == {"turns": 1, "prompt_tokens": 5, "seconds": 3.0}


class FakeSandbox:
    def __init__(self, work):
        self.work = work
        self.commands = []

    def exec(self, cmd, timeout):
        self.commands.append(cmd)
        return 0, "ok\n"


def test_agent_loop_dispatches_tools_and_stops_on_done(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    replies = iter(
        [
            {"message": {"content": "", "tool_calls": [
                {"id": "t1", "function": {"name": "write_file", "arguments": {"path": "a.txt", "content": "hi"}}},
                {"id": "t2", "function": {"name": "bash", "arguments": {"cmd": "ls"}}},
            ]}, "prompt_eval_count": 10, "eval_count": 2},
            {"message": {"content": "finished", "tool_calls": [
                {"id": "t3", "function": {"name": "done", "arguments": {"summary": "wrote a.txt"}}},
            ]}, "prompt_eval_count": 20, "eval_count": 3},
        ]
    )
    chat = lambda messages, tool_schema: next(replies)
    sandbox = FakeSandbox(work)
    events = design_agent.run_agent(
        chat, sandbox, work, "do it", condition="nomemory", memory=None, max_turns=10, timeout=60,
        log=tmp_path / "stream.ndjson",
    )
    assert (work / "a.txt").read_text() == "hi"
    assert sandbox.commands == ["ls"]
    assert events[-1] == {"type": "result", "turns": 2, "stop_reason": "done", "summary": "wrote a.txt"}
    logged = [json.loads(l) for l in (tmp_path / "stream.ndjson").read_text().splitlines()]
    assert logged == events
    assert design_agent.metrics(events)["orientation"]["turns"] == 1


def test_agent_loop_stops_at_max_turns_and_refuses_unknown_tool(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    chat = lambda messages, tool_schema: {
        "message": {"content": "", "tool_calls": [{"id": "x", "function": {"name": "rm_rf", "arguments": {}}}]},
        "prompt_eval_count": 1, "eval_count": 1,
    }
    events = design_agent.run_agent(
        chat, FakeSandbox(work), work, "p", condition="nomemory", memory=None, max_turns=3, timeout=60,
        log=tmp_path / "s.ndjson",
    )
    assert events[-1]["stop_reason"] == "max_turns"
    results = [e for e in events if e["type"] == "tool_result"]
    assert results and all("unknown tool" in r["output"] for r in results)


def test_memory_tools_route_to_mcp_client_with_fixture_project(tmp_path):
    calls = []

    class Client:
        project = "stompy_benchmark"

        def call(self, name, arguments, allow_error=False):
            calls.append((name, arguments))
            return {"result": "ok"}

    out = design_agent.memory_call(Client(), "stompy_recall_context", {"topic": "rules", "project": "stompy"})
    assert calls == [("recall_context", {"topic": "rules", "project": "stompy_benchmark"})]
    assert json.loads(out) == {"result": "ok"}
    with pytest.raises(ValueError):
        design_agent.memory_call(Client(), "stompy_db_execute", {})


def test_result_row_is_design_mode_with_zero_cost():
    events = [{"type": "result", "turns": 0, "stop_reason": "done"}]
    row = design_run.result_row("nomemory", "gemma4:26b", events, grade=None, wall=12.5)
    assert row["mode"] == "DESIGN"
    assert row["cost_usd"] == 0.0
    assert row["model"] == "gemma4:26b"
    assert row["outcome"] == "UNGRADED"
    assert "verdict" in row["limitation"].lower()
    graded = design_run.result_row(
        "stompy", "m", events, grade={"outcome": "TASK_FAIL", "total_score": 3, "total_max": 5, "checks": []}, wall=1
    )
    assert graded["outcome"] == "TASK_FAIL" and graded["score"] == 3
