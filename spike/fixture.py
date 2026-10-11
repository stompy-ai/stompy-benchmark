"""Serialized staging reset and full logical fixture comparison.

Parked/archived tickets are reset residue, not canonical task input. Full
context versions/content and all active graph edges are compared, never counts.
Archival storage is retained by the product and reported as a limitation.
"""

import fcntl
import hashlib
import json
from contextlib import contextmanager
from pathlib import Path

from spike.readiness import wait_ready

CONTEXT_FIELDS = ("label", "version", "content", "priority", "lifecycle")
TICKET_FIELDS = ("title", "description", "status", "type", "priority")
QUERIES = {
    "contexts": "SELECT label,version,content,priority,lifecycle FROM context_locks ORDER BY label,version",
    "links": "SELECT source_label,target_label,link_type,provenance,rationale,grounding FROM context_edges ORDER BY source_label,target_label,link_type",
    "tickets": "SELECT id,title,description,status,type,priority,archived_at FROM tickets ORDER BY id",
}


@contextmanager
def fixture_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError("fixture is already locked") from None
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def inventory(client) -> dict:
    result = {}
    for name, query in QUERIES.items():
        # Fixed statements; values never interpolate into SQL.
        wrapped = (
            "SELECT COALESCE(json_agg(rows), '[]'::json) AS snapshot FROM ("
            + query
            + " LIMIT 10001) rows"
        )
        rows = client.query(wrapped)
        if len(rows) != 1 or not isinstance(rows[0].get("snapshot"), list):
            raise ValueError("incomplete fixture inventory")
        data = rows[0]["snapshot"]
        if len(data) > 10000:
            raise ValueError("fixture inventory exceeds spike limit")
        result[name] = data
    return result


def canonical(data: dict) -> dict:
    return {
        "contexts": sorted(
            [{k: c[k] for k in CONTEXT_FIELDS} for c in data["contexts"]],
            key=lambda c: (c["label"], c["version"]),
        ),
        "links": sorted(data["links"], key=lambda l: json.dumps(l, sort_keys=True)),
        "tickets": sorted(
            [
                {k: t[k] for k in TICKET_FIELDS}
                for t in data["tickets"]
                if not t.get("archived_at") and t["status"] != "parked"
            ],
            key=lambda t: t["title"],
        ),
    }


def assert_fixture(expected: dict, actual: dict):
    if canonical(expected) != canonical(actual):
        raise ValueError("full fixture read-back differs from committed manifest")


