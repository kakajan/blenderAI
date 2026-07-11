# MCP guide

Connect Cursor, Claude Desktop, or other MCP clients to a **live Blender session** through the BlenderAI sidecar.

فارسی: [mcp.fa.md](mcp.fa.md)

## Prerequisites

1. Blender is open with the **BlenderAI** extension enabled.
2. Sidecar is running (`python -m blender_ai_sidecar.main serve` or via the installer shortcut).
3. For write actions, set autonomy / MCP write policy appropriately in the WebUI.

## Cursor example

```json
{
  "mcpServers": {
    "blender-ai": {
      "command": "python",
      "args": ["-m", "blender_ai_sidecar.main", "mcp", "--stdio"],
      "cwd": "D:/Projects/blenderAI/sidecar"
    }
  }
}
```

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
| `scene_summary` | Compact live scene summary |
| `viewport_capture` | Request a viewport image |
| `execute_skill` | Run a named skill with a prompt |
| `chat` | Agent chat turn |
| `list_objects` | Objects from the cached summary |
| `undo` / `redo` | History control |

## Safety tips

- Prefer read-only exploration first (`scene_summary`, `list_objects`).
- Keep **Local Only** on if you do not want cloud models involved.
- Rotate the MCP token from WebUI **Settings** if you expose HTTP/SSE later.

## Troubleshooting

| Symptom | Try |
|---------|-----|
| Tools time out | Is Blender open? Is the addon connected (N-Panel status)? |
| Empty scene summary | Select something in Blender or wait for the bridge hello |
| Module not found | Activate the sidecar venv / fix `cwd` |

Need help? [Open an issue](https://github.com/kakajan/blenderAI/issues) or reach [@kakajan](https://github.com/kakajan) — we’re happy to walk through your setup.
