"""python -m spike.handover_run --gen NAME --condition stompy|nomemory [--task tasks/handover-meridian] [--model M]

Scenario C (STOMPY-2798): a LEAD agent delivers part one and records the
handover; a FRESH sub-agent (new conversation, new container, same working
tree) delivers part two. Same weak local model in both arms; the only
difference is the channel the handover travels through: Stompy memory or the
repository. DESIGN mode: zero provider cost, never a verdict.
"""

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import time
from pathlib import Path

from spike.design_agent import OLLAMA, Sandbox, metrics, ollama_chat, run_agent
from spike.design_run import IMAGE, LIMITATION
from spike.fixture import fixture_lock, inventory, reset
from spike.grade_node import grade_node
from spike.mcp import MCP
from spike.readiness import wait_ready

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "meridian-base"
IGNORE = shutil.ignore_patterns("node_modules", "dist", ".git")
MEMORY_TOOL_HINT = "stompy_context_search, stompy_recall_context, stompy_ticket_search"
PLACEHOLDERS = {
    ("lead", "stompy"): {
        "HANDOVER_CHANNEL": f"the Stompy memory project, which it can search and recall ({MEMORY_TOOL_HINT})",
        "RECORDING_INSTRUCTION": "use stompy_lock_context for one context per decision plus one handover context with the current state, and stompy_ticket to create a ticket for part two; do not leave notes files in the repository",
    },
    ("lead", "nomemory"): {
        "HANDOVER_CHANNEL": "nothing else",
        "RECORDING_INSTRUCTION": "leave whatever it needs in the repository, for example a HANDOVER.md; there is no memory service",
    },
    ("handover", "stompy"): {
        "MEMORY_INSTRUCTION": f"The lead recorded them in Stompy: search and recall them before acting ({MEMORY_TOOL_HINT}).",
    },
    ("handover", "nomemory"): {
        "MEMORY_INSTRUCTION": "Whatever the lead left is in the repository; there is no memory service.",
    },
}


def render(task: Path, phase: str, condition: str) -> str:
    text = (task / f"prompt-{phase}.md").read_text()
    for key, value in PLACEHOLDERS[(phase, condition)].items():
        text = text.replace("{{" + key + "}}", value)
    if "{{" in text:
        raise ValueError("unrendered placeholder in " + phase)
    return text


def stage_command(work: Path, image: str) -> list:
    # The one networked step: dependencies are installed before any agent runs.
    return ["docker", "run", "--rm", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
            "--memory", "2g", "--pids-limit", "256", "-v", f"{work.resolve()}:/work", "--workdir", "/work",
            "--entrypoint", "bash", image, "-lc", "npm ci --no-audit --no-fund --ignore-scripts=false"]


def stage_node_project(source: Path, work: Path, image: str, runner=subprocess.run):
    shutil.copytree(source, work, ignore=IGNORE)
    for path in [work, *work.rglob("*")]:
        if not path.is_symlink():
            path.chmod(0o777 if path.is_dir() else 0o666)
    done = runner(stage_command(work, image), capture_output=True, text=True)
    (work.parent / "stage.log").write_text((getattr(done, "stdout", "") or "") + (getattr(done, "stderr", "") or ""))
    if getattr(done, "returncode", 0) != 0:
        raise RuntimeError(f"dependency install failed (exit {done.returncode}); see stage.log")


