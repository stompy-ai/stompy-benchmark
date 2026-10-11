#!/usr/bin/env python3
"""Verify a Claude Code stream-json run saw exactly its condition's MCP servers.

Usage: check-isolation.py CONDITION result-stream.ndjson [--write isolation.json]

stompy   -> exactly one server, named "stompy", not failed/needs-auth
nomemory -> no MCP servers at all

Exit 0 = isolated, 1 = violated (or no init event: unreadable is not a pass).
"""
import json
import sys

EXPECTED = {"stompy": {"stompy"}, "nomemory": set()}
BAD_STATUS = {"failed", "needs-auth"}


def init_servers(path):
    with open(path, errors="replace") as f:
        for line in f:
            try:
                obj = json.loads(line)
            except ValueError:
                continue
            if obj.get("type") == "system" and obj.get("subtype") == "init":
                return obj.get("mcp_servers") or []
    return None


def verdict(condition, servers):
    if servers is None:
        return {"ok": False, "reason": "no system/init event in the stream", "servers": []}
    names = {s.get("name") for s in servers}
    want = EXPECTED[condition]
    problems = []
    if names != want:
        problems.append("servers %s != expected %s" % (sorted(names), sorted(want)))
    for s in servers:
        if s.get("name") in want and s.get("status") in BAD_STATUS:
            problems.append("%s is %s" % (s["name"], s["status"]))
    return {
        "ok": not problems,
        "reason": "; ".join(problems) or "isolated",
        "servers": [{"name": s.get("name"), "status": s.get("status")} for s in servers],
    }


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    condition, path = argv[1], argv[2]
    if condition not in EXPECTED:
        print("unknown condition %r" % condition)
        return 2
    result = verdict(condition, init_servers(path))
    result["condition"] = condition
    if "--write" in argv:
        i = argv.index("--write")
        if i + 1 >= len(argv):
            print("--write needs a path")
            return 2
        with open(argv[i + 1], "w") as f:
            json.dump(result, f, indent=2)
    print("  isolation: %s (%s)" % ("OK" if result["ok"] else "VIOLATED", result["reason"]))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
