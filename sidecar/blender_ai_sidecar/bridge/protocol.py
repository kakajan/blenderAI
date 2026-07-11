from __future__ import annotations

import asyncio
import uuid
from typing import Any, Callable, Awaitable

# Pending tool calls waiting for Blender addon response
_pending: dict[str, asyncio.Future] = {}
_blender_send: Callable[[dict[str, Any]], Awaitable[None]] | None = None
_scene_cache: dict[str, Any] = {"connected": False, "summary": {}}


def set_blender_sender(sender: Callable[[dict[str, Any]], Awaitable[None]] | None) -> None:
    global _blender_send
    _blender_send = sender


def set_scene_cache(**kwargs: Any) -> None:
    _scene_cache.update(kwargs)


def get_scene_cache() -> dict[str, Any]:
    return dict(_scene_cache)


async def request_tool(tool: str, args: dict[str, Any] | None = None, timeout: float = 30.0) -> dict[str, Any]:
    if not _blender_send:
        return {"ok": False, "error": "Blender not connected"}
    req_id = str(uuid.uuid4())
    loop = asyncio.get_running_loop()
    fut: asyncio.Future = loop.create_future()
    _pending[req_id] = fut
    await _blender_send({"type": "tool_request", "id": req_id, "tool": tool, "args": args or {}})
    try:
        return await asyncio.wait_for(fut, timeout=timeout)
    except asyncio.TimeoutError:
        return {"ok": False, "error": "Tool timeout"}
    finally:
        _pending.pop(req_id, None)


def resolve_tool(req_id: str, result: dict[str, Any]) -> None:
    fut = _pending.get(req_id)
    if fut and not fut.done():
        fut.set_result(result)


# Allowlisted logical tools mapped for documentation / MCP
ALLOWLIST = {
    "scene.create_object",
    "mesh.ops",
    "selection.set",
    "modifier.add",
    "modifier.apply",
    "material.create",
    "material.assign",
    "node.set",
    "light.set",
    "world.set",
    "collection.organize",
    "sculpt.set_brush",
    "nodes.geometry_set",
    "render.set",
    "viewport.capture",
    "scene.summary",
    "undo",
    "redo",
}
