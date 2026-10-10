"""Private loopback model gateway. Provider key enters once over stdin only.

Runs in a separate container/PID/filesystem namespace. Agent shares only its
network namespace, never key env, stdin, source mount or evidence mount.
"""

import json
import os
import sys
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

if __package__:
    from .gateway_budget import Budget
else:
    from gateway_budget import Budget

UPSTREAM = "https://api.anthropic.com"
MODEL = "claude-sonnet-4-6"
KEY = None
BUDGET = None
AUDIT = None


def audit():
    temporary = AUDIT.with_suffix(".tmp")
    temporary.write_text(json.dumps(BUDGET.snapshot(), indent=2) + "\n")
    temporary.replace(AUDIT)


def upstream(path, payload):
    headers = {
        "x-api-key": KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    req = urllib.request.Request(
        UPSTREAM + path, data=json.dumps(payload).encode(), headers=headers
    )
    return urllib.request.urlopen(req, timeout=180)


def usage_from(raw, streaming):
    if not streaming:
        return json.loads(raw).get("usage")
    usage = {}
    complete = False
    for line in raw.decode().splitlines():
        if not line.startswith("data: "):
            continue
        event = json.loads(line[6:])
        if event.get("type") == "message_start":
            usage.update(event.get("message", {}).get("usage", {}))
        elif event.get("type") == "message_delta":
            usage.update(event.get("usage", {}))
        elif event.get("type") == "message_stop":
            complete = True
    return usage if complete else None


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # Never log provider bodies, headers, prompts or credentials.

    def send(self, code, value, content_type="application/json"):
        data = value if isinstance(value, bytes) else json.dumps(value).encode()
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/health":
            self.send(200, {"ready": True, "model": MODEL})
        else:
            self.send(404, {"error": "unsupported gateway route"})

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        if path not in {"/v1/messages", "/v1/messages/count_tokens"}:
            self.send(404, {"error": "unsupported gateway route"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 8_000_000:
                raise ValueError("invalid request size")
            body = json.loads(self.rfile.read(length))
            if body.get("model") != MODEL:
                raise ValueError("model outside pinned allowlist")
            if (
                body.get("service_tier", "auto") not in {"auto", "standard_only"}
                or body.get("inference_geo", "global") != "global"
            ):
                raise ValueError("premium inference is disabled")
            if body.get("speed") or any(
                t.get("type", "custom") != "custom" for t in body.get("tools", [])
            ):
                raise ValueError("premium/server tools are disabled")
            with BUDGET.lock:
                if path.endswith("count_tokens"):
                    with upstream(path, body) as response:
                        self.send(200, response.read())
                    return
                counting = {
                    k: body[k]
                    for k in ("model", "messages", "system", "tools", "thinking")
                    if k in body
                }
                with upstream("/v1/messages/count_tokens", counting) as response:
                    count = json.load(response)["input_tokens"]
                maximum, reserved, tokens = BUDGET.reserve(
                    count, body.get("max_tokens", 4096)
                )
                body["max_tokens"] = maximum
                body["service_tier"] = "standard_only"
                # Reserve durably before starting billable work. An interrupted
                # stream never refunds itself or permits another request.
                BUDGET.unknown = True
                audit()
                try:
                    with upstream(path, body) as response:
                        BUDGET.accepted_requests += 1
                        audit()
                        raw = response.read()
                    usage = usage_from(raw, body.get("stream", False))
                    BUDGET.unknown = False
                    BUDGET.settle(reserved, tokens, usage)
                    audit()
                    self.send(
                        200,
                        raw,
                        (
                            "text/event-stream"
                            if body.get("stream")
                            else "application/json"
                        ),
                    )
                except Exception:
                    BUDGET.unknown = True
                    audit()
                    raise
        except ValueError:
            self.send(
                429,
                {
                    "type": "error",
                    "error": {
                        "type": "rate_limit_error",
                        "message": "gateway refused request or budget exhausted",
                    },
                },
            )
        except Exception:
            self.send(
                502,
                {
                    "type": "error",
                    "error": {
                        "type": "api_error",
                        "message": "gateway upstream unavailable; billing may be unknown",
                    },
                },
            )


if __name__ == "__main__":
    KEY = sys.stdin.readline().strip()
    if not KEY:
        raise SystemExit("gateway credential missing")
    BUDGET = Budget(
        float(os.environ["BENCH_GATEWAY_BUDGET"]),
        int(os.environ["BENCH_GATEWAY_TOKENS"]),
    )
    AUDIT = Path("/evidence/gateway.json")
    audit()
    ThreadingHTTPServer(("127.0.0.1", 18777), Handler).serve_forever()
