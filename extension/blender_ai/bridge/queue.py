from __future__ import annotations

import json
import queue
from typing import Any

import bpy

_tool_queue: queue.Queue = queue.Queue()


def enqueue_tool(request_id: str, tool: str, args: dict[str, Any]) -> None:
    _tool_queue.put({"id": request_id, "tool": tool, "args": args})


def _drain():
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

            bridge_client.send_json(
                {
                    "type": "tool_result",
                    "id": item.get("id"),
                    "result": {"ok": False, "error": str(e)},
                }
            )
    return 0.1


def register():
    if not bpy.app.timers.is_registered(_drain):
        bpy.app.timers.register(_drain, first_interval=0.2, persistent=True)


def unregister():
    if bpy.app.timers.is_registered(_drain):
        bpy.app.timers.unregister(_drain)
