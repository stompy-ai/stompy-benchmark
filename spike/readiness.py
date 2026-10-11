"""Bounded project-key worker readiness gate (STOMPY-2711).

Two zero observations are a stability check, not a distributed write lock.
Every observation includes delayed jobs; failed/unknown states never pass.
"""

import json
import time

STATES = {"pending", "processing", "failed", "dead_letter", "completed", "unknown"}


def validate(value, project):
    counts = value.get("counts") if isinstance(value, dict) else None
    if (
        not isinstance(counts, dict)
        or set(counts) != STATES
        or any(type(n) is not int or n < 0 for n in counts.values())
        or value.get("project") != project
        or value.get("scope") != "team_main"
        or type(value.get("ready")) is not bool
        or value["ready"] != (not any(n for k, n in counts.items() if k != "completed"))
    ):
        raise ValueError("invalid readiness response or project scope")
    if any(counts[k] for k in ("failed", "dead_letter", "unknown")):
        raise ValueError("fixture has failed or unknown worker jobs")
    return value["ready"]


def wait_ready(client, evidence, *, timeout=600, interval=5, clock=None, sleep=None):
    clock = clock or time.monotonic
    sleep = sleep or time.sleep
    deadline = clock() + timeout
    observations = []
    consecutive = 0
    try:
        while True:
            value = client.call("project_jobs", {"project": client.project})
            observations.append(value)
            consecutive = consecutive + 1 if validate(value, client.project) else 0
            if clock() >= deadline:
                raise ValueError("fixture worker readiness timed out")
            if consecutive == 2:
                return value
            sleep(interval)
    finally:
        evidence.parent.mkdir(parents=True, exist_ok=True)
        evidence.write_text(json.dumps({"observations": observations}, indent=2) + "\n")
