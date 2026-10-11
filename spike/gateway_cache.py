"""Short-lived, exact-prefix cache forecasts; never assume a provider cache hit.

Only usage-confirmed prefixes earn read pricing. Unknown shapes stay cold.
No prompt content is persisted; the gateway keeps digests in memory per cell.
"""

import hashlib
import json
import time


def _clean(value: object) -> object:
    if isinstance(value, dict):
        return {k: _clean(v) for k, v in value.items() if k != "cache_control"}
    if isinstance(value, list):
        return [_clean(v) for v in value]
    return value


def prefixes(body: dict) -> tuple[list[str], int, str]:
    parts = []
    last = -1
    ttl = "5m"

    def add(label: object, block: object) -> None:
        nonlocal last, ttl
        parts.append([label, _clean(block)])
        control = block.get("cache_control") if isinstance(block, dict) else None
        if control:
            if control.get("type") != "ephemeral" or control.get("ttl", "5m") not in {
                "5m",
                "1h",
            }:
                raise ValueError("unsupported cache directive")
            last = len(parts) - 1
            if control.get("ttl") == "1h":
                ttl = "1h"

    # Include every request-level input-affecting setting in the digest.
    salt = {
        k: v
        for k, v in body.items()
        if k
        not in {"tools", "system", "messages", "max_tokens", "stream", "service_tier"}
    }
    for index, tool in enumerate(body.get("tools", [])):
        add(["tool", index], tool)
    system = body.get("system", [])
    for index, block in enumerate([system] if isinstance(system, str) else system):
        add(["system", index], block)
    for index, message in enumerate(body.get("messages", [])):
        content = message.get("content", [])
        for position, block in enumerate(
            [content] if isinstance(content, str) else content
        ):
            add(["message", index, message.get("role"), position], block)
    digest = hashlib.sha256(json.dumps(salt, sort_keys=True).encode())
    keys = []
    for part in parts:
        digest.update(json.dumps(part, sort_keys=True).encode())
        keys.append(digest.hexdigest())
    # Automatic caching isn't inferred: forecast all input as a cold write.
    if body.get("cache_control"):
        return [], -1, "1h"
    return keys, last, ttl


class CacheForecast:
    def __init__(self) -> None:
        self.confirmed: dict[str, tuple[int, float]] = {}

    def estimate(self, body: dict, total: int) -> dict:
        keys, last, ttl = prefixes(body)
        now = time.monotonic()
        self.confirmed = {k: v for k, v in self.confirmed.items() if v[1] > now}
        cached = 0
        if last >= 0:
            # Provider lookup is bounded; don't credit arbitrarily old prefixes.
            for key in keys[max(0, last - 19) : last + 1]:
                cached = max(cached, self.confirmed.get(key, (0, 0))[0])
        cached = min(total, cached)
        if last < 0 and not body.get("cache_control"):
            return {"input_tokens": total, "output_tokens": 0}
        return {
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_read_input_tokens": cached,
            "cache_creation_input_tokens": total - cached,
            "cache_creation": {
                "ephemeral_5m_input_tokens": total - cached if ttl == "5m" else 0,
                "ephemeral_1h_input_tokens": total - cached if ttl == "1h" else 0,
            },
        }

    def observe(self, body: dict, usage: dict) -> None:
        keys, last, _ = prefixes(body)
        if last < 0:
            return
        cached = usage.get("cache_read_input_tokens", 0) + usage.get(
            "cache_creation_input_tokens", 0
        )
        if cached:
            # Use less than the minimum TTL even for 1h writes. Eviction remains
            # possible; Budget's independent cold-miss guard covers that risk.
            self.confirmed[keys[last]] = (cached, time.monotonic() + 240)
        else:
            self.confirmed.clear()
