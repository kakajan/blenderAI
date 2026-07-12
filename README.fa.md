# BlenderAI

**همکار هوش مصنوعی شما داخل بلندر — وقتی بخواهید خصوصی، وقتی لازم باشد قدرتمند.**

BlenderAI بلندر را به مدل‌های محلی و ابری وصل می‌کند (Ollama، OpenAI، Claude، DeepSeek، Qwen، GLM، OpenCode Zen و هر API سازگار با OpenAI). از **N-Panel داخل خود بلندر** چت کنید، با **Skills** مدلینگ و متریال و نور بسازید، و از Cursor با **MCP** صحنهٔ زنده را کنترل کنید. WebUI مرورگر برای Providers و صفحات پیشرفته اختیاری است.

> English: [README.md](README.md) · راهنما: [GUIDE.fa.md](GUIDE.fa.md) · مشارکت: [CONTRIBUTING.fa.md](CONTRIBUTING.fa.md)

| | |
|--|--|
| **ریپوزیتوری** | [github.com/kakajan/blenderAI](https://github.com/kakajan/blenderAI) |
| **نویسنده** | [AsherQelich SayyedMuhammadi](https://github.com/kakajan) (`@kakajan`) |
| **Issues** | [ثبت مشکل یا ایده](https://github.com/kakajan/blenderAI/issues) |
| **وب‌سایت** | [kakajan.github.io/blenderAI](https://kakajan.github.io/blenderAI/) |
| **مجوز** | [MIT](LICENSE) |

### نقشهٔ کوتاه مستندات

| نیاز | فارسی | English |
|------|--------|---------|
| معرفی (همین فایل) | [README.fa.md](README.fa.md) | [README.md](README.md) |
| راهنمای گام‌به‌گام | [GUIDE.fa.md](GUIDE.fa.md) | [GUIDE.md](GUIDE.md) |
| مشارکت | [CONTRIBUTING.fa.md](CONTRIBUTING.fa.md) | [CONTRIBUTING.md](CONTRIBUTING.md) |
| معماری / MCP / Skills | [docs/](docs/) | همان پوشه (`*.md`) |

---

## چرا BlenderAI؟

- **کنترل دست شماست** — کلیدها روی دستگاه خودتان می‌مانند؛ حالت Local Only کلود را قفل می‌کند.
- **آفلاین کار می‌کند** — اولویت با Ollama برای استودیوهای خصوصی.
- **برای کار واقعی** — اسکیل، پریست، ابزارهای سازگار با Undo، و پنل جمع‌وجور داخل بلندر.
- **باز و دوستانه** — مجوز MIT. ایده، باگ‌فیکس و اسکیل جدید واقعاً خوشحال‌مان می‌کند.

---

## پیش‌نیازها

| ابزار | نسخه |
|------|------|
| Blender | **4.2+** |
| Python | **3.11+** (برای sidecar) |
| Node.js | **20+** (اختیاری؛ برای بیلد WebUI) |
| Ollama | اختیاری، برای مدل محلی |

سیستم‌عامل‌ها: **ویندوز**، **macOS**، **لینوکس**.

---

## شروع سریع (پیشنهادی)

### ۱. اجرای اینستالر

**ویندوز**

```bat
installer\Install.bat
```

**macOS / لینوکس**

```bash
chmod +x installer/Install.sh
./installer/Install.sh
```

یا در هر سیستم‌عامل:

```bash
python installer/install.py
# بدون GUI: python installer/install.py --cli
```

اینستالر بلندر را پیدا می‌کند، افزونه را نصب می‌کند و Sidecar + WebUI را در پوشهٔ دادهٔ کاربر آماده می‌کند.

### ۲. ری‌استارت بلندر

بلندر را باز کنید → در ویوپورت سه‌بعدی تب **BlenderAI** را در N-Panel ببینید (`N`).

### ۳. چت در N-Panel

در تب **BlenderAI** سایدبار، پرامپت بنویسید و **Send** بزنید. چت داخل خود بلندر اجرا می‌شود.

برای Providers / History / Skills در UI بزرگ‌تر، **Open in browser** را بزنید (یا [http://127.0.0.1:8765](http://127.0.0.1:8765)).

### ۴. اتصال مدل

به **Providers** بروید:

1. **Ollama** (محلی) و/یا یک ارائه‌دهنده ابری را فعال کنید.
2. Base URL / کلید API را وارد کنید.
3. **Test Connection** را بزنید.
4. مدل پیش‌فرض را تنظیم کنید.

حالا می‌توانید با زبان طبیعی مش، متریال و نور بسازید.

---

## استفاده روزمره

### داخل بلندر (N-Panel)

| عمل | کار |
|-----|-----|
| **Chat → Send** | گفتگو با صحنه از داخل بلندر |
| **Chat → Stop / New Chat** | توقف تولید یا پاک‌کردن تاریخچه |
| Providers (browser) | تنظیمات اتصال AI در WebUI |
| Capture | تصویر ویوپورت برای vision / نقد |
| Undo AI | برگرداندن آخرین گروه ابزار AI |
| Open in browser | WebUI اختیاری (Providers، History، Skills) |
| Start / Stop | کنترل سرویس محلی Sidecar |

### در WebUI (اختیاری)

| تب | کاربرد |
|----|--------|
| **Chat** | گفتگو با صحنه؛ انتخاب ارائه‌دهنده، مدل و اسکیل |
| **Skills** | اسکیل‌های داخلی و **ساخت اسکیل سفارشی** |
| **Presets** | پرامپت و ورک‌فلو آماده |
| **Providers** | همهٔ تنظیمات اتصال AI |
| **History** | تاریخچه گفتگو |
| **Settings** | زبان (EN/FA)، جهت متن (LTR/RTL)، خودمختاری، توکن MCP |

**نکته:** زبان و جهت نمایش مستقل‌اند — می‌توانید UI انگلیسی با چیدمان RTL داشته باشید.

### سطح خودمختاری

- **Ask** — تأیید برای کارهای پرریسک  
- **Auto-safe** — اجرای خودکار ابزارهای امن  
- **Auto-full** — اجرای ابزارهای allowlisted بدون پرسش  

### مدل‌سازی پیشرفته (Surface / Edge-Based)

برای کاراکتر و آبجکت‌های جزئیات‌دار، BlenderAI دیگر فقط پریمیتیو نمی‌چیند. در **شروع هر چت** یک **Modeling Strategy** انتخاب می‌شود — بهترین ترکیب روش‌ها برای همان درخواست:

| روش | مثال ترکیب |
|-----|------------|
| **Hybrid blockout + surface** | cube → `mesh.extrude` → SUBSURF → `mesh.from_data` |
| **Sculpt + mesh edit** | box → SUBSURF → `sculpt.remesh` → bevel/inset |
| **Hard-surface** | blockout → loop/bevel → BOOLEAN → BEVEL modifier |
| **Reference turnaround** | surface build → capture سه‌نما → اصلاح → متریال |

**اسکیل‌های پیشنهادی:** `modeling.surface_advanced`، `workflow.surface_character`، `modeling.character_stylized`

**ابزارهای جدید bridge:** `mesh.extrude`، `mesh.edge_loop`، `mesh.profile_extrude`، انتخاب معنایی در `mesh.select` (`top_cap`، `by_normal`، `boundary`)

بعد از addon reload در Blender، ابزارها فعال می‌شوند. جزئیات: [docs/mcp.md](docs/mcp.md)

---

## نصب دستی (توسعه‌دهندگان)

### Sidecar

```bash
cd sidecar
python -m venv .venv
# ویندوز: .venv\Scripts\activate
source .venv/bin/activate
pip install -e ".[dev]"
python -m blender_ai_sidecar.main serve
```

### WebUI (توسعه)

```bash
cd webui
npm install
npm run dev
```

### افزونه

در بلندر: **Edit → Preferences → Get Extensions → Install from Disk** → فایل
`%APPDATA%\BlenderAI\cache\blender_ai_extension.zip` (یا پوشهٔ `extension/`) را انتخاب کنید → در تب **Add-ons** افزونهٔ **BlenderAI** را Enable کنید.

---

## MCP (Cursor و ایجنت‌های دیگر)

راهنمای کامل: [docs/mcp.md](docs/mcp.md) · فارسی: [docs/mcp.fa.md](docs/mcp.fa.md)

بلندر باید باز باشد، افزونه فعال، و sidecar در حال اجرا.

---

## ساختار پروژه

| مسیر | نقش |
|------|-----|
| `extension/` | افزونه بلندر |
| `sidecar/` | سرویس AI / MCP |
| `webui/` | رابط چت و Providers |
| `installer/` | اینستالر چندسکویی |
| `skills/` | تعریف اسکیل‌ها |
| `presets/` | پرامپت و ورک‌فلو |
| `docs/` | مستندات |

---

## حریم خصوصی

| سیستم | پوشه داده |
|--------|-----------|
| ویندوز | `%APPDATA%\BlenderAI` |
| macOS | `~/Library/Application Support/BlenderAI` |
| لینوکس | `~/.local/share/BlenderAI` |

کلیدها در keyring سیستم ذخیره می‌شوند؛ هرگز داخل فایل `.blend` نیستند.

---

## مشارکت

کمک شما ارزشمند است — از یک اسکیل کوچک تا یک باگ‌فیکس.

1. مسیر خوش‌حال کاربر را در [GUIDE.fa.md](GUIDE.fa.md) ببینید.
2. [CONTRIBUTING.fa.md](CONTRIBUTING.fa.md) را دنبال کنید (English: [CONTRIBUTING.md](CONTRIBUTING.md)).
3. برای ایده یا باگ Issue باز کنید، سپس Pull Request متمرکز بفرستید.

**به‌خصوص خوشحال می‌شویم از**

- اسکیل‌های جدید (اسکالپت، GeoNodes، ریگ، کامپوزیت)
- آداپتر ارائه‌دهنده و تست
- پولیش UI/UX و دسترسی‌پذیری
- مستندات، ترجمه و آموزش
- بررسی امنیتی allowlist و MCP

---

## حمایت از پروژه

اگر BlenderAI وقتتان را ذخیره کرده:

- به [ریپوزیتوری](https://github.com/kakajan/blenderAI) ستاره بدهید و با استودیو/دوستانتان به اشتراک بگذارید
- باگ را در [Issues](https://github.com/kakajan/blenderAI/issues) با نسخه بلندر و سیستم‌عامل گزارش کنید
- نویسنده: [@kakajan](https://github.com/kakajan) — AsherQelich SayyedMuhammadi
- اگر لینک حمایت منتشر شد، هر کمکی چراغ پروژه را روشن نگه می‌دارد
- همکاری قراردادی که به بهبود متن‌باز کمک کند همیشه قابل گفتگوست

ممنون که اینجایی. ابزار خلاق باید شریک باشد، نه مانع.

---

## مجوز

[MIT](LICENSE) — Copyright © 2026 [AsherQelich SayyedMuhammadi](https://github.com/kakajan). استفاده کنید، فورک کنید، روی آن بسازید.

---

**BlenderAI** — [github.com/kakajan/blenderAI](https://github.com/kakajan/blenderAI) · امروز چیزی زیبا بساز.
