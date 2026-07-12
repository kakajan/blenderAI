---
name: blenderai-dev
description: >-
  Develop the BlenderAI repo (flat extension/, sidecar FastAPI, installer,
  WebUI, MCP). Use when changing extension bridge/tools, sidecar chat/agent,
  installer enable flow, N-Panel chat, or debugging Blender not connected /
  scene.create_object failures in this project.
---

# BlenderAI development

Apply together with **blender-extensions** and **blender-addon-api**.

## Architecture

```text
N-Panel / WebUI  →  HTTP/SSE  →  Sidecar :8765  →  WS tool_request  →  Extension
                                                         ↑
                                              blender_connected must be true
```

- Extension: `extension/` (flat: `blender_manifest.toml` + `__init__.py`)
- Sidecar: `sidecar/blender_ai_sidecar`
- Installer: `installer/install_core.py` (copy + `install-file --enable` + Python enable fallback)
- WebUI: `webui/` (optional; Providers / Chat)

## Extension conventions (this repo)

- Preferences: `bl_idname = __package__` in `preferences.py`
- Bridge: `bridge/client.py` — defer sidecar spawn via timer; WS hello `role: blender`
- Tools: main-thread via `bridge/queue.py` → `blender_ai.execute_tool`
- Do not block `register()` with long HTTP/FS work
- `install_info.json`: AppData `BlenderAI/` (+ optional copy next to package)

## Install / test loop

1. Build zip: installer `build_extension_zip` or Blender `extension build` from `extension/`
2. Close Blender → run installer **or** Install from Disk the zip
3. Add-ons → enable **BlenderAI**
4. Health: `http://127.0.0.1:8765/health` → `"blender_connected": true`
5. Viewport `N` → **BlenderAI**

Enable module candidates: `bl_ext.user_default.blender_ai`, legacy `blender_ai`.

## Sidecar

```bash
cd sidecar && python -m blender_ai_sidecar.main serve
```

Chat can work without Blender; **tools** require the WS bridge.

## When fixing “nothing created in Blender”

1. Sidecar online?
2. Extension enabled + N-Panel visible?
3. `/health` → `blender_connected`?
4. `websocket-client` available in Blender Python? (else poll-only, tools never run)

## Docs in repo

- `README.md` / `README.fa.md`
- `docs/architecture.md`
- `docs/mcp.md`
