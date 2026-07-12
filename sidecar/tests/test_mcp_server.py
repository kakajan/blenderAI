from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from blender_ai_sidecar.mcp.server import _call_tool


@pytest.mark.asyncio
async def test_execute_skill_defaults_to_cursor_delegate():
    delegated = {
        "ok": True,
        "mode": "delegated",
        "provider_id": "cursor",
        "allowed_tools": ["scene.create_object"],
    }
    with patch("blender_ai_sidecar.mcp.server.proxy.chat_turn", new_callable=AsyncMock) as chat_turn:
        chat_turn.return_value = delegated
        result = await _call_tool(
            "execute_skill",
            {"skill_id": "modeling.blockout", "prompt": "add a cube"},
        )
    assert result == delegated
    chat_turn.assert_awaited_once_with(
        "add a cube",
        skill_id="modeling.blockout",
        provider_id="cursor",
    )


@pytest.mark.asyncio
async def test_chat_defaults_to_cursor_delegate():
    delegated = {"ok": True, "mode": "delegated", "provider_id": "cursor"}
    with patch("blender_ai_sidecar.mcp.server.proxy.chat_turn", new_callable=AsyncMock) as chat_turn:
        chat_turn.return_value = delegated
        result = await _call_tool("chat", {"message": "status?"})
    assert result["mode"] == "delegated"
    chat_turn.assert_awaited_once_with("status?", skill_id=None, provider_id="cursor")


@pytest.mark.asyncio
async def test_scene_summary_prefers_live_fetch():
    live = {"ok": True, "summary": {"object_names": ["Bird_Body", "Beak"]}}
    with patch("blender_ai_sidecar.mcp.server.proxy.invoke_tool", new_callable=AsyncMock) as invoke:
        invoke.return_value = live
        result = await _call_tool("scene_summary", {})
    assert result == live["summary"]
    invoke.assert_awaited_once_with("scene.summary", {}, timeout=15.0)


@pytest.mark.asyncio
async def test_list_objects_prefers_live_fetch():
    live = {"ok": True, "summary": {"objects": [{"name": "Bird_Body"}]}}
    with patch("blender_ai_sidecar.mcp.server.proxy.invoke_tool", new_callable=AsyncMock) as invoke:
        invoke.return_value = live
        result = await _call_tool("list_objects", {})
    assert result == [{"name": "Bird_Body"}]
    invoke.assert_awaited_once_with("scene.summary", {}, timeout=15.0)


@pytest.mark.asyncio
async def test_execute_skill_honors_explicit_provider():
    with patch("blender_ai_sidecar.mcp.server.proxy.chat_turn", new_callable=AsyncMock) as chat_turn:
        chat_turn.return_value = {"ok": True, "text": "hi"}
        await _call_tool(
            "execute_skill",
            {"skill_id": "modeling.blockout", "prompt": "cube", "provider_id": "ollama"},
        )
    chat_turn.assert_awaited_once_with(
        "cube",
        skill_id="modeling.blockout",
        provider_id="ollama",
    )
