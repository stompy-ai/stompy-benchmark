"""STOMPY-2798 scenario C: lead -> fresh sub-agent handover on meridian-base, DESIGN mode."""

import json
import re
from pathlib import Path

import pytest

from spike import design_agent, grader, grade_node, handover_run

ROOT = Path(__file__).resolve().parents[2]
TASK = ROOT / "tasks/handover-meridian"

JUNIT = """<?xml version="1.0" encoding="UTF-8" ?>
<testsuites name="vitest tests" tests="3" failures="1" errors="0" time="1">
  <testsuite name="tests/handover.test.ts" tests="3" failures="1" errors="0" skipped="0">
    <testcase classname="tests/handover.test.ts" name="hubs_list_is_seeded" time="0.1"/>
    <testcase classname="tests/handover.test.ts" name="decision_events_newest_first" time="0.1">
      <failure message="expected IN_TRANSIT">AssertionError</failure>
    </testcase>
    <testcase classname="tests/handover.test.ts" name="decision_limit_above_100_is_rejected" time="0.1"/>
  </testsuite>
</testsuites>
"""
EXPECTED = {
    "hubs_list_is_seeded": {"critical": False, "decision": False},
    "decision_events_newest_first": {"critical": False, "decision": True},
    "decision_limit_above_100_is_rejected": {"critical": False, "decision": True},
}


def test_vitest_and_tsc_count_as_productive():
    for cmd in ("npx vitest run", "npm test", "npx tsc --noEmit"):
        events = [
            {"type": "assistant", "turn": 1, "t": 2.0, "usage": {"prompt_eval_count": 5, "eval_count": 1},
             "tool_calls": [{"id": "a", "name": "bash", "arguments": {"cmd": cmd}}]},
            {"type": "result", "turns": 1, "stop_reason": "done"},
        ]
        assert design_agent.metrics(events)["orientation"] == {"turns": 1, "prompt_tokens": 5, "seconds": 2.0}, cmd


def test_parse_grade_accepts_task_expected_table_with_decisions(tmp_path):
    xml = tmp_path / "junit.xml"
    xml.write_text(JUNIT)
    result = grader.parse_grade(xml, 1, EXPECTED)
    assert result["outcome"] == "TASK_FAIL"
    assert result["total_score"] == 2 and result["total_max"] == 3
    assert result["decisions"] == {"decision_events_newest_first": False, "decision_limit_above_100_is_rejected": True}
    assert result["critical_passed"] is True


def test_parse_grade_default_remains_lifecycle_table(tmp_path):
    assert len(grader.EXPECTED) == 8
    xml = tmp_path / "junit.xml"
    xml.write_text(JUNIT)
    assert grader.parse_grade(xml, 1)["reason"] == "grader test identity set mismatch"


def test_node_grade_command_is_isolated_and_reads_submission_read_only(tmp_path):
    command = grade_node.command(tmp_path / "work", TASK, tmp_path / "evidence", "img:tag", "grade-x")
    joined = " ".join(command)
    assert "--network none" in joined and "--read-only" in joined and "--cap-drop ALL" in joined
    assert f"{(tmp_path / 'work').resolve()}:/submission:ro" in command
    assert f"{(TASK / 'hidden-tests').resolve()}:/oracle:ro" in command
    assert "img:tag" in command
    assert "handover.test.ts" in joined and "--reporter=junit" in joined and "/evidence/junit.xml" in joined


def test_stage_command_installs_dependencies_inside_image(tmp_path):
    command = handover_run.stage_command(tmp_path / "work", "img:tag")
    joined = " ".join(command)
    assert "npm ci" in joined and "img:tag" in command and f"{(tmp_path / 'work').resolve()}:/work" in command
    assert "--network none" not in joined  # the one networked step: dependency install before the agent


def test_stage_node_project_copies_source_without_node_modules(tmp_path):
    source = tmp_path / "src"
    (source / "node_modules" / "x").mkdir(parents=True)
    (source / "src").mkdir()
    (source / "src" / "index.ts").write_text("// a")
    (source / "package.json").write_text("{}")
    calls = []
    work = tmp_path / "work"
    handover_run.stage_node_project(source, work, "img:tag", runner=lambda cmd, **kw: calls.append(cmd))
    assert (work / "src" / "index.ts").read_text() == "// a"
    assert not (work / "node_modules" / "x").exists()
    assert len(calls) == 1 and "npm ci" in " ".join(calls[0])


def test_render_prompts_per_condition():
    lead_s = handover_run.render(TASK, "lead", "stompy")
    lead_n = handover_run.render(TASK, "lead", "nomemory")
    hand_s = handover_run.render(TASK, "handover", "stompy")
    hand_n = handover_run.render(TASK, "handover", "nomemory")
    for text in (lead_s, lead_n, hand_s, hand_n):
        assert "{{" not in text
        assert "npx" not in text  # the agent image has node and npm but no npx
    assert "stompy_lock_context" in lead_s and "stompy_lock_context" not in lead_n
    assert "repository" in lead_n and "no memory service" in lead_n
    assert "stompy_context_search" in hand_s and "stompy_" not in hand_n
    # the decisions reach the lead in both arms and never reach the sub-agent prompt
    for text in (lead_s, lead_n):
        assert "NEWEST FIRST" in text
    for text in (hand_s, hand_n):
        assert "NEWEST FIRST" not in text and "limit must be" not in text


def test_result_row_has_two_phases_and_decision_columns():
    lead = [{"type": "assistant", "turn": 1, "t": 1.0, "usage": {"prompt_eval_count": 10, "eval_count": 1},
             "tool_calls": [{"id": "a", "name": "stompy_lock_context", "arguments": {"topic": "d1", "content": "x"}}]},
            {"type": "result", "turns": 1, "stop_reason": "done"}]
    hand = [{"type": "assistant", "turn": 1, "t": 1.0, "usage": {"prompt_eval_count": 20, "eval_count": 2},
             "tool_calls": [{"id": "b", "name": "write_file", "arguments": {"path": "a", "content": ""}}]},
            {"type": "result", "turns": 1, "stop_reason": "done"}]
    grade = {"outcome": "TASK_FAIL", "total_score": 7, "total_max": 10, "checks": [],
             "decisions": {"decision_events_newest_first": True, "decision_limit_above_100_is_rejected": False}}
    row = handover_run.result_row("stompy", "gemma4:26b", lead, hand, grade=grade, wall=9.0,
                                  memory_after_lead={"contexts": [{"label": "d1"}], "tickets": [], "links": []})
    assert row["mode"] == "DESIGN" and row["scenario"] == "C" and row["cost_usd"] == 0.0
    assert row["phases"]["lead"]["memory_calls"] == 1
    assert row["phases"]["handover"]["orientation"]["turns"] == 1
    assert row["decisions"] == grade["decisions"] and row["decisions_passed"] == 1
    assert row["memory_recorded"] == {"contexts": 1, "tickets": 0}
    assert row["score"] == 7 and row["outcome"] == "TASK_FAIL"


def test_task_artifact_names_match_expected_table():
    names = re.findall(r"^test\('([a-z0-9_]+)'", (TASK / "hidden-tests/handover.test.ts").read_text(), re.M)
    expected = json.loads((TASK / "hidden-tests/expected.json").read_text())
    assert names and set(names) == set(expected)
    assert sum(e["decision"] for e in expected.values()) == 3
    assert (TASK / "memory-fixture.json").exists() and json.loads((TASK / "memory-fixture.json").read_text())["contexts"] == []
