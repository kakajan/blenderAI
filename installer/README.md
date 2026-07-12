# BlenderAI Installer

Cross-platform graphical installer for **Windows**, **macOS**, and **Linux**.

The UI and scripts are **English-only**.

## Run

| OS | Command |
|----|---------|
| Windows | `Install.bat` |
| macOS | double-click `Install.command` or `./Install.sh` |
| Linux | `./Install.sh` |
| Any | `python install.py` |
| CLI | `python install.py --cli` |

## Requirements

- Python **3.11+**
- Blender **4.2+**
- Optional: Node.js 20+ (to build WebUI; otherwise uses existing `webui/dist`)
- Linux GUI: `python3-tk` for the graphical UI

## What it installs

1. Extension → Blender `extensions/user_default/blender_ai`
2. **Enable** BlenderAI in Blender preferences (CLI `install-file --enable`, then background Python fallback)
3. Sidecar → platform data dir (`%APPDATA%\BlenderAI`, macOS Application Support, or `~/.local/share/BlenderAI`)
4. WebUI static files
5. Desktop / app-menu shortcut
6. **Cursor MCP** — registers `blender-ai` in `~/.cursor/mcp.json` (restart Cursor after install)

After install: restart Blender and use the **BlenderAI** N-Panel (no manual Enable needed if auto-enable succeeded).

- Repository: [github.com/kakajan/blenderAI](https://github.com/kakajan/blenderAI)
- Author: [@kakajan](https://github.com/kakajan) — AsherQelich SayyedMuhammadi

See the main [README](../README.md) for full usage. فارسی: [README.fa.md](../README.fa.md)
