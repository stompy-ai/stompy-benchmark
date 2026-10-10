"""Runtime REST-contract oracles; existing lifecycle storage is a controlled seam.

These test transport, validation, authorization routing and argument/response
parity. They do not claim to revalidate the existing lifecycle SQL implementation.
"""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

ROUTE = "/api/v1/projects/bench/contexts/rule/lifecycle"


@pytest.fixture
def door(monkeypatch):
    import stompy_server
    from src.api.dependencies import get_current_user, get_user_db_url
    from src.api.router import api_router
    from src.services import project_access_resolver as resolver
    from src.services.request_scope import (
        reset_token_project_scope,
        set_token_project_scope,
    )

    user = SimpleNamespace(
        user_id="test", internal_id=51, tier="beta", auth_type="project_api_key"
    )
    app = FastAPI()
    app.include_router(api_router, prefix="/api/v1")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_user_db_url] = lambda: "postgresql://personal/db"
    monkeypatch.setattr(resolver, "_personal_schema_for", lambda *a: None)
    monkeypatch.setattr(
        resolver,
        "_shared_project_row",
        lambda name: {"schema_name": name, "is_shared": True},
    )
    monkeypatch.setattr(resolver, "_membership", lambda *a: (True, app.state.role))
    monkeypatch.setattr(resolver, "_main_db_url", lambda: "postgresql://main/db")
    app.state.role = "owner"

    async def transition(**kw):
        return json.dumps(
            {"topic": kw["topic"], "lifecycle": kw["state"], "changed": True}
        )

    tool = AsyncMock(side_effect=transition)
    monkeypatch.setattr(stompy_server, "set_lifecycle", tool)

    @app.middleware("http")
    async def scope(request, call_next):
        tokens = set_token_project_scope("bench", "test")
        try:
            return await call_next(request)
        finally:
            reset_token_project_scope(tokens)

    with TestClient(app) as client:
        yield SimpleNamespace(client=client, tool=tool, app=app)


def test_transition_response_and_arguments(door):
    response = door.client.post(
        ROUTE, json={"state": "parked", "review_after_days": 12, "note": "later"}
    )
    assert response.status_code == 200, response.text
    assert response.json()["lifecycle"] == "parked"
    door.tool.assert_awaited_once_with(
        topic="rule",
        state="parked",
        project="bench",
        review_after_days=12,
        note="later",
    )


def test_invalid_state_is_422(door):
    response = door.client.post(ROUTE, json={"state": "deleted"})
    assert response.status_code == 422, response.text
    door.tool.assert_not_called()


def test_critical_viewer_cannot_transition(door):
    door.app.state.role = "viewer"
    response = door.client.post(ROUTE, json={"state": "archived"})
    assert response.status_code == 403, response.text
    door.tool.assert_not_called()


def test_critical_cross_project_key_refused(door):
    assert door.client.post(ROUTE, json={"state": "active"}).status_code == 200
    door.tool.reset_mock()
    response = door.client.post(
        ROUTE.replace("/bench/", "/other/"), json={"state": "archived"}
    )
    assert response.status_code == 404, response.text
    door.tool.assert_not_called()


def test_missing_topic_maps_to_404(door):
    door.tool.side_effect = None
    door.tool.return_value = json.dumps(
        {"success": False, "error": "CONTEXT_NOT_FOUND", "message": "absent"}
    )
    response = door.client.post(ROUTE, json={"state": "active"})
    # Requiring invocation prevents the missing-route 404 from passing.
    door.tool.assert_awaited_once()
    assert response.status_code == 404, response.text
    assert "CONTEXT_NOT_FOUND" in response.text


def test_idempotent_result_preserved(door):
    door.tool.side_effect = None
    door.tool.return_value = json.dumps(
        {"topic": "rule", "lifecycle": "active", "changed": False}
    )
    response = door.client.post(ROUTE, json={"state": "active"})
    assert response.status_code == 200, response.text
    assert response.json()["changed"] is False


def test_contract_names_route_and_keeps_mcp():
    import src

    root = Path(src.__file__).resolve().parent.parent
    row = json.loads((root / "surface_contract.json").read_text())["capabilities"][
        "context.lifecycle"
    ]
    assert row["rest"] == "POST /projects/{name}/contexts/{topic}/lifecycle"
    assert row["mcp"] == "set_lifecycle"
    assert "rest" not in row.get("waived", {})
    assert row.get("cli") or row["waived"]["cli"]


def test_critical_authentication_required(door):
    from src.api.dependencies import get_current_user

    door.app.dependency_overrides.pop(get_current_user)
    response = door.client.post(ROUTE, json={"state": "active"})
    assert response.status_code == 401, response.text
    door.tool.assert_not_called()
