import pytest

from spike.integrity import (
    assess_run,
    clean_environment,
    tool_histograms,
    validate_matrix,
)


def result():
    return {
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "total_cost_usd": 1.0,
        "num_turns": 3,
        "usage": {"input_tokens": 1, "output_tokens": 1},
    }


def test_missing_terminal_is_invalid():
    assert assess_run([], 0)["outcome"] == "INVALID"


def test_killed_cell_is_invalid_even_with_partial_score():
    row = assess_run([result()], -9)
    assert row["outcome"] == "INVALID" and row["score"] is None


def test_missing_cost_is_not_free():
    event = result()
    del event["total_cost_usd"]
    assert assess_run([event], 0)["outcome"] == "INVALID"


def test_success_control():
    assert assess_run([result()], 0)["outcome"] == "OK"


def test_operator_credentials_are_scrubbed():
    env = clean_environment(
        {
            "STOMPY_API_KEY": "secret",
            "GITHUB_TOKEN": "secret",
            "AWS_SECRET_ACCESS_KEY": "secret",
            "PATH": "/evil",
            "HOME": "/operator",
        }
    )
    assert env == {
        "HOME": "/home/benchmark",
        "CLAUDE_CONFIG_DIR": "/home/benchmark/.claude",
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "LANG": "C.UTF-8",
    }


def test_stray_mcp_server_in_teammate_is_invalid():
    stream = [
        {
            "type": "assistant",
            "parent_tool_use_id": "agent-1",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "id": "call-1",
                        "name": "mcp__stompy-direct__recall_context",
                    }
                ]
            },
        }
    ]
    with pytest.raises(ValueError, match="unexpected MCP server"):
        tool_histograms({"lead": stream}, "stompy")


def test_lead_and_teammate_histograms_and_no_double_count():
    event = {
        "type": "assistant",
        "message": {
            "content": [
                {
                    "type": "tool_use",
                    "id": "call-1",
                    "name": "mcp__stompy__recall_context",
                }
            ]
        },
    }
    assert tool_histograms({"lead": [event, event], "teammate-1": []}, "stompy") == {
        "lead": {"stompy": 1},
        "teammate-1": {},
    }


def test_incomplete_and_duplicate_matrices_are_invalid():
    rows = [{"condition": "stompy", "repeat": 1, "outcome": "OK"}]
    assert not validate_matrix(rows, 2)
    assert not validate_matrix(rows * 4, 2)


def test_complete_matrix_control():
    rows = [
        {"condition": c, "repeat": n, "outcome": "OK"}
        for c in ["stompy", "nomemory"]
        for n in [1, 2]
    ]
    assert validate_matrix(rows, 2)
    rows[0]["outcome"] = "INVALID"
    assert not validate_matrix(rows, 2)


def test_each_teammate_requires_its_own_evidence():
    from spike.integrity import verify_delegates

    calls = [
        {
            "type": "assistant",
            "message": {
                "content": [
                    {"type": "tool_use", "id": name, "name": "Agent"}
                    for name in ("call-a", "call-b")
                ]
            },
        }
    ]
    # Two unrelated transcripts cannot substitute for either actual child.
    with pytest.raises(ValueError, match="missing teammate evidence"):
        verify_delegates({"lead": calls, "agent-wrong1": [{}], "agent-wrong2": [{}]})
    calls += [
        {
            "type": "user",
            "message": {"content": [{"type": "tool_result", "tool_use_id": name}]},
            "tool_use_result": {"agentId": child},
        }
        for name, child in [("call-a", "a"), ("call-b", "b")]
    ]
    result = verify_delegates({"lead": calls, "agent-a": [{}], "agent-b": [{}]})
    assert result["delegate_trace_map"] == {"call-a": "agent-a", "call-b": "agent-b"}


def test_nested_teammate_cannot_escape_trace_validation():
    from spike.integrity import verify_delegates

    root = [
        {"parent_tool_use_id": "root-call"},
        {
            "message": {
                "content": [{"type": "tool_use", "id": "root-call", "name": "Agent"}]
            }
        },
    ]
    nested = [
        {
            "message": {
                "content": [{"type": "tool_use", "id": "child-call", "name": "Agent"}]
            }
        }
    ]
    with pytest.raises(ValueError, match="missing teammate evidence: child-call"):
        verify_delegates({"lead": root, "agent-a": nested})


def test_no_delegation_is_observed_task_behavior_not_missing_evidence():
    from spike.integrity import verify_delegates

    assert verify_delegates({"lead": []})["delegated_calls"] == 0
