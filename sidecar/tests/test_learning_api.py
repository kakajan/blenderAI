"""Promotion gate + learning clear APIs."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from blender_ai_sidecar.config import get_settings
from blender_ai_sidecar.main import create_app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    app = create_app()
    with TestClient(app) as c:
        token = c.get("/api/auth/session").json()["token"]
        c.headers["X-BlenderAI-Token"] = token
        yield c
    get_settings.cache_clear()


def test_learning_enabled_setting(client: TestClient):
    put = client.put("/api/settings", json={"learning_enabled": False})
    assert put.status_code == 200
    assert put.json()["learning_enabled"] is False
    put2 = client.put("/api/settings", json={"learning_enabled": True})
    assert put2.json()["learning_enabled"] is True


def test_clear_learnings(client: TestClient):
    fb = client.post(
        "/api/learnings/feedback",
        json={"rating": "up", "user_goal": "make a bird", "note": "nice"},
    )
    assert fb.status_code == 200
    cleared = client.delete("/api/learnings")
    assert cleared.status_code == 200
    assert cleared.json()["deleted"] >= 1


def test_confirm_endpoint_exists(client: TestClient):
    # Unknown run returns ok=false
    resp = client.post("/api/runs/does-not-exist/confirm", json={"approved": True})
    assert resp.status_code == 200
    assert resp.json()["ok"] is False
