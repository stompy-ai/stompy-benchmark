"""Staging-only MCP client. The fixture's existing key is read from env only."""

import json
import os
import urllib.error
import urllib.request

from toon import decode

STAGING = "https://api-staging.stompy.ai"


class MCP:
    def __init__(self):
        self.project = os.environ["STOMPY_BENCHMARK_PROJECT"]
        if self.project != "stompy_benchmark":
            raise ValueError("unexpected fixture project")
        self.key = os.environ["STOMPY_BENCHMARK_API_KEY"]
        self.sequence = 0
        self.headers = {
            "Authorization": "Bearer " + self.key,
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        }
        self.rpc(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "stompy-shadow-spike", "version": "1"},
            },
        )

    def rpc(self, method, params):
        self.sequence += 1
        body = json.dumps(
            {"jsonrpc": "2.0", "id": self.sequence, "method": method, "params": params}
        ).encode()
        request = urllib.request.Request(
            STAGING + "/mcp", data=body, headers=self.headers
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                raw = response.read().decode()
                session = response.headers.get("Mcp-Session-Id")
                if session:
                    self.headers["Mcp-Session-Id"] = session
        except Exception as error:
            raise RuntimeError(
                f"MCP transport failed: {type(error).__name__}"
            ) from None
        if raw.startswith("event:") or raw.startswith("data:"):
            payloads = [
                json.loads(line[6:])
                for line in raw.splitlines()
                if line.startswith("data: ")
            ]
            payload = next((p for p in payloads if p.get("id") == self.sequence), None)
            if payload is None:
                raise ValueError("missing matching MCP response")
        else:
            payload = json.loads(raw)
        if "error" in payload:
            raise ValueError("MCP protocol error")
        return payload["result"]

    def call(self, name, arguments, *, allow_error=False):
        result = self.rpc("tools/call", {"name": name, "arguments": arguments})
        text = result.get("structuredContent", {}).get("result")
        if text is None:
            text = "\n".join(
                c["text"] for c in result.get("content", []) if c.get("type") == "text"
            )
        try:
            value = json.loads(text)
        except (json.JSONDecodeError, TypeError):
            try:
                value = decode(text)
            except Exception:
                value = {"raw": text}
        failed = result.get("isError") or (
            isinstance(value, dict)
            and (value.get("success") is False or value.get("error"))
        )
        if failed and not allow_error:
            raise ValueError(
                f"MCP {name} refused: {str(value.get('error','unknown') if isinstance(value,dict) else value)[:300]}"
            )
        return value

    def query(self, query, params=None):
        result = self.call(
            "db_query",
            {
                "query": query,
                "params": params or [],
                "project": self.project,
                "format": "json",
            },
        )
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            if isinstance(result.get("rows"), list):
                return result["rows"]
            if isinstance(result.get("data"), list):
                return result["data"]
        raise ValueError("db_query did not return a complete JSON row list")

    def preflight(self):
        own = self.query("SELECT current_schema() AS schema")
        if own != [{"schema": self.project}]:
            raise ValueError("fixture schema identity mismatch")
        denied = self.call(
            "context_explore",
            {"project": "stompy", "detail": "summary"},
            allow_error=True,
        )
        if not isinstance(denied, dict) or denied.get("error") not in {
            "ACCESS_DENIED",
            "INVALID_PROJECT",
            "PROJECT_NOT_FOUND",
        }:
            raise ValueError("cross-project preflight did not establish refusal")
        return {
            "own_schema": self.project,
            "other_project": "stompy",
            "refusal": denied["error"],
        }


def server_build():
    with urllib.request.urlopen(STAGING + "/health", timeout=30) as response:
        data = json.load(response)
    sha = data.get("commit", "")
    if (
        data.get("status") != "healthy"
        or len(sha) != 40
        or any(c not in "0123456789abcdef" for c in sha)
    ):
        raise ValueError("missing healthy server build SHA")
    return sha
