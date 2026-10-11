"""Networkless test server: real gateway decision, synthetic token count only."""

import hashlib
import io
import json
import sys
from pathlib import Path
from http.server import ThreadingHTTPServer

sys.path.insert(0, "/gateway")
import gateway_server as server
from gateway_budget import Budget

server.BUDGET = Budget(0.000001, 15000000)
server.AUDIT = Path("/evidence/gateway.json")
counts = {"message_attempts": 0, "provider_calls": 0, "attempts": []}


def upstream(path, payload):
    assert path.endswith("count_tokens"), "billable path reached"
    return io.BytesIO(b'{"input_tokens":10}')


server.upstream = upstream
original = server.Handler.do_POST


def post(self):
    if self.path.split("?")[0] == "/v1/messages":
        counts["message_attempts"] += 1
        raw = self.rfile.read(int(self.headers["Content-Length"]))
        self.rfile = io.BytesIO(raw)
        body = json.loads(raw)
        counts["attempts"].append(
            {
                "body_sha256": hashlib.sha256(raw).hexdigest(),
                "stream": body.get("stream"),
                "model": body.get("model"),
                "retry_count": self.headers.get("x-stainless-retry-count"),
                "max_tokens": body.get("max_tokens"),
            }
        )
        Path("/evidence/calls.json").write_text(json.dumps(counts))
    original(self)


server.Handler.do_POST = post
server.audit()
ThreadingHTTPServer(("127.0.0.1", 18777), server.Handler).serve_forever()
