# کاتالوگ قابلیت BlenderAI

نسخه فارسی خلاصه. جدول کامل و به‌روز: [capability-catalog.md](capability-catalog.md)

## ایده

هر ردیف = **قصد کاربر** (مثلاً «پرتاب و برخورد توپ»)، نه نام خام `bpy.ops`.

سه لایه:

1. **Primitive** — ابزار allowlisted در Bridge
2. **Skill / recipe** — دستور پخت روی همان primitives
3. **Adaptive** — یادگیری شخصی و skill محلی بدون `exec` آزاد

## اولویت P0 فعلی

- انیمیشن کلیدی عمومی (`anim.keyframes`)
- نور استودیویی / دوربین follow
- introspect فقط‌خواندنی
- دانش `docs/blender-refs/`
- ثبت capability gap

## مرز امن

پلاگین در لحظه کد پایتون جدید داخل extension نمی‌نویسد و اجرا نمی‌کند.
به‌جای آن: ترکیب primitives + recipe/skill محلی + RAG مستندات.
