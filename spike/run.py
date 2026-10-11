"""python -m spike.run --gen NAME --backend PATH --output PATH [--kill-control]."""

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

from spike.fixture import assert_fixture, fixture_lock, inventory, reset
from spike.grader import grade
from spike.instructions import VERIFICATION
from spike.invalidation import invalidate
from spike.mcp import MCP, server_build
from spike.readiness import wait_ready
from spike.report import build_report, write_report
from spike.runner import run_cell
from spike.snapshot import snapshot

ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "tasks/lifecycle-rest"


def hash_files(paths):
    digest = hashlib.sha256()
    for path in sorted(p for p in paths if p.is_file()):
        digest.update(str(path.relative_to(ROOT)).encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def run(args) -> int:
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", args.gen):
        raise ValueError("unsafe generation name")
    if args.repeats != 2:
        raise ValueError("this spike fixes n=2")
    if args.budget > 4.5 or args.budget <= 0:
        raise ValueError("cell ceiling is $4.50 (4 cells, $18 max)")
    output = Path(args.output).resolve() / args.gen
    output.mkdir(parents=True, exist_ok=False)
    rows = []
    before = after = None
    hashes = {
        "prompt": hash_files([TASK / "prompt.md"]),
        "fixture": hash_files([TASK / "memory-fixture.json"]),
        "scorer": hash_files(
            [ROOT / "spike/grader.py", *list((TASK / "hidden-tests").glob("*"))]
        ),
        "harness": hash_files(list((ROOT / "spike").glob("*.py"))),
        "snapshot_sha": json.loads((TASK / "memory-fixture.json").read_text())[
            "snapshot_sha"
        ],
    }
    image = subprocess.check_output(
        [
            "docker",
            "image",
            "inspect",
            "stompy-2699-agent:spike",
            "--format",
            "{{.Id}}",
        ],
        text=True,
    ).strip()
    manifest = json.loads((TASK / "memory-fixture.json").read_text())
    prompt_template = (TASK / "prompt.md").read_text()
    schedule = [("stompy", 1), ("nomemory", 1), ("nomemory", 2), ("stompy", 2)]
    try:
        # A single host lock covers reset, every cell, grading and final read-back.
        # No distributed/CI lock in this explicitly local spike.
        with fixture_lock(Path("/private/tmp/stompy-benchmark-staging.lock")):
            before = server_build()
            client = MCP()
            preflight = client.preflight()
            (output / "preflight.json").write_text(
                json.dumps(preflight, indent=2) + "\n"
            )
            for condition, n in schedule:
                row = {
                    "condition": condition,
                    "repeat": n,
                    "outcome": "INVALID",
                    "score": None,
                    "cost_usd": None,
                }
                cell = output / f"{condition}-{n}"
                cell.mkdir()
                try:
                    if server_build() != before:
                        raise ValueError("server build drift before cell")
                    receipt = reset(client, manifest, cell / "fixture")
                    snapshot(Path(args.backend), cell / "work")
                    wait_ready(client, cell / "ready-before-launch.json")
                    assert_fixture(manifest, inventory(client))
                    memory = (
                        "Use only the injected stompy MCP server, project stompy_benchmark. Discover and recall this project's working rules and release-gate rules before acting. Treat the canonical fixture as read-only."
                        if condition == "stompy"
                        else "Work from the supplied source and task. No memory service is available."
                    )
                    prompt = (
                        prompt_template.replace("{{MEMORY_INSTRUCTION}}", memory)
                        + VERIFICATION
                    )
                    (cell / "prompt.txt").write_text(prompt)
                    killed = args.kill_control and not rows
                    row.update(
                        run_cell(
                            cell / "work",
                            cell / "agent",
                            condition,
                            prompt,
                            image=image,
                            budget=0.25 if killed else args.budget,
                            kill_after=10 if killed else None,
                        )
                    )
                    row["repeat"] = n
                    row["fixture"] = receipt
                    row["rendered_prompt_sha256"] = hashlib.sha256(
                        prompt.encode()
                    ).hexdigest()
                    if row["outcome"] == "OK":
                        scores = grade(cell / "work", TASK, cell / "grade")
                        row.update(
                            outcome=scores["outcome"],
                            score=scores["total_score"],
                            max_score=scores["total_max"],
                            critical_passed=scores.get("critical_passed"),
                            checks=scores["checks"],
                            reason=scores.get("reason"),
                        )
                    if (
                        row["outcome"] in {"OK", "TASK_FAIL"}
                        and row.get("delegated_calls") == 0
                    ):
                        row.update(
                            outcome="TASK_FAIL",
                            reason="task requires delegation; lead worked alone",
                        )
                    wait_ready(client, cell / "ready-after-cell.json")
                    post_fixture = inventory(client)
                    (cell / "post-fixture.json").write_text(
                        json.dumps(post_fixture, indent=2) + "\n"
                    )
                    assert_fixture(manifest, post_fixture)
                    if server_build() != before:
                        invalidate(row, "server build drift after cell")
                except Exception as error:
                    invalidate(row, f"{type(error).__name__}: {error}")
                rows.append(row)
                (cell / "result.json").write_text(json.dumps(row, indent=2) + "\n")
                if row["outcome"] == "INVALID":
                    break  # bounded: no automatic retries
            after = server_build()
    except Exception as error:
        (output / "preflight-error.txt").write_text(
            f"{type(error).__name__}: {error}\n"
        )
    report = build_report(rows, repeats=2, before=before, after=after, hashes=hashes)
    report["runtime_image"] = image
    report["retry_limit"] = 0
    report["reserved_agent_budget_usd"] = 0.25 if args.kill_control else 18
    write_report(report, output)
    print(
        json.dumps(
            {
                "output": str(output),
                "outcome": report["outcome"],
                "rows": len(rows),
                "cost": report["known_agent_cost_usd"],
            }
        )
    )
    return 0 if report["outcome"] == "VALID" else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gen", required=True)
    parser.add_argument("--backend", required=True)
    parser.add_argument("--output", default="runs/spike")
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--budget", type=float, default=4.5)
    parser.add_argument("--kill-control", action="store_true")
    raise SystemExit(run(parser.parse_args()))
