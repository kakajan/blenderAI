# اسکیل‌ها

اسکیل‌های داخلی در `/skills/*.yaml` هستند؛ می‌توانید **اسکیل سفارشی** هم بسازید.

English: [skills.md](skills.md)

## ساختار

```yaml
id: domain.action
version: 1
name: Human Name
domains: [modeling]
tools: [scene.create_object]
system_prompt: presets/path.md
risk: low|medium|high
requires_confirmation: false
viewport_capture: false|optional|required
description: توضیح کوتاه
```

## افزودن از WebUI (پیشنهادی)

1. Chat UI → **Skills**.
2. **Add skill** / **افزودن اسکیل**.
3. نام، ابزارها و پرامپت سیستم را پر کنید.
4. ذخیره — اسکیل در «اسکیل‌های شما» و در انتخابگر چت ظاهر می‌شود.

مسیر ذخیره:

| سیستم | مسیر |
|-------|------|
| ویندوز | `%APPDATA%\BlenderAI\user_skills\` |
| macOS | `~/Library/Application Support/BlenderAI/user_skills/` |
| لینوکس | `~/.local/share/BlenderAI/user_skills/` |

هر اسکیل یک YAML به‌همراه `prompts/<id>.md` است.

## افزودن با فایل

1. فایل `user.my_skill.yaml` را در `user_skills` بگذارید.
2. پرامپت را در `user_skills/prompts/user.my_skill.md` بنویسید.
3. در WebUI روی **Reload** بزنید (یا Sidecar را ری‌استارت کنید).

## اسکیل داخلی (ریپو)

1. YAML را در `skills/` بگذارید.
2. پرامپت را در `presets/` بسازید یا دوباره استفاده کنید.
3. Sidecar را ری‌استارت کنید.
4. ابزارهای متناظر در افزونه allowlist شده باشند.

## اشتراک‌گذاری

یک پوشه کوچک (YAML + prompt) بسازید و PR بفرستید.
