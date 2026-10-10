import json
from types import SimpleNamespace

from spike import run as harness


def setup(monkeypatch, tmp_path):
    real_lock = harness.fixture_lock
    monkeypatch.setattr(
        harness, "fixture_lock", lambda _: real_lock(tmp_path / "fixture.lock")
    )
    monkeypatch.setattr(
        harness.subprocess, "check_output", lambda *a, **k: "sha256:test"
    )
    monkeypatch.setattr(harness, "server_build", lambda: "a" * 40)
    monkeypatch.setattr(
        harness,
        "MCP",
        lambda: SimpleNamespace(preflight=lambda: {"refusal": "INVALID_PROJECT"}),
    )
    monkeypatch.setattr(harness, "snapshot", lambda *a: None)
    monkeypatch.setattr(harness, "reset", lambda *a: {"matched": True})
    monkeypatch.setattr(
        harness,
        "inventory",
        lambda *a: json.loads((harness.TASK / "memory-fixture.json").read_text()),
    )
    return SimpleNamespace(
        gen="test",
        output=tmp_path,
        backend=tmp_path,
        repeats=2,
        budget=4.5,
        kill_control=False,
    )


def test_fixture_drift_prevents_launch(monkeypatch, tmp_path):
    args = setup(monkeypatch, tmp_path)
    data = json.loads((harness.TASK / "memory-fixture.json").read_text())
    data["contexts"][0]["content"] = "drifted"
    monkeypatch.setattr(harness, "inventory", lambda *a: data)
    called = []
    monkeypatch.setattr(harness, "run_cell", lambda *a, **kw: called.append(True))
    assert harness.run(args) == 1
    assert called == []
    report = json.loads((tmp_path / "test/report.json").read_text())
    assert not report["matrix_valid"]
    assert report["runs"][0]["outcome"] == "INVALID"
    assert report["runs"][0]["score"] is None


def test_invalid_cell_exits_nonzero_and_never_grades(monkeypatch, tmp_path):
    args = setup(monkeypatch, tmp_path)
    monkeypatch.setattr(
        harness,
        "run_cell",
        lambda *a, **kw: {
            "outcome": "INVALID",
            "score": None,
            "reason": "process exit -9",
        },
    )
    graded = []
    monkeypatch.setattr(harness, "grade", lambda *a: graded.append(True))
    assert harness.run(args) == 1
    report = json.loads((tmp_path / "test/report.json").read_text())
    assert report["observed_runs"] == 1 and report["expected_runs"] == 4
    assert report["runs"][0]["score"] is None
    assert not graded


def test_really_killed_process_is_invalid_not_zero(monkeypatch, tmp_path):
    """Real SIGKILL + actual report path; synthetic child, not a paid Sonnet cell."""
    import subprocess
    import sys

    from spike.integrity import assess_run

    args = setup(monkeypatch, tmp_path)

    def killed_cell(*a, **kw):
        child = subprocess.Popen(
            [
                sys.executable,
                "-u",
                "-c",
                'import time; print("ready", flush=True); time.sleep(300)',
            ],
            stdout=subprocess.PIPE,
            text=True,
        )
        try:
            assert child.stdout.readline().strip() == "ready"
            child.kill()
            code = child.wait(timeout=5)
            assert code < 0
            row = assess_run([], code)
            row["exit_code"] = code
            row["deliberately_killed"] = True
            return row
        finally:
            if child.poll() is None:
                child.kill()
                child.wait()

    monkeypatch.setattr(harness, "run_cell", killed_cell)
    assert harness.run(args) == 1
    report = json.loads((tmp_path / "test/report.json").read_text())
    row = report["runs"][0]
    assert row["outcome"] == "INVALID"
    assert row["score"] is None and row["cost_usd"] is None
    assert row["exit_code"] < 0
    assert report["observed_runs"] == 1 and report["expected_runs"] == 4
