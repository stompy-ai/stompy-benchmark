import io
import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from spike import gateway_server as server
from spike.gateway_budget import Budget


@pytest.fixture
def proxy(monkeypatch, tmp_path):
    calls = []

    def upstream(path, payload):
        calls.append((path, payload))
        data = (
            {"input_tokens": 10}
            if path.endswith("count_tokens")
            else {
                "content": [{"type": "text", "text": "ok"}],
                "usage": {"input_tokens": 10, "output_tokens": 1},
            }
        )
        return io.BytesIO(json.dumps(data).encode())

    monkeypatch.setattr(server, "upstream", upstream)
    monkeypatch.setattr(server, "BUDGET", Budget(0.1, 10000))
    monkeypatch.setattr(server, "AUDIT", tmp_path / "gateway.json")
    http = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    thread = threading.Thread(target=http.serve_forever, daemon=True)
    thread.start()

    def post(body, path="/v1/messages"):
        request = urllib.request.Request(
            "http://127.0.0.1:" + str(http.server_port) + path,
            data=json.dumps(body).encode(),
            headers={"Authorization": "Bearer cannot-forward-this"},
        )
        try:
            with urllib.request.urlopen(request) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as error:
            return error.code, json.load(error)

    yield post, calls, tmp_path
    http.shutdown()
    http.server_close()
    thread.join()


def test_only_fixed_model_and_routes_reach_upstream(proxy):
    post, calls, _ = proxy
    assert post({"model": "other"})[0] == 429
    assert post({"model": server.MODEL}, "/v1/anything")[0] == 404
    assert calls == []
    assert post({"model": server.MODEL, "messages": [], "max_tokens": 1})[0] == 200
    assert calls[-1][1]["service_tier"] == "standard_only"
    assert [x[0] for x in calls] == ["/v1/messages/count_tokens", "/v1/messages"]


def test_provider_failure_retains_reservation_and_stops_next_billable_call(
    proxy, monkeypatch
):
    post, calls, tmp = proxy

    def failed(path, payload):
        calls.append(path)
        if path.endswith("count_tokens"):
            return io.BytesIO(b'{"input_tokens":10}')
        raise OSError("sensitive upstream detail must not escape")

    monkeypatch.setattr(server, "upstream", failed)
    code, body = post({"model": server.MODEL, "messages": [], "max_tokens": 100})
    assert code == 502 and "sensitive" not in json.dumps(body)
    assert json.loads((tmp / "gateway.json").read_text())["billing_unknown"]
    assert post({"model": server.MODEL, "messages": [], "max_tokens": 100})[0] == 429
    assert calls.count("/v1/messages") == 1


def test_incomplete_stream_is_unknown():
    assert (
        server.usage_from(
            b'data: {"type":"message_start","message":{"usage":{"input_tokens":3}}}\n',
            True,
        )
        is None
    )


def test_upstream_rebuilds_headers_with_provider_key_only(monkeypatch):
    requests = []
    monkeypatch.setattr(server, "KEY", "provider-fixture-value")
    monkeypatch.setattr(
        server.urllib.request, "urlopen", lambda req, **kw: requests.append(req)
    )
    server.upstream("/v1/messages", {"model": server.MODEL})
    headers = dict(requests[0].header_items())
    assert headers["X-api-key"] == "provider-fixture-value"
    assert "Authorization" not in headers
