from __future__ import annotations

import json

import httpx
import pytest

from blender_ai_sidecar.providers.ollama import OllamaProvider
from blender_ai_sidecar.skills.engine import SkillEngine
from blender_ai_sidecar.config import repo_root


@pytest.mark.asyncio
async def test_ollama_list_models(monkeypatch):
    payload = {"models": [{"name": "llama3.2:latest"}, {"name": "qwen2.5:7b"}]}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return payload

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return None

        async def get(self, url):
            assert url.endswith("/api/tags")
            return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    provider = OllamaProvider()
    models = await provider.list_models()
    assert [m.id for m in models] == ["llama3.2:latest", "qwen2.5:7b"]


@pytest.mark.asyncio
async def test_ollama_chat_stream_omits_think_flag(monkeypatch):
    """think=false empties gemma4:e4b; omit the field and fall back to thinking."""
    seen = {}

    class FakeStreamResp:
        status_code = 200

        async def aread(self):
            return b""

        async def aiter_lines(self):
            yield json.dumps(
                {"message": {"role": "assistant", "content": "", "thinking": "Hi"}, "done": False}
            )
            yield json.dumps({"message": {"role": "assistant", "content": ""}, "done": True})

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return None

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return None

        def stream(self, method, url, json=None):
            seen["payload"] = json
            return FakeStreamResp()

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    provider = OllamaProvider(default_model="gemma4:12b")
    from blender_ai_sidecar.providers.base import ChatMessage, ChatRequest

    events = []
    texts = []
    async for ev in provider.chat_stream(
        ChatRequest(messages=[ChatMessage(role="user", content="hi")], model="gemma4:12b")
    ):
        events.append(ev.type)
        if ev.type == "token":
            texts.append(ev.content)
    assert "think" not in seen["payload"]
    assert texts == ["Hi"]
    assert "token" in events
    assert events[-1] == "done"


@pytest.mark.asyncio
async def test_ollama_chat_stream_prefers_content_over_thinking(monkeypatch):
    seen = {}

    class FakeStreamResp:
        status_code = 200

        async def aread(self):
            return b""

        async def aiter_lines(self):
            yield json.dumps(
                {
                    "message": {"role": "assistant", "content": "Hello", "thinking": "plan"},
                    "done": False,
                }
            )
            yield json.dumps({"message": {"role": "assistant", "content": ""}, "done": True})

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return None

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return None

        def stream(self, method, url, json=None):
            seen["payload"] = json
            return FakeStreamResp()

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    provider = OllamaProvider(default_model="gemma4:12b")
    from blender_ai_sidecar.providers.base import ChatMessage, ChatRequest

    texts = []
    async for ev in provider.chat_stream(
        ChatRequest(messages=[ChatMessage(role="user", content="hi")], model="gemma4:12b")
    ):
        if ev.type == "token":
            texts.append(ev.content)
    assert texts == ["Hello"]


@pytest.mark.asyncio
async def test_ollama_empty_content_is_soft_status(monkeypatch):
    """Empty done must not hard-error (that aborted N-Panel SSE before recovery)."""

    class FakeStreamResp:
        status_code = 200

        async def aread(self):
            return b""

        async def aiter_lines(self):
            yield json.dumps(
                {
                    "message": {"role": "assistant", "content": ""},
                    "done": True,
                    "done_reason": "stop",
                }
            )

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return None

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return None

        def stream(self, method, url, json=None):
            return FakeStreamResp()

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    provider = OllamaProvider(default_model="gemma4:12b")
    from blender_ai_sidecar.providers.base import ChatMessage, ChatRequest

    events = []
    async for ev in provider.chat_stream(
        ChatRequest(messages=[ChatMessage(role="user", content="hi")], model="gemma4:12b")
    ):
        events.append(ev)
    assert events[0].type == "status"
    assert events[0].content.startswith("empty_model_response")
    assert events[-1].type == "done"
    assert not any(e.type == "error" for e in events)


@pytest.mark.asyncio
async def test_router_does_not_fallback_after_soft_empty(monkeypatch):
    from blender_ai_sidecar.providers.base import ChatMessage, ChatRequest, StreamEvent
    from blender_ai_sidecar.providers.router import ProviderRouter

    class FakeDB:
        async def get_provider(self, pid):
            return {"id": pid, "kind": "ollama", "enabled": True, "base_url": "", "default_model": "m"}

        async def get_setting(self, key, default=""):
            if key == "fallback_chain":
                return '["other"]'
            return default

    calls = {"n": 0}

    class FakeProvider:
        async def chat_stream(self, req):
            calls["n"] += 1
            yield StreamEvent(type="status", content="empty_model_response:stop")
            yield StreamEvent(type="done")

    router = ProviderRouter(FakeDB())  # type: ignore[arg-type]

    async def fake_build(pid):
        return FakeProvider()

    monkeypatch.setattr(router, "build", fake_build)
    events = []
    async for ev in router.chat_stream(
        "ollama", ChatRequest(messages=[ChatMessage(role="user", content="hi")])
    ):
        events.append(ev.type)
    assert events == ["status", "done"]
    assert calls["n"] == 1


def test_opencode_is_default_provider():
    from blender_ai_sidecar.store.db import DEFAULT_PROVIDERS

    by_id = {row[0]: row for row in DEFAULT_PROVIDERS}
    assert "opencode" in by_id
    _id, kind, name, _en, base_url, default_model, _ord = by_id["opencode"]
    assert kind == "openai_compatible"
    assert name == "OpenCode Zen"
    assert base_url == "https://opencode.ai/zen/v1"
    assert default_model == "big-pickle"


def test_cursor_provider_seeded():
    from blender_ai_sidecar.store.db import DEFAULT_PROVIDERS

    by_id = {row[0]: row for row in DEFAULT_PROVIDERS}
    assert "cursor" in by_id
    _id, kind, name, enabled, _url, default_model, sort_order = by_id["cursor"]
    assert kind == "cursor"
    assert name == "Cursor Agent (MCP)"
    assert enabled == 1
    assert default_model == "cursor-agent"
    assert sort_order == -1


@pytest.mark.asyncio
async def test_router_builds_cursor_provider(tmp_path):
    from blender_ai_sidecar.providers.cursor import CursorProvider
    from blender_ai_sidecar.providers.router import ProviderRouter
    from blender_ai_sidecar.store.db import Database

    db = Database(tmp_path / "test.db")
    await db.connect()
    router = ProviderRouter(db)
    provider = await router.build("cursor")
    assert isinstance(provider, CursorProvider)
    result = await router.test("cursor")
    assert result["ok"] is True
    await db.close()


@pytest.mark.asyncio
async def test_seed_inserts_missing_opencode(tmp_path):
    from blender_ai_sidecar.store.db import Database

    db = Database(tmp_path / "test.db")
    await db.connect()
    # Simulate an older install that never had opencode.
    await db.conn.execute("DELETE FROM providers WHERE id='opencode'")
    await db.conn.commit()
    assert await db.get_provider("opencode") is None
    await db._seed_providers()
    row = await db.get_provider("opencode")
    assert row is not None
    assert row["base_url"] == "https://opencode.ai/zen/v1"
    await db.close()

