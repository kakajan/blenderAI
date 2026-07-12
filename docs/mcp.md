# MCP guide

Connect Cursor, Claude Desktop, or other MCP clients to a **live Blender session** through the BlenderAI sidecar.

فارسی: [mcp.fa.md](mcp.fa.md)

## Prerequisites

1. Blender is open with the **BlenderAI** extension enabled.
2. Sidecar is running (`python -m blender_ai_sidecar.main serve` or via the installer shortcut).
3. For write actions, set autonomy / MCP write policy appropriately in the WebUI.

## Cursor example

After running the **BlenderAI installer**, Cursor MCP is configured automatically at `~/.cursor/mcp.json`. Restart Cursor, then verify **blender-ai** appears under MCP servers.

Manual setup (or dev checkout):

```json
{
  "mcpServers": {
    "blender-ai": {
      "command": "C:/Users/You/AppData/Roaming/BlenderAI/sidecar/.venv/Scripts/python.exe",
      "args": ["-m", "blender_ai_sidecar.main", "mcp", "--stdio"],
      "cwd": "C:/Users/You/AppData/Roaming/BlenderAI/sidecar"
    }
  }
}
```

The MCP server **proxies to the running sidecar** on `127.0.0.1:8765` — keep Blender open with the addon connected (N-Panel status).

On macOS/Linux, point `cwd` at your checkout’s `sidecar` folder and ensure the venv’s `python` is on `PATH`, or call the venv interpreter explicitly:

```json
{
  "mcpServers": {
    "blender-ai": {
      "command": "/path/to/BlenderAI/sidecar/.venv/bin/python",
      "args": ["-m", "blender_ai_sidecar.main", "mcp", "--stdio"]
    }
  }
}
```

## Tools

| Tool | Description |
|------|-------------|
| `blender_status` | Connection / Blender status |
| `scene_summary` | Live scene summary (fetched from Blender, not stale cache) |
| `viewport_capture` | Viewport image(s) — supports `views: ["front","side","back",…]`, `target`, `shading` for turnaround-style scene understanding |
| `invoke_tool` | Run a Blender bridge tool directly (`scene.create_object`, `mesh.ops`, `particle.fur_set`, …) |
| `execute_skill` | Prepare a skill for the **Cursor delegated provider** (default) |
| `chat` | Prepare a chat turn for the **Cursor delegated provider** (default) |
| `list_objects` | Objects from live scene summary |
| `undo` / `redo` | History control |

## Learning from sessions

BlenderAI now records successful tool runs and user feedback, then injects relevant past patterns into new chat/MCP turns.

| API | Purpose |
|-----|---------|
| `POST /api/learnings/feedback` | Save thumbs-up/down style feedback (`rating`: up/down/good/bad) with optional note |
| `GET /api/learnings/relevant?user_goal=...` | Retrieve matching past successful sessions |
| `GET /api/learnings/tool-runs?chat_id=...` | Inspect tool history for a chat |
| `POST /api/skills/from-chat` | Promote a successful chat into a `user.*` skill (preserves tool recipes) |
| `POST /api/presets/from-chat` | Now also extracts ` ```json tool ` blocks into the preset |

Auto-learning: chats with ≥3 successful tools auto-record a positive learning entry.

**Modeling Strategy:** at chat start the agent injects a phased plan (e.g. blockout → extrude → SUBSURF → sculpt → mesh polish) chosen from the request, skill, scene, and reference image. Status event `chat_ready` includes `modeling_strategy` metadata.

Recommended skills for reference-based characters:
- `modeling.surface_advanced` — box modeling with extrude/inset/bevel/profile extrude (not primitive stacking)
- `modeling.turnaround_character` — builds and verifies from front/side/back
- `modeling.character_stylized` — materials, fur, eyes (use after surface_advanced)
- Workflow `workflow.surface_character` — surface build → stylized finish → critique
- Workflow `workflow.turnaround_character` — build + critique loop

Advanced mesh tools (extension bridge):
- `mesh.extrude` — semantic face select + extrude + optional inset (`faces: top_cap|by_normal`, `distance`)
- `mesh.edge_loop` — evenly spaced edge loops along an axis
- `mesh.profile_extrude` — 2D profile + depth for wings/tails/beaks
- `mesh.select` — semantic selectors: `by_normal`, `top_cap`, `bottom_cap`, `boundary` edges

## Cursor as provider (delegated mode)

When BlenderAI MCP runs inside **Cursor**, `chat` and `execute_skill` default to `provider_id: cursor`. The MCP server does **not** call Ollama/OpenAI on the sidecar. Instead it returns a **delegated** payload from `POST /api/mcp/prepare`:

- `mode: "delegated"` and `provider_id: "cursor"`
- `system_prompt`, `allowed_tools`, `scene_summary`, and `user_message`
- Instructions to call `invoke_tool` for each Blender action

Typical flow from Cursor:

1. `execute_skill` with `skill_id: modeling.blockout` and your prompt
2. Read the delegated response (`allowed_tools`, scene context)
3. Call `invoke_tool` once per Blender tool (e.g. `scene.create_object`, `mesh.ops`)
4. Confirm each result has `ok: true` before continuing

You do **not** need a separate LLM provider configured in the WebUI for this workflow — Cursor Agent is the reasoning layer.

To use a sidecar LLM instead (Ollama, OpenAI, …), pass `provider_id` explicitly on `chat` / `execute_skill`; those requests go through `/api/chat/stream` as before.

Example `execute_skill` arguments:

```json
{
  "skill_id": "modeling.blockout",
  "prompt": "Block out a simple table with four legs"
}
```

Optional override:

```json
{
  "skill_id": "modeling.blockout",
  "prompt": "Block out a table",
  "provider_id": "ollama"
}
```

## Safety tips

- Prefer read-only exploration first (`scene_summary`, `list_objects`).
- Keep **Local Only** on if you do not want cloud models involved.
- Rotate the MCP token from WebUI **Settings** if you expose HTTP/SSE later.

## Troubleshooting

| Symptom | Try |
|---------|-----|
| `All providers failed` on `execute_skill` / `chat` | Reinstall/restart sidecar so MCP defaults to `cursor`; or pass `provider_id: "cursor"`; or configure Ollama/OpenAI in WebUI |
| Tools time out | Is Blender open? Is the addon connected (N-Panel status)? |
| Empty scene summary | Select something in Blender or wait for the bridge hello |
| Module not found | Activate the sidecar venv / fix `cwd` |

Need help? [Open an issue](https://github.com/kakajan/blenderAI/issues) or reach [@kakajan](https://github.com/kakajan) — we’re happy to walk through your setup.
