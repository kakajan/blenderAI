from __future__ import annotations

"""MCP stdio server for BlenderAI — proxies to the live sidecar on :8765."""

import asyncio
import json
import sys
from typing import Any

from blender_ai_sidecar.mcp import proxy
from blender_ai_sidecar.mcp.proxy import resolve_mcp_provider


TOOLS = [
    {
        "name": "blender_status",
        "description": "Blender/sidecar connection status",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "scene_summary",
        "description": "Compact live scene summary from Blender",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "viewport_capture",
        "description": (
            "Capture the Blender viewport. Optional multi-angle: views "
            "['front','side','back','left','right','top','three_quarter','camera','user'] "
            "returns one image per angle so the scene can be understood like reference turnaround sheets. "
            "target = object name to frame; shading = MATERIAL|RENDERED|SOLID."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "views": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Angles to capture, e.g. ['front','side','back']",
                },
                "view": {"type": "string", "description": "Single angle (front|side|back|left|right|top|three_quarter|camera|user)"},
                "target": {"type": "string", "description": "Object name to frame (default: all visible meshes)"},
                "shading": {"type": "string", "description": "MATERIAL | RENDERED | SOLID | WIREFRAME"},
                "distance": {"type": "number", "description": "View distance override"},
            },
        },
    },
    {
        "name": "invoke_tool",
        "description": "Invoke a Blender tool directly through the live bridge",
        "inputSchema": {
            "type": "object",
            "properties": {
                "tool": {"type": "string"},
                "args": {"type": "object"},
                "timeout": {"type": "number"},
            },
            "required": ["tool"],
        },
    },
    {
        "name": "execute_skill",
        "description": "Prepare a BlenderAI skill for the Cursor agent (delegated provider)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "skill_id": {"type": "string"},
                "prompt": {"type": "string"},
                "provider_id": {"type": "string"},
            },
            "required": ["skill_id", "prompt"],
        },
    },
    {
        "name": "chat",
        "description": "Prepare a BlenderAI chat turn for the Cursor agent (delegated provider)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "message": {"type": "string"},
                "provider_id": {"type": "string"},
                "skill_id": {"type": "string"},
            },
            "required": ["message"],
        },
    },
    {
        "name": "list_objects",
        "description": "List objects from live scene summary",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "undo",
        "description": "Undo last Blender action",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "redo",
        "description": "Redo last Blender action",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


async def _call_tool(name: str, arguments: dict[str, Any]) -> Any:
    if name == "blender_status":
        return await proxy.get_status()
    if name == "scene_summary":
        result = await proxy.invoke_tool("scene.summary", {}, timeout=15.0)
        if result.get("ok") and result.get("summary"):
            return result["summary"]
        status = await proxy.get_status()
        return status.get("summary") or result
    if name == "viewport_capture":
        capture_args = {
            k: v
            for k, v in (arguments or {}).items()
            if k in {"views", "view", "target", "shading", "distance", "azimuth", "elevation"} and v is not None
        }
        return await proxy.invoke_tool("viewport.capture", capture_args, timeout=60.0)
    if name == "list_objects":
        fetched = await proxy.invoke_tool("scene.summary", {}, timeout=15.0)
        summary = fetched.get("summary") if isinstance(fetched, dict) else {}
        if not summary:
            status = await proxy.get_status()
            summary = status.get("summary") or {}
        return summary.get("objects") or summary.get("object_names") or []
    if name == "undo":
        return await proxy.invoke_tool("undo", {})
    if name == "redo":
        return await proxy.invoke_tool("redo", {})
    if name == "invoke_tool":
        return await proxy.invoke_tool(
            arguments.get("tool") or "",
            arguments.get("args"),
            timeout=float(arguments.get("timeout") or 30.0),
        )
    if name == "execute_skill":
        return await proxy.chat_turn(
            arguments.get("prompt") or "",
            skill_id=arguments.get("skill_id"),
            provider_id=resolve_mcp_provider(arguments.get("provider_id")),
        )
    if name == "chat":
        return await proxy.chat_turn(
            arguments.get("message") or "",
            skill_id=arguments.get("skill_id"),
            provider_id=resolve_mcp_provider(arguments.get("provider_id")),
        )
    return {"ok": False, "error": f"Unknown tool {name}"}


def _encode_result(result: Any) -> str:
    return json.dumps(result, ensure_ascii=False, indent=2)


async def run_mcp_stdio() -> None:
    try:
        from mcp.server import Server
        from mcp.server.stdio import stdio_server
        from mcp import types

        server = Server("blender-ai")

        @server.list_tools()
        async def list_tools() -> list[types.Tool]:
            return [
                types.Tool(name=t["name"], description=t["description"], inputSchema=t["inputSchema"])
                for t in TOOLS
            ]

        @server.call_tool()
        async def call_tool(name: str, arguments: dict[str, Any] | None) -> list[types.TextContent]:
            result = await _call_tool(name, arguments or {})
            return [types.TextContent(type="text", text=_encode_result(result))]

        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())
        return
    except ImportError:
        pass

    # Fallback minimal JSON-RPC loop (no mcp package)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue
        method = req.get("method")
        rid = req.get("id")
        if method == "tools/list":
            resp = {"jsonrpc": "2.0", "id": rid, "result": {"tools": TOOLS}}
        elif method == "tools/call":
            params = req.get("params") or {}
            result = await _call_tool(params.get("name"), params.get("arguments") or {})
            resp = {
                "jsonrpc": "2.0",
                "id": rid,
                "result": {"content": [{"type": "text", "text": _encode_result(result)}]},
            }
        elif method == "initialize":
            resp = {
                "jsonrpc": "2.0",
                "id": rid,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "blender-ai", "version": "1.0.3"},
                },
            }
        else:
            resp = {"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": "Method not found"}}
        sys.stdout.write(json.dumps(resp) + "\n")
        sys.stdout.flush()


def main_mcp() -> None:
    asyncio.run(run_mcp_stdio())
