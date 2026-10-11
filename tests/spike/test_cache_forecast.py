from copy import deepcopy

from spike.gateway_cache import CacheForecast


def body(text="first"):
    return {
        "model": "claude-sonnet-4-6",
        "tools": [],
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": text,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
            }
        ],
    }


def test_only_confirmed_matching_prefix_receives_cache_read_estimate():
    cache = CacheForecast()
    first = body()
    assert cache.estimate(first, 10000)["cache_read_input_tokens"] == 0
    cache.observe(first, {"cache_creation_input_tokens": 9000})
    second = deepcopy(first)
    second["messages"][0]["content"][0].pop("cache_control")
    second["messages"].append(body("next")["messages"][0])
    split = cache.estimate(second, 11000)
    assert split["cache_read_input_tokens"] == 9000
    assert split["cache_creation_input_tokens"] == 2000
    assert (
        cache.estimate(body("different teammate"), 11000)["cache_read_input_tokens"]
        == 0
    )
    changed_tools = deepcopy(second)
    changed_tools["tools"] = [{"name": "different", "input_schema": {}}]
    assert cache.estimate(changed_tools, 11000)["cache_read_input_tokens"] == 0


def test_expired_cache_is_cold(monkeypatch):
    monkeypatch.setattr("spike.gateway_cache.time.monotonic", lambda: 0)
    cache = CacheForecast()
    cache.observe(body(), {"cache_creation_input_tokens": 9000})
    monkeypatch.setattr("spike.gateway_cache.time.monotonic", lambda: 241)
    assert cache.estimate(body(), 10000)["cache_read_input_tokens"] == 0


def test_missing_cache_directive_and_automatic_cache_do_not_invent_hits():
    cache = CacheForecast()
    request = body()
    request["messages"][0]["content"][0].pop("cache_control")
    assert cache.estimate(request, 10000) == {"input_tokens": 10000, "output_tokens": 0}
    request["cache_control"] = {"type": "ephemeral"}
    assert (
        cache.estimate(request, 10000)["cache_creation"]["ephemeral_1h_input_tokens"]
        == 10000
    )
