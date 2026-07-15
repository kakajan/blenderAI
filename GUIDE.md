# BlenderAI User Guide

Practical guide for installing, chatting, skills, providers, and MCP.

> فارسی: [GUIDE.fa.md](GUIDE.fa.md) · Overview: [README.md](README.md) · Contributing: [CONTRIBUTING.md](CONTRIBUTING.md)

| | |
|--|--|
| **Repository** | [github.com/kakajan/blenderAI](https://github.com/kakajan/blenderAI) |
| **Website** | [kakajan.github.io/blenderAI](https://kakajan.github.io/blenderAI/) |
| **Author** | [AsherQelich SayyedMuhammadi](https://github.com/kakajan) (`@kakajan`) |

---

## 1. What you get

| Piece | What it does |
|-------|----------------|
| **Blender extension** | N-Panel chat, viewport capture, undo AI, bridge to the sidecar |
| **Sidecar** | Local AI router on `http://127.0.0.1:8765` — providers, skills, MCP |
| **WebUI** (optional) | Larger Providers / Chat / History / Skills screens in the browser |
| **MCP** | Same live scene from Cursor or other MCP clients |

Architecture sketch:

```text
N-Panel / WebUI  →  HTTP/SSE  →  Sidecar :8765  →  WebSocket tools  →  Blender
```

Chat can answer without Blender. **Creating or editing objects requires** the extension enabled and `blender_connected: true` on `/health`.

---

## 2. Install (recommended)

### Requirements

- Blender **4.2+**
- Python **3.11+** (sidecar; installer usually handles this)
- Optional: [Ollama](https://ollama.com) for local models
- Optional: Node.js **20+** only if you rebuild the WebUI yourself

### Run the installer

**Windows**

```bat
installer\Install.bat
```

**macOS / Linux**

```bash
chmod +x installer/Install.sh
./installer/Install.sh
```

Any OS:

```bash
python installer/install.py
# headless: python installer/install.py --cli
```

Then:

1. Restart Blender.
2. Enable **BlenderAI** under **Edit → Preferences → Add-ons** if it is not already on.
3. Press `N` in the 3D Viewport → open the **BlenderAI** tab.
4. Check health: [http://127.0.0.1:8765/health](http://127.0.0.1:8765/health) — look for `"blender_connected": true`.

Data folder (keys, cache, install info):

| Platform | Path |
|----------|------|
| Windows | `%APPDATA%\BlenderAI` |
| macOS | `~/Library/Application Support/BlenderAI` |
| Linux | `~/.local/share/BlenderAI` |

---

## 3. First chat

1. In the N-Panel **BlenderAI** tab, type what you want (for example: *Create a low-poly chair*).
2. Click **Send**.
3. Use **Stop** to cancel generation, **New Chat** / clear to reset history.
4. **Undo AI** undoes the last AI tool group when tools ran in the scene.

For Providers and richer history, click **Open in browser** (or visit [http://127.0.0.1:8765](http://127.0.0.1:8765)).

---

## 4. Providers & models

Open **Providers** (browser):

1. Enable **Ollama** and/or a cloud provider (OpenAI, Claude, DeepSeek, Qwen, GLM, OpenCode Zen, or any OpenAI-compatible API).
2. Set Base URL and API key where needed.
3. Click **Test Connection**.
4. Pick a default model.

Tips:

- **Local Only** disables cloud endpoints — useful for private studios.
- API keys stay in the OS keyring, not in `.blend` files.
- You can keep English UI with RTL layout (or the reverse) — language and direction are independent in Settings.

### Autonomy

| Level | Behavior |
|-------|----------|
| **Ask** | Confirm riskier actions |
| **Auto-safe** | Run safe tools automatically |
| **Auto-full** | Run allowlisted tools without prompts |

---

## 5. Skills & presets

Skills are YAML workflows (modeling, materials, lighting, review, …) under `skills/`. Presets live in `presets/`.

- Pick a skill in Chat when you want a focused pipeline (blockout, hard-surface, stylized character, …).
- Browse and author skills in the WebUI **Skills** tab.
- Deeper reference: [docs/skills.md](docs/skills.md)

---

## 6. MCP (Cursor & agents)

Control the **same open Blender scene** from Cursor, Claude Desktop, Claude Code, Windsurf, VS Code, Cline, or any MCP client.

The installer can write MCP config for **Cursor, Claude Desktop, Claude Code**, and other clients when present (`~/.cursor/mcp.json`, `claude_desktop_config.json`, `~/.claude.json`, …). Restart each app after install.

Keep Blender open with the addon enabled and the sidecar running. Full guide + example JSON files: [docs/mcp.md](docs/mcp.md).

Example shape:

```json
{
  "mcpServers": {
    "blender-ai": {
      "command": "python",
      "args": ["-m", "blender_ai_sidecar.main", "mcp", "--stdio"],
      "cwd": "/path/to/blenderAI/sidecar"
    }
  }
}
```

---

## 7. Developer / manual setup

### Sidecar

```bash
cd sidecar
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate
pip install -e ".[dev]"
python -m blender_ai_sidecar.main serve
```

### WebUI (dev)

```bash
cd webui
npm install
npm run dev
```

### Extension

**Edit → Preferences → Get Extensions → Install from Disk** → select the built zip (often under the BlenderAI data `cache/` folder) or develop from `extension/`. Enable **BlenderAI** in Add-ons.

More: [docs/architecture.md](docs/architecture.md)

---

## 8. Troubleshooting

| Symptom | Check |
|---------|--------|
| Chat works, nothing appears in the scene | `/health` → `blender_connected` must be `true`; extension enabled; N-Panel visible |
| Sidecar won’t start | Prefer N-Panel **Start** (localhost works even if Allow Online Access is off). Port `8765` free? Re-run installer if `%APPDATA%\\BlenderAI\\sidecar` is missing. Or run **Start BlenderAI.bat** |
| Providers fail | Test Connection; Base URL; keyring permissions; Local Only off if you need cloud |
| MCP tools idle | Blender open + addon on + sidecar up; restart Cursor after MCP config changes |
| Extension won’t enable | Blender 4.2+; install from the flat extension zip; see [installer/README.md](installer/README.md) |

Still stuck? [Open an issue](https://github.com/kakajan/blenderAI/issues) with Blender version, OS, and a short `/health` snippet (no API keys).

---

## 9. Docs map

| Doc | Language |
|-----|----------|
| [README.md](README.md) | EN · [FA](README.fa.md) |
| [GUIDE.md](GUIDE.md) (this file) | EN · [FA](GUIDE.fa.md) |
| [CONTRIBUTING.md](CONTRIBUTING.md) | EN · [FA](CONTRIBUTING.fa.md) |
| [docs/architecture.md](docs/architecture.md) | EN · [FA](docs/architecture.fa.md) |
| [docs/mcp.md](docs/mcp.md) | EN · [FA](docs/mcp.fa.md) |
| [docs/skills.md](docs/skills.md) | EN · [FA](docs/skills.fa.md) |
| [docs/capability-catalog.md](docs/capability-catalog.md) | EN · [FA](docs/capability-catalog.fa.md) |
| Landing (GitHub Pages) | [docs/](docs/) → [kakajan.github.io/blenderAI](https://kakajan.github.io/blenderAI/) |

---

**BlenderAI** — make something beautiful today.
