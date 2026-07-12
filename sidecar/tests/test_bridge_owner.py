"""Bridge sender ownership + HTTP poll fallback."""

from __future__ import annotations

import asyncio

from blender_ai_sidecar.bridge import protocol as bridge


def test_clear_blender_sender_only_if_owner():
    async def send_a(_msg):
        return None

    async def send_b(_msg):
        return None

    bridge.set_blender_sender(send_a, owner=1)
    bridge.set_scene_cache(connected=True, summary={"a": 1})
    assert bridge.get_scene_cache()["connected"] is True

    # Newer connection takes over
    bridge.set_blender_sender(send_b, owner=2)
    assert bridge.clear_blender_sender_if(1) is False
    assert bridge.get_scene_cache()["connected"] is True

    assert bridge.clear_blender_sender_if(2) is True
    assert bridge.get_scene_cache()["connected"] is False

    async def check_disconnected():
        return await bridge.request_tool("scene.summary", {})

    result = asyncio.run(check_disconnected())
    assert result.get("ok") is False


def test_http_poll_tool_roundtrip():
    async def run():
        # Reset transport state
        bridge.set_blender_sender(None, owner=None)
        bridge.clear_http_blender()
        owner = bridge.register_http_blender("test-owner")
        assert bridge.bridge_transport() == "http"
        assert bridge.get_scene_cache()["connected"] is True

        async def caller():
            return await bridge.request_tool("scene.create_object", {"type": "cube", "name": "T"})

        async def poller():
            msg = await bridge.poll_outbound(timeout=2.0)
            assert msg is not None
            assert msg["tool"] == "scene.create_object"
            bridge.resolve_tool(msg["id"], {"ok": True, "name": "T"})
            return msg

        result, _msg = await asyncio.gather(caller(), poller())
        assert result == {"ok": True, "name": "T"}
        bridge.clear_http_blender(owner)
        assert bridge.bridge_transport() == "none"

    asyncio.run(run())
