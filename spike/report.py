"""Raw paired differences for a shadow spike; no significance claims at n=2."""

import json
from pathlib import Path

from spike.integrity import validate_matrix

IDENTITY = "project key, team project on MAIN, owner 51/admin"


def build_report(
    rows: list, *, repeats: int, before: str | None, after: str | None, hashes: dict
) -> dict:
    complete = validate_matrix(rows, repeats)
    stable = bool(before and before == after)
    comparisons = []
    for n in range(1, repeats + 1):
        pair = {
            r["condition"]: r
            for r in rows
            if r.get("repeat") == n and r.get("outcome") in {"OK", "TASK_FAIL"}
        }
        if len(pair) != 2:
            continue
        a, b = pair["stompy"], pair["nomemory"]
        if any(r.get("score") is None or r.get("cost_usd") is None for r in (a, b)):
            continue
        comparisons.append(
            {
                "repeat": n,
                "score_stompy_minus_nomemory": a["score"] - b["score"],
                "cost_stompy_minus_nomemory": round(a["cost_usd"] - b["cost_usd"], 6),
            }
        )
    costs = [r.get("cost_usd") for r in rows]
    cost_complete = (
        all(isinstance(c, (int, float)) for c in costs) and len(costs) == 2 * repeats
    )
    nomemory = [
        r
        for r in rows
        if r.get("condition") == "nomemory" and r.get("outcome") in {"OK", "TASK_FAIL"}
    ]
    saturated = (
        all(
            r.get("score") == r.get("max_score") and r.get("critical_passed") is True
            for r in nomemory
        )
        if len(nomemory) == repeats
        else None
    )
    return {
        "mode": "shadow",
        "outcome": "VALID" if complete and stable else "INCONCLUSIVE",
        "matrix_valid": complete,
        "expected_runs": 2 * repeats,
        "observed_runs": len(rows),
        "server_build_before": before,
        "server_build_after": after,
        "build_stable": stable,
        "fixture_identity": IDENTITY,
        "tenant_limitation": "This proves nothing about routed tenants.",
        "hashes": hashes,
        "runs": rows,
        "paired_deltas": comparisons,
        "nomemory_saturates": saturated,
        "known_agent_cost_usd": round(
            sum(c for c in costs if isinstance(c, (int, float))), 6
        ),
        "agent_cost_complete": cost_complete,
        "cost_limitation": "Missing terminal costs remain unknown. Stompy-side embedding/worker costs are not metered by this spike.",
        "comparison_limitation": "n=2 raw matched-repeat deltas only; no CIs or causal claim. Historical comparisons confound provider/model drift.",
        "reset_limitation": "Full logical fixture compared; archived contexts and parked tickets remain in product history.",
        "grader_limitation": "Tests exercise REST runtime contract and resolver decisions with controlled private storage/tool seams. The three critical authorization checks are path-coupled to resolver internals. The real MCP callable and lifecycle SQL are not executed by these oracles; both-door test quality is not scored. Optional review_after_days/note bounds are outside this spike oracle.",
    }


def write_report(report: dict, output: Path):
    output.mkdir(parents=True, exist_ok=True)
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    lines = [
        "# STOMPY-2699 shadow spike",
        "",
        f"Outcome: **{report['outcome']}**",
        "",
        report["fixture_identity"] + ". " + report["tenant_limitation"],
        "",
        f"Server before: `{report['server_build_before']}`; after: `{report['server_build_after']}`.",
        f"Matrix: {report['observed_runs']}/{report['expected_runs']} rows; valid={report['matrix_valid']}.",
        f"Known agent cost: ${report['known_agent_cost_usd']:.4f}; complete={report['agent_cost_complete']}.",
        "",
        "| Condition | Repeat | Outcome | Score | Cost | Reason |",
        "|---|---:|---|---:|---:|---|",
    ]
    for r in report["runs"]:
        cost = "unknown" if r.get("cost_usd") is None else f"${r['cost_usd']:.4f}"
        lines.append(
            f"| {r['condition']} | {r['repeat']} | {r['outcome']} | {r.get('score')} | {cost} | {r.get('reason') or ''} |"
        )
    lines += [
        "",
        "Paired deltas (Stompy − nomemory):",
        "```json",
        json.dumps(report["paired_deltas"], indent=2),
        "```",
        "",
        f"Nomemory saturates: {report['nomemory_saturates']}",
        "",
        "Hashes:",
        "```json",
        json.dumps(report["hashes"], indent=2),
        "```",
        "",
    ]
    lines.extend(
        report[k]
        for k in (
            "comparison_limitation",
            "cost_limitation",
            "reset_limitation",
            "grader_limitation",
        )
    )
    lines += [
        "",
        "Per-actor MCP tool-call histograms:",
        "```json",
        json.dumps(
            [
                {
                    "condition": r["condition"],
                    "repeat": r["repeat"],
                    "actors": r.get("tool_histograms", {}),
                }
                for r in report["runs"]
            ],
            indent=2,
        ),
        "```",
    ]
    (output / "report.md").write_text("\n".join(lines) + "\n")