def file_manifest(work: Path) -> dict:
    return {
        str(p.relative_to(work)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(work.rglob("*"))
        if p.is_file() and "node_modules" not in p.parts and "dist" not in p.parts
    }


def result_row(condition, model, lead_events, handover_events, *, grade, wall, memory_after_lead) -> dict:
    decisions = (grade or {}).get("decisions", {})
    row = {
        "mode": "DESIGN", "scenario": "C", "condition": condition, "model": model, "cost_usd": 0.0,
        "wall_seconds": round(wall, 2),
        "phases": {
            "lead": {**metrics(lead_events), "stop_reason": lead_events[-1].get("stop_reason") if lead_events else None},
            "handover": {**metrics(handover_events), "stop_reason": handover_events[-1].get("stop_reason") if handover_events else None},
        },
        "memory_recorded": {
            "contexts": len(memory_after_lead.get("contexts", [])),
            "tickets": len(memory_after_lead.get("tickets", [])),
        },
        "outcome": "UNGRADED", "score": None, "max_score": None,
        "decisions": decisions, "decisions_passed": sum(decisions.values()),
        "limitation": LIMITATION,
    }
    if grade is not None:
        row.update(outcome=grade["outcome"], score=grade["total_score"], max_score=grade["total_max"],
                   checks=grade["checks"], reason=grade.get("reason"))
    return row


def phase(name, cell, work, prompt, args, client):
    folder = cell / name
    folder.mkdir()
    (folder / "prompt.txt").write_text(prompt)
    sandbox = Sandbox(work, IMAGE)  # a fresh container per phase; the sub-agent inherits only /work
    try:
        events = run_agent(
            ollama_chat(args.model, args.ollama), sandbox, work, prompt,
            condition=args.condition, memory=client, max_turns=args.max_turns, timeout=args.timeout,
            log=folder / "stream.ndjson",
        )
    finally:
        sandbox.close()
    (folder / "files.json").write_text(json.dumps(file_manifest(work), indent=2) + "\n")
    return events


def run(args) -> int:
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", args.gen):
        raise ValueError("unsafe generation name")
    if args.condition not in {"stompy", "nomemory"}:
        raise ValueError("condition must be stompy or nomemory")
    task = Path(args.task).resolve()
    cell = Path(args.output).resolve() / args.gen
    cell.mkdir(parents=True, exist_ok=False)
    manifest = json.loads((task / "memory-fixture.json").read_text())
    client = MCP() if args.condition == "stompy" else None
    work = cell / "work"
    started = time.monotonic()
    memory_after_lead, scores = {}, None
    with fixture_lock(Path("/private/tmp/stompy-benchmark-staging.lock")):
        if client is not None:
            reset(client, manifest, cell / "fixture")  # empty project: the lead's records are the memory under test
            wait_ready(client, cell / "ready-before-launch.json")
        stage_node_project(SOURCE, work, IMAGE)
        lead = phase("lead", cell, work, render(task, "lead", args.condition), args, client)
        if client is not None:
            memory_after_lead = inventory(client)
            (cell / "memory-after-lead.json").write_text(json.dumps(memory_after_lead, indent=2) + "\n")
        handover = phase("handover", cell, work, render(task, "handover", args.condition), args, client)
        if args.grade:
            scores = grade_node(work, task, cell / "grade", IMAGE)
        if client is not None:
            (cell / "memory-after-handover.json").write_text(json.dumps(inventory(client), indent=2) + "\n")
    row = result_row(args.condition, args.model, lead, handover, grade=scores,
                     wall=time.monotonic() - started, memory_after_lead=memory_after_lead)
    row["task"] = str(task.relative_to(ROOT)) if task.is_relative_to(ROOT) else str(task)
    (cell / "result.json").write_text(json.dumps(row, indent=2) + "\n")
    print(json.dumps({k: row.get(k) for k in ("mode", "condition", "model", "outcome", "score", "decisions_passed", "memory_recorded")}
                     | {"lead_turns": row["phases"]["lead"]["turns"], "handover_orientation": row["phases"]["handover"]["orientation"]}))
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gen", required=True)
    parser.add_argument("--condition", required=True)
    parser.add_argument("--task", default=str(ROOT / "tasks/handover-meridian"))
    parser.add_argument("--model", default="gemma4:26b")
    parser.add_argument("--ollama", default=OLLAMA)
    parser.add_argument("--output", default="runs/design")
    parser.add_argument("--max-turns", type=int, default=40)
    parser.add_argument("--timeout", type=int, default=3600)
    parser.add_argument("--grade", action="store_true")
    raise SystemExit(run(parser.parse_args()))
