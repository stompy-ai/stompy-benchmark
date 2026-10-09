#!/usr/bin/env python3
"""Normalize runner output to a common benchmark result schema.

Reads result.json + scores.json from a run directory and produces
a normalized JSON object that works across runners (Claude Code, OpenCode).

Usage:
    python3 runners/normalize-result.py <run-dir> [--model MODEL] [--condition COND]
"""

import json
import sys
from pathlib import Path


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def cumulative_from_stream(run_dir: Path) -> dict:
    """Swarm runs emit several `result` events; the last holds cumulative cost but
    per-segment usage/turns. Use its modelUsage for tokens and sum turns across events."""
    results = []
    try:
        for line in (run_dir / "result-stream.ndjson").read_text().splitlines():
            if line.startswith("{"):
                ev = json.loads(line)
                if ev.get("type") == "result":
                    results.append(ev)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    if not results:
        return {}
    mu = results[-1].get("modelUsage", {}).values()
    return {
        "usage": {
            "input_tokens": sum(u.get("inputTokens", 0) for u in mu),
            "output_tokens": sum(u.get("outputTokens", 0) for u in mu),
            "cache_read_input_tokens": sum(u.get("cacheReadInputTokens", 0) for u in mu),
            "cache_creation_input_tokens": sum(u.get("cacheCreationInputTokens", 0) for u in mu),
        },
        "num_turns": sum(e.get("num_turns", 0) for e in results),
    }


def normalize_claude_code(result: dict, scores: dict, model: str, condition: str, run_dir: Path | None = None) -> dict:
    """Normalize Claude Code result.json to common schema."""
    if run_dir:
        result = {**result, **cumulative_from_stream(run_dir)}
    usage = result.get("usage", {})
    input_tokens = usage.get("input_tokens", 0)
    output_tokens = usage.get("output_tokens", 0)
    cache_read = usage.get("cache_read_input_tokens", 0)
    cache_creation = usage.get("cache_creation_input_tokens", 0)
    total_tokens = input_tokens + output_tokens + cache_read + cache_creation

    wall_clock = result.get("benchmark_wall_clock_seconds", result.get("duration_ms", 0) / 1000)
    duration_api = result.get("duration_api_ms", 0) / 1000
    cost = result.get("total_cost_usd", 0)
    score = scores.get("total_score", 0)
    max_score = scores.get("total_max", 40)

    return {
        "model": model,
        "provider": "anthropic",
        "runner": "claude-code",
        "condition": condition,
        "score": score,
        "max_score": max_score,
        "tokens": {
            "input": input_tokens,
            "output": output_tokens,
            "cache_read": cache_read,
            "cache_creation": cache_creation,
            "total": total_tokens,
        },
        "cost_usd": round(cost, 4),
        "timing": {
            "wall_clock_seconds": round(wall_clock, 2),
            "api_seconds": round(duration_api, 2),
        },
        "turns": result.get("num_turns", 0),
        "is_error": result.get("is_error", False),
        "session_id": result.get("session_id", ""),
        "efficiency": _calc_efficiency(score, max_score, total_tokens, cost, wall_clock),
    }


def normalize_opencode(result: dict, scores: dict, model: str, condition: str) -> dict:
    """Normalize OpenCode result.json to common schema.

    OpenCode JSON format may differ — this handles known fields and falls back gracefully.
    """
    # OpenCode may use different field names; adapt as the CLI stabilizes
    input_tokens = result.get("input_tokens", result.get("usage", {}).get("input_tokens", 0))
    output_tokens = result.get("output_tokens", result.get("usage", {}).get("output_tokens", 0))
    total_tokens = input_tokens + output_tokens
    wall_clock = result.get("benchmark_wall_clock_seconds", result.get("duration_seconds", 0))
    cost = result.get("cost_usd", result.get("total_cost_usd", 0))
    score = scores.get("total_score", 0)
    max_score = scores.get("total_max", 40)

    # Detect provider from model name
    provider = "unknown"
    if "gpt" in model.lower() or "codex" in model.lower():
        provider = "openai"
    elif "gemini" in model.lower():
        provider = "google"
    elif "claude" in model.lower():
        provider = "anthropic"

    return {
        "model": model,
        "provider": provider,
        "runner": "opencode",
        "condition": condition,
        "score": score,
        "max_score": max_score,
        "tokens": {
            "input": input_tokens,
            "output": output_tokens,
            "cache_read": 0,
            "cache_creation": 0,
            "total": total_tokens,
        },
        "cost_usd": round(cost, 4),
        "timing": {
            "wall_clock_seconds": round(wall_clock, 2),
            "api_seconds": 0,
        },
        "turns": result.get("num_turns", result.get("turns", 0)),
        "is_error": result.get("is_error", False),
        "session_id": result.get("session_id", ""),
        "efficiency": _calc_efficiency(score, max_score, total_tokens, cost, wall_clock),
    }


def _calc_efficiency(score: int, max_score: int, total_tokens: int, cost: float, wall_clock: float) -> dict:
    return {
        "tokens_per_point": round(total_tokens / score, 0) if score > 0 else 0,
        "cost_per_point": round(cost / score, 4) if score > 0 else 0,
        "points_per_minute": round(score / (wall_clock / 60), 4) if wall_clock > 0 else 0,
    }


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 normalize-result.py <run-dir> [--model MODEL] [--condition COND]", file=sys.stderr)
        sys.exit(1)

    run_dir = Path(sys.argv[1])
    model = ""
    condition = ""

    # Parse optional args
    args = sys.argv[2:]
    for i in range(0, len(args) - 1, 2):
        if args[i] == "--model":
            model = args[i + 1]
        elif args[i] == "--condition":
            condition = args[i + 1]

    result = load_json(run_dir / "result.json")
    scores = load_json(run_dir / "scores.json")

    # Auto-detect from result metadata if not provided
    if not model:
        model = result.get("benchmark_model", run_dir.name.split("-", 1)[-1].rsplit("-", 1)[0])
    if not condition:
        condition = result.get("benchmark_condition", "nomemory")

    runner = result.get("benchmark_runner", "claude-code")

    if runner == "opencode":
        normalized = normalize_opencode(result, scores, model, condition)
    else:
        normalized = normalize_claude_code(result, scores, model, condition, run_dir)

    print(json.dumps(normalized, indent=2))


if __name__ == "__main__":
    main()
