"""python -m spike.design_run --gen NAME --condition stompy|nomemory --backend PATH [--task DIR] [--model M] [--grade] [--no-fixture]

Design-loop cell (STOMPY-2800). Same task artifact, fixture reset, MCP
injection, snapshot and grader as the verdict harness; a cheap local model
instead of the pinned Claude Code agent. Zero provider cost, no ledger entry,
no gateway. Every row is mode DESIGN and must never be read as a verdict.
"""

import argparse
import hashlib
import json
import re
import time
from pathlib import Path

from spike.design_agent import OLLAMA, Sandbox, metrics, ollama_chat, run_agent
from spike.fixture import assert_fixture, fixture_lock, inventory, reset
from spike.grader import grade
from spike.instructions import VERIFICATION
from spike.mcp import MCP
from spike.readiness import wait_ready
from spike.snapshot import snapshot

ROOT = Path(__file__).resolve().parents[1]
IMAGE = "stompy-2699-agent:spike"
LIMITATION = (
    "DESIGN mode: a cheap local model drove the task to test the benchmark's own "
    "sensitivity. Not a verdict about Claude or about Stompy; never compare with paid rows."
)
MEMORY_INSTRUCTION = {
    "stompy": "Use only the injected stompy memory tools, project stompy_benchmark. Discover and recall this project's working rules and release-gate rules before acting. Treat the canonical fixture as read-only.",
    "nomemory": "Work from the supplied source and task. No memory service is available.",
}


def result_row(condition: str, model: str, events: list, *, grade: dict | None, wall: float) -> dict:
    row = {
        "mode": "DESIGN",
        "condition": condition,
        "model": model,
        "cost_usd": 0.0,
        "wall_seconds": round(wall, 2),
        "stop_reason": events[-1].get("stop_reason") if events else None,
        "outcome": "UNGRADED",
        "score": None,
        "limitation": LIMITATION,
        **metrics(events),
    }
    if grade is not None:
        row.update(
            outcome=grade["outcome"],
            score=grade["total_score"],
            max_score=grade["total_max"],
            critical_passed=grade.get("critical_passed"),
            checks=grade["checks"],
            reason=grade.get("reason"),
        )
    return row


def run(args) -> int:
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", args.gen):
        raise ValueError("unsafe generation name")
    if args.condition not in MEMORY_INSTRUCTION:
        raise ValueError("condition must be stompy or nomemory")
    task = Path(args.task).resolve()
    cell = Path(args.output).resolve() / args.gen
    cell.mkdir(parents=True, exist_ok=False)
    manifest = json.loads((task / "memory-fixture.json").read_text())
    prompt = (task / "prompt.md").read_text().replace(
        "{{MEMORY_INSTRUCTION}}", MEMORY_INSTRUCTION[args.condition]
    ) + VERIFICATION
    (cell / "prompt.txt").write_text(prompt)
    use_fixture = args.condition == "stompy" and not args.no_fixture
    client = MCP() if args.condition == "stompy" else None
    work = cell / "work"
    started = time.monotonic()
    row, scores = None, None
    with fixture_lock(Path("/private/tmp/stompy-benchmark-staging.lock")):
        if use_fixture:
            reset(client, manifest, cell / "fixture")
            wait_ready(client, cell / "ready-before-launch.json")
            assert_fixture(manifest, inventory(client))
        snapshot(Path(args.backend), work)
        for path in [work, *work.rglob("*")]:
            if not path.is_symlink():
                path.chmod(0o777 if path.is_dir() else 0o666)
        sandbox = Sandbox(work, IMAGE)
        try:
            events = run_agent(
                ollama_chat(args.model, args.ollama), sandbox, work, prompt,
                condition=args.condition, memory=client, max_turns=args.max_turns,
                timeout=args.timeout, log=cell / "stream.ndjson",
            )
        finally:
            sandbox.close()
        if args.grade and (task / "hidden-tests").is_dir():
            scores = grade(work, task, cell / "grade")
        if use_fixture:
            post = inventory(client)
            (cell / "post-fixture.json").write_text(json.dumps(post, indent=2) + "\n")
            try:
                assert_fixture(manifest, post)
            except ValueError as error:
                scores = {**(scores or {"total_score": None, "total_max": None, "checks": []}),
                          "outcome": "INVALID", "reason": str(error)}
    row = result_row(args.condition, args.model, events, grade=scores, wall=time.monotonic() - started)
    row["rendered_prompt_sha256"] = hashlib.sha256(prompt.encode()).hexdigest()
    row["task"] = str(task.relative_to(ROOT)) if task.is_relative_to(ROOT) else str(task)
    (cell / "result.json").write_text(json.dumps(row, indent=2) + "\n")
    print(json.dumps({k: row.get(k) for k in ("mode", "condition", "model", "outcome", "score",
                                             "turns", "memory_calls", "orientation", "stop_reason")}))
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gen", required=True)
    parser.add_argument("--condition", required=True)
    parser.add_argument("--backend", required=True)
    parser.add_argument("--task", default=str(ROOT / "tasks/lifecycle-rest"))
    parser.add_argument("--model", default="gemma4:26b")
    parser.add_argument("--ollama", default=OLLAMA)
    parser.add_argument("--output", default="runs/design")
    parser.add_argument("--max-turns", type=int, default=40)
    parser.add_argument("--timeout", type=int, default=3600)
    parser.add_argument("--grade", action="store_true")
    parser.add_argument("--no-fixture", action="store_true")
    raise SystemExit(run(parser.parse_args()))
