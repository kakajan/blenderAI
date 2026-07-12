from __future__ import annotations

import json
import queue
from typing import Any

import bpy

_tool_queue: queue.Queue = queue.Queue()
_drain_registered = False


def enqueue_tool(request_id: str, tool: str, args: dict[str, Any]) -> None:
    _tool_queue.put({"id": request_id, "tool": tool, "args": args})
    _ensure_drain()


def _ensure_drain() -> None:
    global _drain_registered
    if _drain_registered:
        return
    if not bpy.app.timers.is_registered(_drain):
        bpy.app.timers.register(_drain, first_interval=0.05, persistent=True)
    _drain_registered = True


def _drain():
    global _drain_registered
    import importlib
    from ..bridge import tools as tool_exec

    importlib.reload(tool_exec)
    while not _tool_queue.empty():
        item = _tool_queue.get()
        try:
            bpy.ops.blender_ai.execute_tool(
                tool=item["tool"],
                args_json=json.dumps(item.get("args") or {}),
                request_id=item.get("id") or "",
            )
        except Exception as e:
            from . import client as bridge_client
            from .. import log_client

            log_client.exception(f"Tool drain failed: {e}", e, component="tools")
            bridge_client.send_json(
                {
                    "type": "tool_result",
                    "id": item.get("id"),
                    "result": {"ok": False, "error": str(e)},
                }
            )
    # Idle: stop timer until the next enqueue_tool
    _drain_registered = False
    return None


def register():
    # Lazy: timer starts on first tool request (see enqueue_tool)
    pass


def unregister():
    global _drain_registered
    if bpy.app.timers.is_registered(_drain):
        bpy.app.timers.unregister(_drain)
    _drain_registered = False
