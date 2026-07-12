# راهنمای MCP

Cursor، Claude Desktop یا هر کلاینت MCP را از طریق sidecar به **جلسه زنده بلندر** وصل کنید.

English: [mcp.md](mcp.md)

## پیش‌نیاز

1. بلندر باز باشد و افزونه **BlenderAI** فعال باشد.
2. Sidecar در حال اجرا باشد.
3. برای نوشتن روی صحنه، سطح خودمختاری را در WebUI درست تنظیم کنید.

## نمونه Cursor

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

در macOS/لینوکس مسیر `cwd` یا مفسر venv را مطابق سیستم خود بگذارید.

## ابزارها

| ابزار | توضیح |
|------|--------|
| `blender_status` | وضعیت اتصال |
| `scene_summary` | خلاصه صحنه |
| `viewport_capture` | تصویر ویوپورت |
| `invoke_tool` | اجرای مستقیم ابزار bridge |
| `execute_skill` | آماده‌سازی اسکیل برای **Cursor (delegated)** — پیش‌فرض |
| `chat` | آماده‌سازی نوبت چت برای **Cursor (delegated)** — پیش‌فرض |
| `list_objects` | لیست آبجکت‌ها |
| `undo` / `redo` | تاریخچه |

## Cursor به‌عنوان provider (حالت delegated)

در Cursor، `chat` و `execute_skill` به‌طور پیش‌فرض `provider_id: cursor` دارند. sidecar به Ollama/OpenAI وصل نمی‌شود؛ پاسخ **delegated** از `/api/mcp/prepare` برمی‌گردد (پرامپت سیستم، `allowed_tools`، خلاصه صحنه). سپس Cursor باید با `invoke_tool` ابزارهای بلندر را اجرا کند. برای LLM جداگانه، `provider_id` را صریح بگذارید (مثلاً `ollama`).

## نکات ایمنی

- اول با ابزارهای خواندنی شروع کنید.
- اگر نمی‌خواهید کلود درگیر شود، **Local Only** را روشن کنید.
- توکن MCP را از Settings در WebUI بچرخانید.

## عیب‌یابی

| مشکل | کار پیشنهادی |
|------|----------------|
| `All providers failed` در `execute_skill` / `chat` | sidecar را نصب/ری‌استارت کنید تا MCP پیش‌فرض `cursor` شود؛ یا `provider_id: "cursor"` بدهید |
| Timeout | بلندر باز است؟ وضعیت N-Panel چیست؟ |
| خلاصه خالی | چیزی را در صحنه انتخاب کنید |
| Module not found | venv sidecar را فعال کنید |

سؤال داشتید؟ [Issue](https://github.com/kakajan/blenderAI/issues) باز کنید یا به [@kakajan](https://github.com/kakajan) پیام دهید — با کمال میل کمک می‌کنیم.
