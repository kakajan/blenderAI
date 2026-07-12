# Architecture

High-level design of BlenderAI for contributors and curious users.

فارسی: [architecture.fa.md](architecture.fa.md)

## Components

1. **Blender extension** (`extension/`) — flat package (`blender_manifest.toml` + `__init__.py` at root), N-Panel, operators, scene context, WebSocket bridge client, tool queue on the main thread via `bpy.app.timers`.
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

## Capability layers (primitive vs recipe vs adaptive)

See the product matrix in [capability-catalog.md](capability-catalog.md) and Blender cheat-sheets in [blender-refs/](blender-refs/).

```text
User intent
  → Catalog row
  → Prefer compose existing primitives
  → Else ship a new primitive (ToolSpec + allowlist + handler + test)
  → Optional skill/preset recipe for repeated workflows
  → Adaptive: personal recipes + user skills + docs RAG + read-only introspect
```

### Primitive

- Stable allowlisted bridge tool (`ToolSpec` in sidecar `tools/__init__.py`, mirrored in `extension/bridge/allowlist.py`, handler in `extension/bridge/tools.py`).
- Composable and version-safe (e.g. Blender 5.x layered Actions).
- Grown by product releases — **not** by the model writing Python into the install folder.

### Recipe / skill

- YAML under `skills/` (bundled) or `%APPDATA%/BlenderAI/user_skills/` (hot-loaded).
- May only name allowlisted tools. Reload via `POST /api/skills/reload`.

### Adaptive (safe self-improvement)

What we do:

- Inject successful personal tool recipes from `LearningEngine`.
- Retrieve short passages from `docs/blender-refs/` (and optional local knowledge cache).
- Call `blender.introspect` (read-only) for version/engine/RNA hints.
- Hot-load user skills without reinstalling the extension.
- Record `capability_gap` when an intent needs a missing primitive.

What we deliberately do **not** do:

- `exec` / freeform `bpy` from model output as a default tool.
- Auto-writing new handlers into the installed extension package.
- Bypassing `PolicyEngine` / allowlist.
