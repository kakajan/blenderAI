export type Lang = "en" | "fa";
export type UiDirection = "auto" | "ltr" | "rtl";

const dict = {
  en: {
    tagline: "Professional AI assistant for Blender",
    "nav.chat": "Chat",
    "nav.skills": "Skills",
    "nav.presets": "Presets",
    "nav.providers": "Providers",
    "nav.history": "History",
    "nav.settings": "Settings",
    "chat.title": "Chat",
    "chat.lead": "Talk to the live Blender scene and run tools.",
    "chat.placeholder": "e.g. Create a modern 120cm table…",
    "chat.send": "Send",
    "chat.provider": "Provider",
    "chat.model": "Model",
    "chat.skill": "Skill",
    "providers.title": "AI Connections",
    "providers.lead": "Configure keys, endpoints, and models entirely in this UI.",
    "providers.test": "Test Connection",
    "providers.refresh": "Refresh Models",
    "providers.save": "Save",
    "providers.default": "Set Default",
    "providers.localOnly": "Local Only (Ollama)",
    "providers.fallback": "Fallback chain",
    "providers.onboarding": "Quick start",
    "providers.onboarding.1": "Pick local Ollama or enable a cloud provider.",
    "providers.onboarding.2": "Enter Base URL / API Key.",
    "providers.onboarding.3": "Run Test Connection and set a default model.",
    "skills.title": "Skills",
    "skills.lead": "Domain skills for modeling, materials, lighting, and more.",
    "presets.title": "Presets",
    "presets.lead": "System prompts, styles, and workflows.",
    "history.title": "History",
    "settings.title": "Settings",
    "settings.language": "Language",
    "settings.direction": "Text direction",
    "settings.direction.help": "Independent of language. Use RTL for Persian layout even when UI language is English.",
    "settings.direction.auto": "Auto (follow language)",
    "settings.direction.ltr": "LTR (left to right)",
    "settings.direction.rtl": "RTL (right to left)",
    "settings.autonomy": "Autonomy",
    "settings.mcp": "MCP token",
    "settings.rotate": "Rotate token",
    "settings.saved": "Saved",
    "settings.blenderNote": "Blender N-Panel labels stay in English.",
  },
  fa: {
    tagline: "دستیار هوش مصنوعی حرفه‌ای برای بلندر",
    "nav.chat": "چت",
    "nav.skills": "اسکیل‌ها",
    "nav.presets": "پریست‌ها",
    "nav.providers": "ارائه‌دهنده‌ها",
    "nav.history": "تاریخچه",
    "nav.settings": "تنظیمات",
    "chat.title": "چت",
    "chat.lead": "با صحنهٔ زنده بلندر حرف بزنید و ابزارها را اجرا کنید.",
    "chat.placeholder": "مثلاً: یک میز مدرن ۱۲۰ سانتی بساز…",
    "chat.send": "ارسال",
    "chat.provider": "ارائه‌دهنده",
    "chat.model": "مدل",
    "chat.skill": "اسکیل",
    "providers.title": "اتصال هوش‌های مصنوعی",
    "providers.lead": "همهٔ کلیدها، آدرس‌ها و مدل‌ها را از همین صفحه تنظیم کنید.",
    "providers.test": "تست اتصال",
    "providers.refresh": "بروزرسانی مدل‌ها",
    "providers.save": "ذخیره",
    "providers.default": "پیش‌فرض",
    "providers.localOnly": "فقط محلی (Ollama)",
    "providers.fallback": "زنجیرهٔ Fallback",
    "providers.onboarding": "شروع سریع",
    "providers.onboarding.1": "Ollama محلی را انتخاب کنید یا یک ارائه‌دهنده ابری را فعال کنید.",
    "providers.onboarding.2": "Base URL / API Key را وارد کنید.",
    "providers.onboarding.3": "Test Connection بزنید و مدل پیش‌فرض را تنظیم کنید.",
    "skills.title": "اسکیل‌ها",
    "skills.lead": "اسکیل‌های دامنه برای مدلینگ، متریال، نور و بیشتر.",
    "presets.title": "پریست‌ها",
    "presets.lead": "پرامپت‌های سیستم، استایل‌ها و ورک‌فلوها.",
    "history.title": "تاریخچه",
    "settings.title": "تنظیمات",
    "settings.language": "زبان",
    "settings.direction": "جهت نمایش",
    "settings.direction.help": "مستقل از زبان. حتی با UI انگلیسی می‌توانید RTL فارسی را فعال کنید.",
    "settings.direction.auto": "خودکار (بر اساس زبان)",
    "settings.direction.ltr": "چپ‌به‌راست (LTR)",
    "settings.direction.rtl": "راست‌به‌چپ (RTL)",
    "settings.autonomy": "سطح خودمختاری",
    "settings.mcp": "توکن MCP",
    "settings.rotate": "چرخش توکن",
    "settings.saved": "ذخیره شد",
    "settings.blenderNote": "برچسب‌های پنل Blender همیشه انگلیسی می‌مانند.",
  },
} as const;

export type I18nKey = keyof (typeof dict)["en"];

let current: Lang = "en";

export function setLang(lang: Lang) {
  current = lang === "fa" ? "fa" : "en";
}

export function getLang(): Lang {
  return current;
}

export function t(key: I18nKey): string {
  return dict[current][key] || dict.en[key] || key;
}

/** Resolve effective document direction from language + ui_direction setting. */
export function resolveDirection(lang: Lang, uiDirection: UiDirection | string): "ltr" | "rtl" {
  if (uiDirection === "ltr" || uiDirection === "rtl") return uiDirection;
  return lang === "fa" ? "rtl" : "ltr";
}
