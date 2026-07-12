# راهنمای MCP

**Cursor**، **Claude Desktop**، **Claude Code**، **Windsurf**، **VS Code**، **Cline**، **Continue** یا هر کلاینت MCP دیگر را از طریق sidecar به **جلسه زنده بلندر** وصل کنید.

English: [mcp.md](mcp.md)

## پیش‌نیاز

1. بلندر باز باشد و افزونه **BlenderAI** فعال باشد.
2. Sidecar در حال اجرا باشد.
3. برای نوشتن روی صحنه، سطح خودمختاری را در WebUI درست تنظیم کنید.

## راه‌اندازی سریع (اینستالر)

با گزینه MCP در اینستالر، این کلاینت‌ها در صورت وجود پوشهٔ تنظیمات ثبت می‌شوند:

| کلاینت | فایل تنظیمات |
|--------|---------------|
| **Cursor** | `~/.cursor/mcp.json` |
| **Claude Desktop** | مسیر جدول زیر |
| **Claude Code** | `~/.claude.json` |
| **Windsurf** | `~/.codeium/windsurf/mcp_config.json` |
| **Cline** | `cline_mcp_settings.json` (اگر نصب باشد) |

بعد از نصب، هر اپ را ری‌استارت کنید.

نمونه‌های دستی در همین پوشه:

| کلاینت | فایل نمونه |
|--------|-------------|
| Cursor | [mcp.cursor.example.json](mcp.cursor.example.json) |
| Claude Desktop | [mcp.claude-desktop.example.json](mcp.claude-desktop.example.json) |
| Claude Code | [mcp.claude-code.example.json](mcp.claude-code.example.json) |
| Windsurf | [mcp.windsurf.example.json](mcp.windsurf.example.json) |
| VS Code | [mcp.vscode.example.json](mcp.vscode.example.json) |
| Cline | [mcp.cline.example.json](mcp.cline.example.json) |
| Continue | [mcp.continue.example.json](mcp.continue.example.json) |

`REPLACE_WITH_SIDECAR_VENV_PYTHON` و `REPLACE_WITH_SIDECAR_DIR` را با مسیر نصب خود عوض کنید (معمولاً `%APPDATA%\BlenderAI\sidecar` در ویندوز).

---

## Cursor

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

ترجیحاً مفسر venv sidecar را به‌جای `python` عمومی بگذارید.

---

## Claude Desktop

| سیستم | مسیر |
|--------|------|
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| ویندوز | `%APPDATA%\Claude\claude_desktop_config.json` |
| ویندوز (MSIX) | `%LOCALAPPDATA%\Packages\Claude_*\LocalCache\Roaming\Claude\claude_desktop_config.json` |
| لینوکس | `~/.config/Claude/claude_desktop_config.json` |

در اپ: **Settings → Developer → Edit Config** و بلوک `mcpServers` را اضافه کنید. مسیرها مطلق باشند. Claude Desktop را کامل ببندید و دوباره باز کنید.

---

## Claude Code

در `~/.claude.json` (کاربر) یا `.mcp.json` (پروژه) همان بلوک `mcpServers` را بگذارید. یا:

```bash
claude mcp add blender-ai -- /path/to/sidecar/.venv/bin/python -m blender_ai_sidecar.main mcp --stdio
```

---

## Windsurf / VS Code / Cline / Continue

- **Windsurf:** `~/.codeium/windsurf/mcp_config.json` — شکل Cursor
- **VS Code:** `.vscode/mcp.json` با کلید `servers` و `"type": "stdio"` — [mcp.vscode.example.json](mcp.vscode.example.json)
- **Cline:** تنظیمات MCP داخل افزونه — [mcp.cline.example.json](mcp.cline.example.json)
- **Continue:** [mcp.continue.example.json](mcp.continue.example.json)

---

## ابزارها

| ابزار | توضیح |
|------|--------|
| `blender_status` | وضعیت اتصال |
| `scene_summary` | خلاصه صحنه |
| `viewport_capture` | تصویر ویوپورت |
| `invoke_tool` | اجرای مستقیم ابزار bridge |
| `execute_skill` | آماده‌سازی اسکیل (در Cursor: delegated) |
| `chat` | آماده‌سازی نوبت چت (در Cursor: delegated) |
| `list_objects` | لیست آبجکت‌ها |
| `undo` / `redo` | تاریخچه |

## Cursor به‌عنوان provider (حالت delegated)

در Cursor، `chat` و `execute_skill` به‌طور پیش‌فرض `provider_id: cursor` دارند. در **Claude Desktop و بقیه** از `invoke_tool` مستقیم استفاده کنید، یا `provider_id` را صریح بگذارید (مثلاً `ollama`).

## نکات ایمنی

- اول با ابزارهای خواندنی شروع کنید.
- اگر نمی‌خواهید کلود درگیر شود، **Local Only** را روشن کنید.
- توکن MCP را از Settings در WebUI بچرخانید.

## عیب‌یابی

| مشکل | کار پیشنهادی |
|------|----------------|
| سرور در کلاینت نیست | بعد از ویرایش config، کلاینت را ری‌استارت کنید؛ مسیر مطلق |
| Claude Desktop در ویندوز | مسیر MSIX زیر Packages را هم چک کنید |
| `All providers failed` | `provider_id` صریح بدهید؛ delegated فقط در Cursor است |
| Timeout | بلندر باز است؟ وضعیت N-Panel چیست؟ |
| Module not found | venv sidecar و `cwd` را درست کنید |

سؤال داشتید؟ [Issue](https://github.com/kakajan/blenderAI/issues) باز کنید یا به [@kakajan](https://github.com/kakajan) پیام دهید.
