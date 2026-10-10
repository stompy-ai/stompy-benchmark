from types import SimpleNamespace

import pytest

import spike.gateway as runtime
from spike.gateway_budget import Budget


def launched_budget(monkeypatch, tmp_path):
    commands = []

    def launch(command, **kwargs):
        commands.append(command)
        return SimpleNamespace(poll=lambda: None, wait=lambda timeout: 0)

    monkeypatch.setattr(runtime.subprocess, "Popen", launch)
    monkeypatch.setattr(
        runtime.subprocess, "run", lambda *a, **kw: SimpleNamespace(returncode=0)
    )
    monkeypatch.setattr(runtime, "reserve", lambda *a: None)
    with runtime.gateway(tmp_path, 4.5):
        command = commands[0]
        return Budget(float(command[5]), int(command[6]))


def test_cached_history_can_exceed_one_million_tokens_within_dollar_budget(
    monkeypatch, tmp_path
):
    budget = launched_budget(monkeypatch, tmp_path)
    for _ in range(16):
        _, charge, tokens = budget.reserve(70000, 4096)
        budget.settle(
            charge,
            tokens,
            {"input_tokens": 0, "output_tokens": 1, "cache_read_input_tokens": 70000},
        )
    assert budget.tokens > 1000000
    assert budget.charged < budget.ceiling
    assert not budget.unknown


def test_gateway_dollar_reservation_still_refuses_overspend(monkeypatch, tmp_path):
    budget = launched_budget(monkeypatch, tmp_path)
    budget.reserve(700000, 4096)
    with pytest.raises(ValueError, match="budget exhausted"):
        budget.reserve(700000, 4096)
    assert budget.charged <= 4500000
