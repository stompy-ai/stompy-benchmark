"""Read-only staging acceptance walk, gated on the deployed 2704 commit."""

import argparse
import json
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

from spike.mcp import MCP, STAGING, server_build

FIX = "e6524c64b701de1fbe2699a3b314fa0e78beccd8"


def rest(client, path):
    req = urllib.request.Request(
        STAGING + path, headers={"Authorization": "Bearer " + client.key}
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        return error.code, {}  # Never publish arbitrary error bodies/credentials.


def walk(backend, reset_run, output):
    before = server_build()
    if subprocess.run(
        ["git", "-C", str(backend), "merge-base", "--is-ancestor", FIX, before],
        capture_output=True,
    ).returncode:
        raise ValueError("staging does not yet prove it contains #1277")
    client = MCP()
    # Project-key guard deliberately excludes the profile route. A future policy
    # change needs an explicit probe update, not a silent identity assumption.
    identity_code, identity = rest(client, "/api/v1/auth/me")
    rest_code, contexts = rest(client, "/api/v1/projects/stompy_benchmark/contexts")
    foreign_code, _ = rest(client, "/api/v1/projects/stompy/contexts")
    project = client.call("project_info", {"name": client.project})
    database = client.query(
        "SELECT current_database() AS database, current_schema() AS schema"
    )
    negative = client.preflight()
    after = server_build()
    evidence = {
        "server_before": before,
        "server_after": after,
        "fix_commit": FIX,
        "reset_workflow_run": reset_run,
        "rest_contexts_status": rest_code,
        "rest_foreign_status": foreign_code,
        "identity_status": identity_code,
        "identity": {
            k: identity.get(k)
            for k in ("user_id", "auth_type", "tier", "region", "region_confirmed")
        },
        "mcp_project": project,
        "database": database,
        "negative_preflight": negative,
        "fixture_identity": "project key, team project on MAIN, owner 51/admin",
        "principal_note": "auth/me is intentionally forbidden to project keys. Owner 51 is observed in MCP members; auth_type=project_api_key and beta tier clamp are derived from the deployed server_hosted.py authentication path, not exposed by auth/me. The configured key label is benchmark-harness; REST user_id would be that label plus (api key).",
        "identity_evidence": "MCP membership and scoped-door behavior observed; principal fields code-derived",
    }
    evidence["passed"] = (
        before == after
        and rest_code == 200
        and identity_code == 403
        and foreign_code == 404
        and project.get("is_shared") is True
        and project.get("my_role") == "owner"
        and any(
            str(m.get("user_id")) == "51" and m.get("role") == "owner"
            for m in project.get("members", [])
        )
        and database[0]["schema"] == "stompy_benchmark"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: evidence[k]
                for k in (
                    "passed",
                    "server_after",
                    "rest_contexts_status",
                    "rest_foreign_status",
                    "identity",
                    "database",
                )
            }
        )
    )
    return 0 if evidence["passed"] else 1


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--backend", required=True)
    p.add_argument("--reset-run", required=True)
    p.add_argument("--output", required=True)
    a = p.parse_args()
    raise SystemExit(walk(Path(a.backend), a.reset_run, Path(a.output)))
