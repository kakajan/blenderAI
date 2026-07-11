from __future__ import annotations

"""Minimal MCP stdio server for BlenderAI.

Uses JSON-RPC style framing compatible with MCP tool listing when the optional
`mcp` package is unavailable — falls back to a simple stdio protocol.
"""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

from blender_ai_sidecar.bridge import protocol as bridge
from blender_ai_sidecar.config import get_settings
from blender_ai_sidecar.providers.router import ProviderRouter
from blender_ai_sidecar.skills.engine import SkillEngine
from blender_ai_sidecar.store.db import Database
from blender_ai_sidecar.chat.agent import ChatAgent


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
        "description": "Request a viewport capture from Blender",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "execute_skill",
        "description": "Execute a BlenderAI skill with a prompt",
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
        "description": "Chat with BlenderAI agent",
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
        "description": "List objects from cached scene summary",
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


async def _call_tool(name: str, arguments: dict[str, Any], agent: ChatAgent) -> Any:
    if name == "blender_status":
        return bridge.get_scene_cache()
    if name == "scene_summary":
        cached = bridge.get_scene_cache().get("summary")
        if cached:
            return cached
        return await bridge.request_tool("scene.summary", {})
    if name == "viewport_capture":
        return await bridge.request_tool("viewport.capture", {})
    if name == "list_objects":
        summary = bridge.get_scene_cache().get("summary") or {}
        return summary.get("objects") or summary.get("object_names") or []
    if name == "undo":
        return await bridge.request_tool("undo", {})
    if name == "redo":
        return await bridge.request_tool("redo", {})
    if name in {"chat", "execute_skill"}:
        text_parts: list[str] = []
        async for event in agent.run_stream(
            provider_id=arguments.get("provider_id") or "ollama",
            model=None,
            skill_id=arguments.get("skill_id"),
            user_message=arguments.get("prompt") or arguments.get("message") or "",
            local_only=False,
        ):
            if event.type == "token":
                text_parts.append(event.content)
            elif event.type == "error":
                return {"ok": False, "error": event.content}
        return {"ok": True, "text": "".join(text_parts)}
    return {"ok": False, "error": f"Unknown tool {name}"}


async def run_mcp_stdio() -> None:
    settings = get_settings()
    db = Database(settings.resolved_db())
    await db.connect()
    skills = SkillEngine()
    skills.load()
    router = ProviderRouter(db)
    agent = ChatAgent(db, router, skills)

    # Try official MCP SDK
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
            result = await _call_tool(name, arguments or {}, agent)
            return [types.TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())
        return
    except Exception:
        pass

    # Fallback minimal JSON-RPC loop
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
            result = await _call_tool(params.get("name"), params.get("arguments") or {}, agent)
            resp = {"jsonrpc": "2.0", "id": rid, "result": {"content": [{"type": "text", "text": json.dumps(result)}]}}
        elif method == "initialize":
            resp = {
                "jsonrpc": "2.0",
                "id": rid,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "blender-ai", "version": "1.0.0"},
                },
            }
        else:
            resp = {"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": "Method not found"}}
        sys.stdout.write(json.dumps(resp) + "\n")
        sys.stdout.flush()

    await db.close()


def main_mcp() -> None:
    asyncio.run(run_mcp_stdio())