def reset(client, manifest: dict, evidence: Path) -> dict:
    evidence.mkdir(parents=True, exist_ok=False)
    wait_ready(client, evidence / "ready-before-reset.json")
    before = inventory(client)
    (evidence / "before.json").write_text(json.dumps(before, indent=2) + "\n")
    wanted = {c["label"]: c for c in manifest["contexts"]}
    groups = {}
    for row in before["contexts"]:
        groups.setdefault(row["label"], []).append(row)
    for label, rows in groups.items():
        expected = wanted.get(label)
        if expected is None or [{k: r[k] for k in CONTEXT_FIELDS} for r in rows] != [
            {k: expected[k] for k in CONTEXT_FIELDS}
        ]:
            client.call(
                "unlock_context",
                {
                    "project": client.project,
                    "topic": label,
                    "version": "all",
                    "force": True,
                    "archive": True,
                },
            )
            if any(c["label"] == label for c in inventory(client)["contexts"]):
                raise ValueError("context archive failed read-back")
    existing = {c["label"] for c in inventory(client)["contexts"]}
    for label, context in wanted.items():
        if label not in existing:
            client.call(
                "lock_context",
                {
                    "project": client.project,
                    "topic": label,
                    "content": context["content"],
                    "priority": context["priority"],
                    "force_store": True,
                    "lazy": True,
                },
            )
            rows = [c for c in inventory(client)["contexts"] if c["label"] == label]
            if [{k: r[k] for k in CONTEXT_FIELDS} for r in rows] != [
                {k: context[k] for k in CONTEXT_FIELDS}
            ]:
                (evidence / "replay-mismatch.json").write_text(
                    json.dumps({"actual": rows, "expected": context}, indent=2) + "\n"
                )
                raise ValueError("context replay failed full read-back")
    desired = {t["title"]: t for t in manifest["tickets"]}
    current = inventory(client)["tickets"]
    for ticket in current:
        if (
            ticket["title"] not in desired
            and not ticket["archived_at"]
            and ticket["status"] != "parked"
        ):
            client.call(
                "ticket",
                {
                    "project": client.project,
                    "action": "move",
                    "ticket_id": ticket["id"],
                    "status": "parked",
                    "reason": "Benchmark reset: absent from committed fixture",
                    "revisit_by": "2027-01-01",
                },
            )
            row = next(
                t for t in inventory(client)["tickets"] if t["id"] == ticket["id"]
            )
            if row["status"] != "parked":
                raise ValueError("ticket parking failed read-back")
    for title, ticket in desired.items():
        matches = [t for t in current if t["title"] == title]
        if len(matches) > 1:
            raise ValueError("duplicate fixture ticket identity")
        if not matches:
            client.call(
                "ticket",
                {
                    "project": client.project,
                    "action": "create",
                    "title": title,
                    "description": ticket["description"],
                    "type": ticket["type"],
                    "priority": ticket["priority"],
                },
            )
            matches = [t for t in inventory(client)["tickets"] if t["title"] == title]
        if len(matches) != 1:
            raise ValueError("ticket create failed read-back")
        row = matches[0]

        def read_ticket():
            return next(t for t in inventory(client)["tickets"] if t["id"] == row["id"])

        if row["archived_at"]:
            client.call(
                "ticket",
                {
                    "project": client.project,
                    "action": "unarchive",
                    "ticket_id": row["id"],
                },
            )
            row = read_ticket()
            if row["archived_at"]:
                raise ValueError("ticket unarchive failed read-back")
        if (
            row["description"] != ticket["description"]
            or row["priority"] != ticket["priority"]
        ):
            client.call(
                "ticket",
                {
                    "project": client.project,
                    "action": "update",
                    "ticket_id": row["id"],
                    "description": ticket["description"],
                    "priority": ticket["priority"],
                },
            )
            row = read_ticket()
            if any(row[k] != ticket[k] for k in ("description", "priority")):
                raise ValueError("ticket update failed read-back")
        if row["status"] != ticket["status"]:
            client.call(
                "ticket",
                {
                    "project": client.project,
                    "action": "move",
                    "ticket_id": row["id"],
                    "status": ticket["status"],
                },
            )
            row = read_ticket()
            if row["status"] != ticket["status"]:
                raise ValueError("ticket move failed read-back")
    # No scoped context-unlink tool exists. Raw db_execute is admin-only,
    # including for admin-owned project keys. Archive/replay each offending
    # source once through the native door; its delete path purges owned edges.
    # Missing committed derived edges also need source replay; the worker gate
    # waits for extraction before the final diff. Never silently adopt its output.
    current_edges = inventory(client)["links"]
    expected_edges = canonical(manifest)["links"]
    changed_edges = [edge for edge in current_edges if edge not in expected_edges]
    changed_edges += [edge for edge in expected_edges if edge not in current_edges]
    for label in sorted({edge["source_label"] for edge in changed_edges}):
        if label not in wanted:
            raise ValueError("orphan graph edge cannot be reset by the project key")
        client.call(
            "unlock_context",
            {
                "project": client.project,
                "topic": label,
                "version": "all",
                "force": True,
                "archive": True,
            },
        )
        gone = inventory(client)
        if any(c["label"] == label for c in gone["contexts"]) or any(
            e["source_label"] == label for e in gone["links"]
        ):
            raise ValueError("graph source archive failed read-back")
        context = wanted[label]
        client.call(
            "lock_context",
            {
                "project": client.project,
                "topic": label,
                "content": context["content"],
                "priority": context["priority"],
                "force_store": True,
                "lazy": True,
            },
        )
        rows = [c for c in inventory(client)["contexts"] if c["label"] == label]
        if [{k: r[k] for k in CONTEXT_FIELDS} for r in rows] != [
            {k: context[k] for k in CONTEXT_FIELDS}
        ]:
            raise ValueError("graph source replay failed full read-back")
    wait_ready(client, evidence / "ready-after-replay.json")
    after = inventory(client)
    (evidence / "read-back.json").write_text(json.dumps(after, indent=2) + "\n")
    (evidence / "expected.json").write_text(
        json.dumps(canonical(manifest), indent=2) + "\n"
    )
    assert_fixture(manifest, after)
    receipt = {
        "matched": True,
        "contexts": len(after["contexts"]),
        "links": len(after["links"]),
        "tickets": len(canonical(after)["tickets"]),
        "parked_or_archived_tickets": len(after["tickets"])
        - len(canonical(after)["tickets"]),
        "sha256": hashlib.sha256(
            json.dumps(canonical(after), sort_keys=True).encode()
        ).hexdigest(),
        "archive_limitation": "Archived contexts and parked tickets are retained; this is a logical reset, not physical deletion.",
    }
    (evidence / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt
