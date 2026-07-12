"""Auth + policy integration for bridge invoke."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from blender_ai_sidecar.config import get_settings
from blender_ai_sidecar.main import create_app
from blender_ai_sidecar.tools import get_registry


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    app = create_app()
    with TestClient(app) as c:
        session = c.get("/api/auth/session")
        assert session.status_code == 200
        token = session.json()["token"]
        assert token
        c.headers["X-BlenderAI-Token"] = token
        yield c
    get_settings.cache_clear()


def test_registry_allowlist_includes_scene_create_object():
    assert "scene.create_object" in get_registry().allowlist()


def test_bridge_invoke_requires_token(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    app = create_app()
    with TestClient(app) as c:
        # Ensure a token exists (session bootstrap) but do not send it.
        session = c.get("/api/auth/session")
        assert session.status_code == 200
        resp = c.post("/api/bridge/invoke", json={"tool": "scene.summary", "args": {}})
        assert resp.status_code == 401
    get_settings.cache_clear()


def test_object_delete_requires_confirmation_when_ask(client: TestClient):
    from blender_ai_sidecar.bridge import protocol as bridge

    bridge.set_scene_cache(connected=True, summary={})
    # Default autonomy is ask; destructive tools need confirmation.
    put = client.put("/api/settings", json={"autonomy": "ask"})
    assert put.status_code == 200

    resp = client.post(
        "/api/bridge/invoke",
        json={"tool": "object.delete", "args": {"names": ["Cube"]}},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is False
    assert data["error_code"] == "confirmation_required"
    assert data.get("requires_confirmation") is True


def test_object_delete_allowed_when_confirmed(client: TestClient):
    from blender_ai_sidecar.bridge import protocol as bridge

    bridge.set_scene_cache(connected=True, summary={})
    put = client.put("/api/settings", json={"autonomy": "ask"})
    assert put.status_code == 200

    with patch(
        "blender_ai_sidecar.bridge.protocol.request_tool",
        new_callable=AsyncMock,
        return_value={"ok": True, "deleted": ["Cube"]},
    ) as mock_rt:
        resp = client.post(
            "/api/bridge/invoke",
            json={
                "tool": "object.delete",
                "args": {"names": ["Cube"]},
                "confirmed": True,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        mock_rt.assert_awaited_once()
