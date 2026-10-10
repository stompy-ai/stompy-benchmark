import json

import pytest

from spike.readiness import wait_ready


def status(**updates):
    counts = dict(
        pending=0, processing=0, failed=0, dead_letter=0, completed=3, unknown=0
    )
    counts.update(updates)
    return dict(
        project="stompy_benchmark",
        scope="team_main",
        counts=counts,
        ready=not any(v for k, v in counts.items() if k != "completed"),
    )


class Client:
    project = "stompy_benchmark"

    def __init__(self, observations):
        self.observations = iter(observations)
        self.calls = 0

    def call(self, tool, arguments):
        assert (tool, arguments) == ("project_jobs", {"project": self.project})
        self.calls += 1
        return next(self.observations)


def test_delayed_pending_drains_before_two_ready_observations(tmp_path):
    client = Client(
        [status(pending=1), status(), status(processing=1), status(), status()]
    )
    wait_ready(client, tmp_path / "ready.json", sleep=lambda _: None, clock=lambda: 0)
    assert client.calls == 5
    assert len(json.loads((tmp_path / "ready.json").read_text())["observations"]) == 5


@pytest.mark.parametrize("state", ["failed", "dead_letter", "unknown"])
def test_failed_jobs_refuse_immediately(tmp_path, state):
    with pytest.raises(ValueError, match="failed or unknown"):
        wait_ready(Client([status(**{state: 1})]), tmp_path / "ready.json")


@pytest.mark.parametrize(
    "change",
    [
        {"project": "foreign"},
        {"scope": "routed"},
        {"ready": True, "counts": {"pending": 1}},
        {"counts": {**status()["counts"], "pending": -1}},
        {"counts": {**status()["counts"], "pending": True}},
    ],
)
def test_malformed_or_wrong_scope_readiness_refused(tmp_path, change):
    value = {**status(), **change}
    with pytest.raises(ValueError, match="invalid readiness"):
        wait_ready(Client([value]), tmp_path / "ready.json")


def test_pending_timeout_never_launches(tmp_path):
    times = iter([0, 1, 7])
    with pytest.raises(ValueError, match="timed out"):
        wait_ready(
            Client([status(pending=1)] * 2),
            tmp_path / "ready.json",
            timeout=5,
            clock=lambda: next(times),
            sleep=lambda _: None,
        )
