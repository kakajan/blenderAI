# اسکیل‌ها

اسکیل‌ها در `/skills/*.yaml` هستند و به پرامپت‌های `/presets` ارجاع می‌دهند.

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

## افزودن اسکیل

1. YAML را در `skills/` بگذارید.
2. پرامپت سیستم را در `presets/` بسازید یا دوباره استفاده کنید.
3. Sidecar را ری‌استارت کنید.
4. ابزارهای متناظر در افزونه allowlist شده باشند.

## اشتراک‌گذاری

یک پوشه کوچک (YAML + preset) بسازید و PR بفرستید — پک‌های اسکیل جامعه بهترین راه رشد BlenderAI هستند.
