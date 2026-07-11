# معماری

نمای کلی طراحی BlenderAI برای مشارکت‌کنندگان و کاربران کنجکاو.

English: [architecture.md](architecture.md)

## اجزا

1. **افزونه بلندر** — پنل، اپراتور، کانتکست صحنه، کلاینت WebSocket، صف ابزار روی main thread.
2. **Sidecar** — سرویس FastAPI برای ارائه‌دهنده‌ها، ایجنت چت، اسکیل، SQLite، MCP و WebUI استاتیک.
3. **WebUI** — چت و تنظیمات Providers.
4. **Skills / Presets** — تعریف YAML و markdown.

## جریان داده

```text
کاربر (WebUI یا MCP)
  → Router / Skill Engine
  → ToolCall JSON
  → صف افزونه
  → bpy + Undo
  → نتیجه → حلقه ایجنت
```

## پورت پیش‌فرض

`127.0.0.1:8765`

## اصول

- I/O شبکه UI بلندر را فریز نکند.
- ابزار allowlisted بر اجرای آزاد Python اولویت دارد.
- کلیدها در keyring سیستم.
- زبان پیش‌فرض محصول انگلیسی است؛ WebUI از فارسی و RTL مستقل پشتیبانی می‌کند.
