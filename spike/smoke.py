"""One bounded live isolation smoke; separate from the scored n=2 matrix."""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from spike.fixture import assert_fixture, fixture_lock, inventory, reset
from spike.mcp import MCP, server_build
from spike.run import ROOT, TASK, hash_files
from spike.runner import run_cell

PROMPT = """This is a short MCP isolation smoke, not a coding task.
Use only the injected stompy MCP server, project stompy_benchmark. As lead,
call context_explore on that project. Delegate exactly one Agent/Task teammate
to independently call context_explore on the same project using the same MCP
server and report one topic title. Wait for it to finish, then summarize in
one sentence. Do not write any memory, files, tickets or code. Do not use other
MCP connectors or shell/network substitutes. Keep the work minimal."""


def isolation(row):
    hist = row.get("tool_histograms", {})
    if not hist.get("lead", {}).get("stompy") or not row.get("delegated_calls"):
        return False
    for call, trace in row.get("delegate_trace_map", {}).items():
        if not (hist.get(call, {}).get("stompy") or hist.get(trace, {}).get("stompy")):
            return False
    return all(set(counts) <= {"stompy"} for counts in hist.values())


def smoke(output):
    output.mkdir(parents=True, exist_ok=False)
    row = {"outcome": "INVALID", "score": None, "cost_usd": None}
    before = after = None
    manifest = json.loads((TASK / "memory-fixture.json").read_text())
    try:
        with fixture_lock(Path("/private/tmp/stompy-benchmark-staging.lock")):
            before = server_build()
            client = MCP()
            preflight = client.preflight()
            receipt = reset(client, manifest, output / "fixture")
            work = output / "work"
            work.mkdir()
            assert_fixture(manifest, inventory(client))
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
            row = run_cell(
                work,
                output / "agent",
                "stompy",
                PROMPT,
                image=image,
                budget=1.25,
                timeout=300,
            )
            row["isolation_proven"] = row["outcome"] == "OK" and isolation(row)
            row["preflight"] = preflight
            row["fixture"] = receipt
            post = inventory(client)
            (output / "post-fixture.json").write_text(json.dumps(post, indent=2) + "\n")
            assert_fixture(manifest, post)
            after = server_build()
            if before != after:
                raise ValueError("server build drift")
            if not row["isolation_proven"]:
                raise ValueError(
                    "lead and every teammate must exercise the scoped server"
                )
    except Exception as error:
        row.update(
            outcome="INVALID", score=None, reason=f"{type(error).__name__}: {error}"
        )
        try:
            after = server_build()
        except Exception:
            pass
    report = {
        "kind": "isolation-smoke",
        "reserved_budget_usd": 1.25,
        "server_before": before,
        "server_after": after,
        "fixture_identity": "project key, team project on MAIN, owner 51/admin",
        "tenant_limitation": "This proves nothing about routed tenants.",
        "prompt_sha256": hashlib.sha256(PROMPT.encode()).hexdigest(),
        "fixture_hash": hash_files([TASK / "memory-fixture.json"]),
        "harness_hash": hash_files(list((ROOT / "spike").glob("*.py"))),
        "run": row,
    }
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {
                "output": str(output),
                "outcome": row["outcome"],
                "isolation_proven": row.get("isolation_proven", False),
                "cost": row.get("cost_usd"),
            }
        )
    )
    return 0 if row["outcome"] == "OK" else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    raise SystemExit(smoke(Path(parser.parse_args().output).resolve()))
