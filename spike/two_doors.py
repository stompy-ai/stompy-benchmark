"""Read-only staging acceptance walk, gated on the deployed 2704 commit."""

import argparse
import json
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

from spike.mcp import MCP, STAGING, server_build

FIX = "35dee5c3606ae030c3c6e864f0ab5408043f4096"


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
        "principal_note": "Owner tier is admin; project-key principal is clamped to beta. REST user_id is the key label, not the internal owner ID.",
    }
    evidence["passed"] = (
        before == after
        and rest_code == 200
        and identity_code == 200
        and foreign_code == 404
        and identity.get("auth_type") == "project_api_key"
        and identity.get("tier") == "beta"
        and bool(identity.get("user_id"))
        and project.get("is_shared") is True
        and project.get("my_role") == "owner"
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
