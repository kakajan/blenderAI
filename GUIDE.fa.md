# راهنمای کاربری BlenderAI

راهنمای عملی نصب، چت، اسکیل، Providers و MCP.

> English: [GUIDE.md](GUIDE.md) · معرفی: [README.fa.md](README.fa.md) · مشارکت: [CONTRIBUTING.fa.md](CONTRIBUTING.fa.md)

| | |
|--|--|
| **ریپوزیتوری** | [github.com/kakajan/blenderAI](https://github.com/kakajan/blenderAI) |
| **وب‌سایت** | [kakajan.github.io/blenderAI](https://kakajan.github.io/blenderAI/) |
| **نویسنده** | [AsherQelich SayyedMuhammadi](https://github.com/kakajan) (`@kakajan`) |

---

## ۱. چه چیزی دریافت می‌کنید

| بخش | کار |
|-----|-----|
| **افزونه بلندر** | چت N-Panel، کپچر ویوپورت، Undo AI، پل به sidecar |
| **Sidecar** | روتر AI محلی روی `http://127.0.0.1:8765` — ارائه‌دهنده، اسکیل، MCP |
| **WebUI** (اختیاری) | صفحات بزرگ‌تر Providers / Chat / History / Skills در مرورگر |
| **MCP** | همان صحنه زنده از Cursor یا کلاینت‌های MCP دیگر |

طرح معماری:

```text
N-Panel / WebUI  →  HTTP/SSE  →  Sidecar :8765  →  WebSocket tools  →  Blender
```

چت می‌تواند بدون بلندر جواب دهد. **ساخت یا ویرایش آبجکت** نیاز به افزونه فعال و `"blender_connected": true` در `/health` دارد.

---

## ۲. نصب (پیشنهادی)

### پیش‌نیازها

- بلندر **۴.۲+**
- پایتون **۳.۱۱+** (sidecar؛ معمولاً اینستالر مدیریت می‌کند)
- اختیاری: [Ollama](https://ollama.com) برای مدل محلی
- اختیاری: Node.js **۲۰+** فقط اگر خودتان WebUI را بیلد می‌کنید

### اجرای اینستالر

**ویندوز**

```bat
installer\Install.bat
```

**macOS / لینوکس**

```bash
chmod +x installer/Install.sh
./installer/Install.sh
```

هر سیستم‌عامل:

```bash
python installer/install.py
# بدون GUI: python installer/install.py --cli
```

سپس:

1. بلندر را ری‌استارت کنید.
2. اگر لازم است، **BlenderAI** را در **Edit → Preferences → Add-ons** فعال کنید.
3. در ویوپورت سه‌بعدی `N` بزنید → تب **BlenderAI**.
4. سلامت را چک کنید: [http://127.0.0.1:8765/health](http://127.0.0.1:8765/health) — باید `"blender_connected": true` باشد.

پوشه داده:

| سیستم | مسیر |
|--------|------|
| ویندوز | `%APPDATA%\BlenderAI` |
| macOS | `~/Library/Application Support/BlenderAI` |
| لینوکس | `~/.local/share/BlenderAI` |

---

## ۳. اولین چت

1. در تب **BlenderAI** بنویسید چه می‌خواهید (مثلاً: *یک صندلی لوپولی بساز*).
2. **Send** را بزنید.
3. با **Stop** تولید را قطع کنید؛ با New Chat / پاک‌کردن، تاریخچه را ریست کنید.
4. **Undo AI** آخرین گروه ابزار AI را برمی‌گرداند.

برای Providers و تاریخچه غنی‌تر، **Open in browser** را بزنید (یا [http://127.0.0.1:8765](http://127.0.0.1:8765)).

---

## ۴. Providers و مدل‌ها

**Providers** را در مرورگر باز کنید:

1. **Ollama** و/یا ارائه‌دهنده ابری را فعال کنید.
2. Base URL و API key را وارد کنید.
3. **Test Connection** بزنید.
4. مدل پیش‌فرض را انتخاب کنید.

نکته‌ها:

- **Local Only** کلود را قفل می‌کند.
- کلیدها در keyring سیستم می‌مانند، نه داخل `.blend`.
- زبان و جهت متن مستقل‌اند — می‌توانید UI انگلیسی با RTL داشته باشید.

### سطح خودمختاری

| سطح | رفتار |
|-----|--------|
| **Ask** | تأیید اقدامات پرریسک |
| **Auto-safe** | ابزارهای امن خودکار |
| **Auto-full** | ابزارهای allowlist بدون تأیید |

---

## ۵. اسکیل و پریست

اسکیل‌ها YAML هستند (`skills/`). پریست‌ها در `presets/`.

- برای پایپ‌لاین متمرکز (بلاک‌اوت، هاردسرفیس، کاراکتر استایلایز و …) اسکیل را در Chat انتخاب کنید.
- در تب **Skills** وب‌یوآی می‌توانید اسکیل بسازید.
- جزئیات: [docs/skills.fa.md](docs/skills.fa.md)

---

## ۶. MCP (Cursor و ایجنت‌ها)

همان صحنه باز بلندر را از Cursor، Claude Desktop، Claude Code، Windsurf، VS Code، Cline یا هر کلاینت MCP کنترل کنید.

اینستالر می‌تواند تنظیمات MCP را برای **Cursor، Claude Desktop، Claude Code** و کلاینت‌های دیگر بنویسد. بعد از نصب هر اپ را ری‌استارت کنید.

بلندر باز، افزونه فعال، sidecar روشن. راهنما و فایل‌های نمونه: [docs/mcp.fa.md](docs/mcp.fa.md).

---

## ۷. نصب دستی / توسعه

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

**Edit → Preferences → Get Extensions → Install from Disk** → زیپ ساخته‌شده یا پوشه `extension/`. سپس **BlenderAI** را در Add-ons فعال کنید.

بیشتر: [docs/architecture.fa.md](docs/architecture.fa.md)

---

## ۸. عیب‌یابی

| نشانه | بررسی |
|--------|--------|
| چت کار می‌کند ولی چیزی در صحنه نیست | `/health` → `blender_connected`؛ افزونه فعال؛ N-Panel دیده شود |
| Sidecar بالا نمی‌آید | پورت `8765` آزاد؟ پایتون ۳.۱۱+؟ اینستالر را دوباره اجرا کنید |
| Providers fail | Test Connection؛ Base URL؛ Local Only |
| MCP بی‌حرکت | بلندر + افزونه + sidecar؛ بعد از تغییر MCP، Cursor را ری‌استارت کنید |
| افزونه enable نمی‌شود | بلندر ۴.۲+؛ زیپ flat؛ [installer/README.md](installer/README.md) |

هنوز گیر کردید؟ [Issue](https://github.com/kakajan/blenderAI/issues) با نسخه بلندر، سیستم‌عامل و خلاصه `/health` (بدون کلید API) باز کنید.

---

## ۹. نقشه مستندات

| سند | زبان |
|-----|------|
| [README.fa.md](README.fa.md) | FA · [EN](README.md) |
| [GUIDE.fa.md](GUIDE.fa.md) (همین فایل) | FA · [EN](GUIDE.md) |
| [CONTRIBUTING.fa.md](CONTRIBUTING.fa.md) | FA · [EN](CONTRIBUTING.md) |
| لندینگ GitHub Pages | [docs/](docs/) → [kakajan.github.io/blenderAI](https://kakajan.github.io/blenderAI/) |

---

**BlenderAI** — امروز چیزی زیبا بسازید.
