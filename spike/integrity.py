"""Run validity is independent of task score."""

import math
from collections import Counter


def clean_environment(source: dict) -> dict:
    # Allowlist from scratch: never inherit the operator's shell, PATH or config.
    return {
        "HOME": "/home/benchmark",
        "CLAUDE_CONFIG_DIR": "/home/benchmark/.claude",
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "LANG": "C.UTF-8",
    }


def assess_run(events: list, exit_code: int) -> dict:
    terminals = [e for e in events if e.get("type") == "result"]
    row = {
        "outcome": "INVALID",
        "score": None,
        "cost_usd": None,
        "reason": "missing terminal result",
    }
    if not terminals:
        return row
    terminal = terminals[-1]
    cost = terminal.get("total_cost_usd")
    if (
        isinstance(cost, (float, int))
        and not isinstance(cost, bool)
        and math.isfinite(cost)
        and cost >= 0
    ):
        row["cost_usd"] = cost
    else:
        row["reason"] = "missing or invalid cost"
        return row
    if exit_code != 0:
        row["reason"] = f"process exit {exit_code}"
        return row
    if terminal.get("is_error") is not False or terminal.get("subtype") != "success":
        row["reason"] = "non-success terminal result"
        return row
    if not isinstance(terminal.get("usage"), dict) or not isinstance(
        terminal.get("num_turns"), int
    ):
        row["reason"] = "missing usage or turns"
        return row
    row.update(
        outcome="OK",
        reason=None,
        turns=sum(e.get("num_turns", 0) for e in terminals),
        usage=terminal["usage"],
    )
    return row


def tool_histograms(streams: dict, condition: str) -> dict:
    hist = {actor: Counter() for actor in streams}
    seen = set()
    for actor, events in streams.items():
        for event in events:
            owner = event.get("parent_tool_use_id") or actor
            hist.setdefault(owner, Counter())
            message = event.get("message", {})
            for block in (
                message.get("content", []) if isinstance(message, dict) else []
            ):
                if not isinstance(block, dict) or block.get("type") != "tool_use":
                    continue
                name = block.get("name", "")
                if not name.startswith("mcp__"):
                    continue
                server = name.split("__", 2)[1]
                if condition != "stompy" or server != "stompy":
                    raise ValueError(f"unexpected MCP server: {server} ({owner})")
                identity = block.get("id")
                if not identity:
                    raise ValueError("missing tool-call identity")
                if identity not in seen:
                    hist[owner][server] += 1
                    seen.add(identity)
    return {actor: dict(counts) for actor, counts in sorted(hist.items())}


def validate_matrix(rows: list, repeats: int) -> bool:
    expected = {(c, n) for c in ("stompy", "nomemory") for n in range(1, repeats + 1)}
    actual = [(r.get("condition"), r.get("repeat")) for r in rows]
    return (
        len(actual) == len(expected)
        and set(actual) == expected
        and all(r.get("outcome") in {"OK", "TASK_FAIL"} for r in rows)
    )


def verify_delegates(streams: dict) -> dict:
    """Every Agent/Task call needs its own identified child trace, recursively."""
    calls = set()
    linked = {}
    parent_events = set()
    for events in streams.values():
        for event in events:
            parent = event.get("parent_tool_use_id")
            if parent:
                parent_events.add(parent)
            content = event.get("message", {}).get("content", [])
            if not isinstance(content, list):
                continue
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "tool_use" and block.get("name") in {
                    "Agent",
                    "Task",
                }:
                    calls.add(block["id"])
                if block.get("type") == "tool_result":
                    result = event.get("tool_use_result")
                    if isinstance(result, dict) and result.get("agentId"):
                        linked[block["tool_use_id"]] = "agent-" + result["agentId"]
    for call in calls:
        if call in parent_events:
            continue
        child = linked.get(call)
        if child not in streams or not streams[child]:
            raise ValueError("missing teammate evidence: " + call)
    return {
        "delegated_calls": len(calls),
        "teammate_transcripts": sorted(k for k in streams if k != "lead"),
        "delegate_trace_map": {
            c: linked.get(c, "parent_tool_use_id:" + c) for c in sorted(calls)
        },
    }
