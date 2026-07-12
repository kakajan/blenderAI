# BlenderAI

**Your AI co-pilot inside Blender — private when you want, powerful when you need it.**

BlenderAI connects Blender to local and cloud models (Ollama, OpenAI, Claude, DeepSeek, Qwen, GLM, OpenCode Zen, and any OpenAI-compatible API). Chat from the **N-Panel inside Blender**, run domain **Skills** for modeling, materials, lighting, and more, and control a live scene from Cursor via **MCP**. The browser WebUI is optional for Providers and richer screens.

> فارسی: [README.fa.md](README.fa.md) · User guide: [GUIDE.md](GUIDE.md) · Contributing: [CONTRIBUTING.md](CONTRIBUTING.md)

| | |
|--|--|
| **Repository** | [github.com/kakajan/blenderAI](https://github.com/kakajan/blenderAI) |
| **Author** | [AsherQelich SayyedMuhammadi](https://github.com/kakajan) (`@kakajan`) |
| **Issues** | [Open an issue](https://github.com/kakajan/blenderAI/issues) |
| **Website** | [kakajan.github.io/blenderAI](https://kakajan.github.io/blenderAI/) |
| **License** | [MIT](LICENSE) |

### Docs at a glance

| Need | English | فارسی |
|------|---------|--------|
| Overview (this file) | [README.md](README.md) | [README.fa.md](README.fa.md) |
| Step-by-step guide | [GUIDE.md](GUIDE.md) | [GUIDE.fa.md](GUIDE.fa.md) |
| Contributing | [CONTRIBUTING.md](CONTRIBUTING.md) | [CONTRIBUTING.fa.md](CONTRIBUTING.fa.md) |
| Architecture / MCP / Skills | [docs/](docs/) | same folder (`*.fa.md`) |

---

## Why BlenderAI?

- **You stay in control** — API keys stay on your machine; Local Only mode locks cloud providers.
- **Works offline** — Ollama-first for private studios and air-gapped setups.
- **Built for real pipelines** — Skills, presets, undo-friendly tools, and a Blender N-Panel that stays out of your way.
- **Open & welcoming** — MIT licensed. Ideas, fixes, and new skills are genuinely appreciated.

---

## Requirements

| Tool | Version |
|------|---------|
| Blender | **4.2+** |
| Python | **3.11+** (sidecar) |
| Node.js | **20+** (optional; to rebuild WebUI) |
| Ollama | Optional, for local models |

Supported platforms: **Windows**, **macOS**, **Linux**.

---

## Quick start (recommended)

### 1. Run the installer

**Windows**

```bat
installer\Install.bat
```

**macOS / Linux**

```bash
chmod +x installer/Install.sh
./installer/Install.sh
```

Or from any OS:

```bash
python installer/install.py
# headless: python installer/install.py --cli
```

The installer finds Blender, installs the extension, and sets up the Sidecar + WebUI in your user data folder.

### 2. Restart Blender

Open Blender → look for the **BlenderAI** tab in the 3D Viewport N-Panel (press `N`).

### 3. Chat in the N-Panel

In the **BlenderAI** sidebar tab, type a prompt and click **Send**. Chat runs inside Blender.

For Providers / History / Skills in a larger UI, use **Open in browser** (or visit [http://127.0.0.1:8765](http://127.0.0.1:8765)).

### 4. Connect a model

Go to **Providers**:

1. Enable **Ollama** (local) and/or a cloud provider.
2. Enter Base URL / API key.
3. Click **Test Connection**.
4. Set a default model.

You’re ready to create meshes, materials, and lighting with natural language.

---

## Everyday usage

Full walkthrough (install → providers → skills → MCP → troubleshooting): **[GUIDE.md](GUIDE.md)**.

### In Blender (N-Panel)

| Action | What it does |
|--------|----------------|
| **Chat → Send** | Talk to the scene from inside Blender |
| **Chat → Stop / New Chat** | Cancel generation or clear history |
| Providers (browser) | Opens AI connection settings in the WebUI |
| Capture | Sends a viewport snapshot for vision / critique skills |
| Undo AI | Undoes the last AI tool group |
| Open in browser | Optional rich WebUI (Providers, History, Skills) |
| Start / Stop | Controls the local Sidecar service |

### In the WebUI (optional)

| Tab | Purpose |
|-----|---------|
| **Chat** | Talk to the scene; pick provider, model, and skill |
| **Skills** | Browse built-in skills and **create your own** |
| **Presets** | Ready-made prompts and workflows |
| **Providers** | All AI connection settings (the source of truth) |
| **History** | Past conversations |
| **Settings** | Language (EN/FA), text direction (LTR/RTL), autonomy, MCP token |

**Tip:** Language and text direction are independent — you can keep English UI with RTL layout if you prefer.

### Autonomy levels

- **Ask** — confirm riskier actions  
- **Auto-safe** — run safe tools automatically  
- **Auto-full** — run allowlisted tools without prompts  

---

## Manual setup (developers)

### Sidecar

```bash
cd sidecar
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate   # macOS / Linux
pip install -e ".[dev]"
python -m blender_ai_sidecar.main serve
```

Health check: [http://127.0.0.1:8765/health](http://127.0.0.1:8765/health)

### WebUI (dev)

```bash
cd webui
npm install
npm run dev
```

### Extension

In Blender: **Edit → Preferences → Get Extensions → Install from Disk** → select
`%APPDATA%\BlenderAI\cache\blender_ai_extension.zip` (or the `extension/` folder) → enable **BlenderAI** in the **Add-ons** tab.

---

## MCP (Cursor, Claude Desktop & other agents)

Control the **same open Blender scene** from Cursor, Claude Desktop, Claude Code, Windsurf, VS Code, Cline, Continue, or any MCP client.

The **installer configures MCP clients automatically** (Cursor, Claude Desktop, Claude Code, …) — restart each app after install.

See the full guide and example JSON files: [docs/mcp.md](docs/mcp.md)

Keep Blender open with the addon enabled and the sidecar running.

---

## Project layout

| Path | Role |
|------|------|
| `extension/` | Blender 4.2+ extension (N-Panel, bridge, tools) |
| `sidecar/` | Local AI router, chat agent, skills, MCP server |
| `webui/` | Chat + Providers UI |
| `installer/` | Cross-platform graphical installer |
| `skills/` | Skill definitions (YAML) |
| `presets/` | System prompts & workflows |
| `docs/` | Architecture & guides |

More detail: [docs/architecture.md](docs/architecture.md) · [docs/skills.md](docs/skills.md)

---

## Data & privacy

| Platform | Data directory |
|----------|----------------|
| Windows | `%APPDATA%\BlenderAI` |
| macOS | `~/Library/Application Support/BlenderAI` |
| Linux | `~/.local/share/BlenderAI` |

- API keys are stored via the OS keyring (never in `.blend` files).
- Scene context is only sent to cloud models when you choose to use those providers.
- **Local Only** in Providers disables cloud endpoints.

---

## Contributing

We’d love your help — whether you ship one skill, fix a typo, or redesign a flow.

1. Read the user [GUIDE.md](GUIDE.md) so you know the happy path.
2. Follow [CONTRIBUTING.md](CONTRIBUTING.md) (فارسی: [CONTRIBUTING.fa.md](CONTRIBUTING.fa.md)).
3. Open an issue for bugs or ideas, then send a focused pull request.

**Especially welcome**

- New skills (sculpt, geo nodes, rigging, compositing)
- Provider adapters and tests
- UI/UX polish and accessibility
- Docs, translations, and tutorials
- Security reviews of the tool allowlist / MCP surface

---

## Support the project

If BlenderAI saves you time:

- [Star the repository](https://github.com/kakajan/blenderAI) and share it with your studio
- [Report bugs](https://github.com/kakajan/blenderAI/issues) with clear steps (Blender version + OS help a lot)
- Follow / reach the author: [@kakajan](https://github.com/kakajan) — AsherQelich SayyedMuhammadi
- Sponsor or donate if we publish a support link — every bit keeps the lights on
- Hire / contract work that funds open improvements is always welcome to discuss

Thank you for being here. Creative tools should feel like partners, not obstacles.

---

## License

[MIT](LICENSE) — Copyright © 2026 [AsherQelich SayyedMuhammadi](https://github.com/kakajan). Use it, fork it, build on it.

---

**BlenderAI** — [github.com/kakajan/blenderAI](https://github.com/kakajan/blenderAI) · make something beautiful today.
