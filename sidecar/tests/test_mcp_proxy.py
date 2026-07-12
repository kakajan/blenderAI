from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from blender_ai_sidecar.mcp import proxy


@pytest.mark.asyncio
async def test_get_status_offline():
    with patch("blender_ai_sidecar.mcp.proxy.httpx.AsyncClient") as client_cls:
        client = AsyncMock()
        client.__aenter__.return_value = client
        client.get.side_effect = proxy.httpx.ConnectError("refused")
        client_cls.return_value = client
        status = await proxy.get_status()
    assert status["sidecar_online"] is False
    assert "Sidecar not running" in status["error"]


@pytest.mark.asyncio
async def test_invoke_tool_success():
    with patch("blender_ai_sidecar.mcp.proxy.httpx.AsyncClient") as client_cls:
        client = AsyncMock()
        client.__aenter__.return_value = client
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {"ok": True, "summary": {"objects": []}}
        client.post.return_value = resp
        client_cls.return_value = client
        result = await proxy.invoke_tool("scene.summary", {})
    assert result["ok"] is True


@pytest.mark.asyncio
async def test_resolve_mcp_provider_defaults_to_cursor():
    assert proxy.resolve_mcp_provider(None) == "cursor"
    assert proxy.resolve_mcp_provider("") == "cursor"
    assert proxy.resolve_mcp_provider("cursor-agent") == "cursor"
    assert proxy.resolve_mcp_provider("ollama") == "ollama"


@pytest.mark.asyncio
async def test_chat_turn_empty_provider_uses_delegate():
    with patch("blender_ai_sidecar.mcp.proxy.httpx.AsyncClient") as client_cls:
        client = AsyncMock()
        client.__aenter__.return_value = client
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {"ok": True, "mode": "delegated"}
        client.post.return_value = resp
        client_cls.return_value = client
        result = await proxy.chat_turn("hello", provider_id="")
    assert result["mode"] == "delegated"
    assert client.post.await_args.args[0].endswith("/api/mcp/prepare")


@pytest.mark.asyncio
async def test_chat_turn_uses_cursor_delegate():
    with patch("blender_ai_sidecar.mcp.proxy.httpx.AsyncClient") as client_cls:
        client = AsyncMock()
        client.__aenter__.return_value = client
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {"ok": True, "mode": "delegated", "allowed_tools": ["scene.create_object"]}
        client.post.return_value = resp
        client_cls.return_value = client
        result = await proxy.chat_turn("build a cube", skill_id="modeling.blockout", provider_id="cursor")
    assert result["ok"] is True
    assert result["mode"] == "delegated"
    client.post.assert_awaited_once()
    assert client.post.await_args.args[0].endswith("/api/mcp/prepare")


@pytest.mark.asyncio
async def test_cursor_provider_test_connection():
    from blender_ai_sidecar.providers.cursor import CursorProvider

    provider = CursorProvider()
    result = await provider.test_connection()
    assert result["ok"] is True
    models = await provider.list_models()
    assert models[0].id == "cursor-agent"


@pytest.mark.asyncio
async def test_chat_turn_parses_sse():
    async def fake_aiter_text():
        payload = json.dumps({"type": "token", "content": "Hello"})
        yield f"data: {payload}\n\n"

    class FakeStream:
        status_code = 200

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        def aiter_text(self):
            return fake_aiter_text()

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        def stream(self, *args, **kwargs):
            return FakeStream()

    with patch("blender_ai_sidecar.mcp.proxy.httpx.AsyncClient", FakeClient):
        result = await proxy.chat_turn("hi", provider_id="opencode")
    assert result == {"ok": True, "text": "Hello"}
