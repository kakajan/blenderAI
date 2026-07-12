# مشارکت در BlenderAI

از اینکه به فکر مشارکت هستید ممنونیم. لازم نیست متخصص باشید — Issue شفاف، PR کوچک و بازبینی مهربانانه همه به پروژه کمک می‌کنند.

> English: [CONTRIBUTING.md](CONTRIBUTING.md) · راهنما: [GUIDE.fa.md](GUIDE.fa.md) · معرفی: [README.fa.md](README.fa.md)

| | |
|--|--|
| **ریپوزیتوری** | [github.com/kakajan/blenderAI](https://github.com/kakajan/blenderAI) |
| **نویسنده** | [AsherQelich SayyedMuhammadi](https://github.com/kakajan) (`@kakajan`) |
| **Issues / PR** | [Issues](https://github.com/kakajan/blenderAI/issues) · [Pull requests](https://github.com/kakajan/blenderAI/pulls) |
| **وب‌سایت** | [kakajan.github.io/blenderAI](https://kakajan.github.io/blenderAI/) |

## چطور کمک کنید

| حوزه | مثال |
|------|------|
| Skills | اسکیل YAML جدید + پریست برای اسکالپت، نود، ریگ، VFX |
| Providers | آداپتر، retry، پیام خطای بهتر، تست |
| WebUI | دسترسی‌پذیری، RTL، پرفورمنس، طراحی |
| Extension | ابزار امن‌تر، کانتکست صحنه بهتر، سازگاری نسخه بلندر |
| Docs | آموزش، GIF، ترجمه، نکات کاربردی |
| امنیت | بررسی allowlist، سخت‌سازی MCP، مدیریت کلید |

## راه‌اندازی توسعه

1. فورک و کلون کنید.
2. بخش **نصب دستی** در [README.fa.md](README.fa.md) را دنبال کنید.
3. تست sidecar:

```bash
cd sidecar
pip install -e ".[dev]"
pytest -q
```

4. WebUI:

```bash
cd webui
npm install
npm run build
```

## چک‌لیست Pull Request

- [ ] توضیح دهید **چرا** این تغییر به کاربر یا نگهدارنده کمک می‌کند
- [ ] دیف را متمرکز نگه دارید
- [ ] برای منطق sidecar در صورت نیاز تست اضافه/به‌روز کنید
- [ ] سکرت، `.env` یا کلید API شخصی commit نکنید
- [ ] با سبک کد موجود هماهنگ باشید
- [ ] اگر رفتار یا نصب عوض شد، مستندات را به‌روز کنید

## رفتار محترمانه

با احترام باشید. نیت خوب فرض کنید. آزار، اسپم یا دروازه‌بانی خصمانه جایی ندارد. برای هنرمندان و TDها ابزار می‌سازیم — لحن حمایتی بماند.

## امنیت

اگر آسیب‌پذیری پیدا کردید (مخصوصاً اجرای ابزار یا MCP write)، به‌جای انتشار عمومی PoC، از advisory خصوصی یا ایمیل به نگهدارندگان استفاده کنید.

## مجوز

با مشارکت، کار شما تحت [مجوز MIT](LICENSE) پروژه منتشر می‌شود.

---

سؤال دارید؟ [Issue](https://github.com/kakajan/blenderAI/issues) با برچسب `question` باز کنید یا به [@kakajan](https://github.com/kakajan) پیام دهید. خوشحالیم که اینجایی.
