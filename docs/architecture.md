# Architecture

High-level design of BlenderAI for contributors and curious users.

فارسی: [architecture.fa.md](architecture.fa.md)

## Components

1. **Blender extension** (`extension/blender_ai`) — N-Panel, operators, scene context, WebSocket bridge client, tool queue on the main thread via `bpy.app.timers`.
2. **Sidecar** (`sidecar/blender_ai_sidecar`) — FastAPI + WebSocket service for providers, chat agent, skills, SQLite store, MCP server, static WebUI.
3. **WebUI** (`webui`) — Chat and Providers settings UI served by the sidecar.
4. **Skills / Presets** — YAML + markdown definitions loaded by the sidecar.

## Data flow

```text
User (WebUI or MCP)
  → Sidecar Provider Router / Skill Engine
  → ToolCall JSON
  → Addon queue (main thread)
  → bpy ops + undo push
  → result → agent loop
```

## Default port

`127.0.0.1:8765` — HTTP, WebSocket, and static UI.

## Design principles

- Never block Blender’s UI thread on network I/O.
- Prefer allowlisted tools over freeform Python execution.
- Treat API keys as secrets (OS keyring).
- Keep English as the default product language; WebUI supports FA + independent RTL.
