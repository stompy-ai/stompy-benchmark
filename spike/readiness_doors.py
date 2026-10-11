"""Read-only STOMPY-2711 staging walk; run only after its merge is deployed."""

import argparse
import json
import subprocess
import urllib.request
from pathlib import Path

from spike.mcp import MCP, STAGING, server_build
from spike.readiness import validate
from spike.two_doors import rest


def walk(backend, fix, output):
    before = server_build()
    if subprocess.run(
        ["git", "-C", str(backend), "merge-base", "--is-ancestor", fix, before],
        capture_output=True,
    ).returncode:
        raise ValueError("staging does not contain the readiness merge")
    client = MCP()
    request = urllib.request.Request(
        STAGING + "/api/v1/projects/stompy_benchmark/jobs",
        headers={"Authorization": "Bearer " + client.key},
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        status, cache = response.status, response.headers.get("Cache-Control")
        rest_value = json.load(response)
    mcp_value = client.call("project_jobs", {"project": client.project})
    foreign_rest, _ = rest(client, "/api/v1/projects/stompy/jobs")
    foreign_mcp = client.call("project_jobs", {"project": "stompy"}, allow_error=True)
    after = server_build()
    evidence = {
        "server_before": before,
        "server_after": after,
        "fix_commit": fix,
        "rest_status": status,
        "cache_control": cache,
        "rest": rest_value,
        "mcp": mcp_value,
        "foreign_rest_status": foreign_rest,
        "foreign_mcp_code": foreign_mcp.get("error"),
        "fixture_identity": "project key, team project on MAIN, owner 51/admin",
        "limitation": "This proves nothing about routed tenants. Observations are not a write lock.",
    }
    try:
        # A failed queue is evidence, never a successful readiness walk.
        validate(rest_value, client.project)
        validate(mcp_value, client.project)
        evidence["passed"] = (
            before == after
            and status == 200
            and cache == "no-store"
            and foreign_rest == 404
            and evidence["foreign_mcp_code"] == "PROJECT_NOT_FOUND"
        )
    except ValueError as error:
        evidence.update(passed=False, reason=str(error))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps(evidence, indent=2))
    return 0 if evidence["passed"] else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", required=True)
    parser.add_argument("--fix", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    raise SystemExit(walk(Path(args.backend), args.fix, Path(args.output)))
