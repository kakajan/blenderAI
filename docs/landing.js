const REPO = "kakajan/blenderAI";
const API = `https://api.github.com/repos/${REPO}`;

const copy = {
  en: {
    brand: "BlenderAI",
    "nav.features": "Features",
    "nav.guide": "Guide",
    "nav.repo": "Repository",
    "nav.contribute": "Contribute",
    "nav.github": "GitHub",
    "hero.title": "Your AI co-pilot inside Blender",
    "hero.lead":
      "Local or cloud models, domain skills, and live scene control — without leaving your viewport.",
    "hero.ctaPrimary": "View on GitHub",
    "hero.ctaSecondary": "Read the guide",
    "hero.prompt": "“Create a modern oak table…”",
    "repo.eyebrow": "Open source",
    "repo.fallbackDesc": "AI co-pilot for Blender — N-Panel chat, skills, providers, and MCP.",
    "repo.stars": "Stars",
    "repo.forks": "Forks",
    "repo.issues": "Open issues",
    "repo.language": "Language",
    "repo.license": "License",
    "repo.updated": "Updated",
    "features.eyebrow": "Built for real pipelines",
    "features.title": "One assistant across your whole scene",
    "features.lead":
      "From blockout to look-dev — talk to Blender in English or Persian, with tools that respect undo.",
    "features.f1.title": "Multi-provider brain",
    "features.f1.body":
      "Ollama, OpenAI, Claude, DeepSeek, Qwen, GLM, and any OpenAI-compatible endpoint.",
    "features.f2.title": "Domain skills",
    "features.f2.body": "Modeling, materials, lighting, sculpt assist, review — extend with YAML.",
    "features.f3.title": "Private by default",
    "features.f3.body": "Keys in the OS keyring. Local Only mode. Scene context stays under your control.",
    "features.f4.title": "MCP for Cursor",
    "features.f4.body": "Drive the same open Blender scene from Cursor or any MCP client.",
    "how.eyebrow": "Three steps",
    "how.title": "From install to first mesh",
    "how.s1.title": "Run the installer",
    "how.s1.body": "Windows, macOS, or Linux — finds Blender and sets up the sidecar.",
    "how.s2.title": "Connect a model",
    "how.s2.body": "Open Providers, test Ollama or a cloud key, set your default.",
    "how.s3.title": "Chat in the N-Panel",
    "how.s3.body": "Press N → BlenderAI → describe what you need in the scene.",
    "docs.guide": "Full user guide →",
    "docs.readme": "Project README →",
    "docs.mcp": "MCP setup →",
    "providers.eyebrow": "Providers",
    "providers.title": "Local studio or cloud horsepower",
    "providers.lead": "Switch models per chat or skill. Chain fallbacks when one endpoint fails.",
    "contribute.eyebrow": "Community",
    "contribute.title": "Build it with us",
    "contribute.lead":
      "Skills, providers, UI polish, docs, security reviews — every contribution makes artists faster.",
    "contribute.star": "Star on GitHub",
    "contribute.guide": "Contributing guide",
    "contribute.issues": "Open an issue",
    "footer.tag": "MIT licensed · made for people who ship scenes",
    "footer.repo": "Repository",
    "footer.guide": "Guide",
    "footer.contrib": "Contribute",
    "footer.license": "License",
  },
  fa: {
    brand: "BlenderAI",
    "nav.features": "قابلیت‌ها",
    "nav.guide": "راهنما",
    "nav.repo": "ریپو",
    "nav.contribute": "مشارکت",
    "nav.github": "گیت‌هاب",
    "hero.title": "همکار هوش مصنوعی شما داخل بلندر",
    "hero.lead": "مدل محلی یا ابری، اسکیل‌های دامنه، و کنترل زنده صحنه — بدون ترک ویوپورت.",
    "hero.ctaPrimary": "مشاهده در گیت‌هاب",
    "hero.ctaSecondary": "خواندن راهنما",
    "hero.prompt": "«یک میز بلوط مدرن بساز…»",
    "repo.eyebrow": "متن‌باز",
    "repo.fallbackDesc": "همکار AI برای بلندر — چت N-Panel، اسکیل، Providers و MCP.",
    "repo.stars": "ستاره‌ها",
    "repo.forks": "فورک‌ها",
    "repo.issues": "Issueهای باز",
    "repo.language": "زبان",
    "repo.license": "مجوز",
    "repo.updated": "به‌روزرسانی",
    "features.eyebrow": "برای پایپ‌لاین واقعی",
    "features.title": "یک دستیار برای کل صحنه",
    "features.lead":
      "از بلاک‌اوت تا لوک‌دو — با انگلیسی یا فارسی با بلندر حرف بزنید؛ ابزارها Undo را رعایت می‌کنند.",
    "features.f1.title": "چند ارائه‌دهنده",
    "features.f1.body": "Ollama، OpenAI، Claude، DeepSeek، Qwen، GLM و هر endpoint سازگار.",
    "features.f2.title": "اسکیل‌های دامنه",
    "features.f2.body": "مدلینگ، متریال، نور، اسکالپت، نقد — با YAML گسترش‌پذیر.",
    "features.f3.title": "خصوصی به‌صورت پیش‌فرض",
    "features.f3.body": "کلیدها در keyring سیستم. حالت Local Only. کانتکست صحنه زیر کنترل شما.",
    "features.f4.title": "MCP برای Cursor",
    "features.f4.body": "همان صحنه باز بلندر را از Cursor یا هر کلاینت MCP برانید.",
    "how.eyebrow": "سه قدم",
    "how.title": "از نصب تا اولین مش",
    "how.s1.title": "اینستالر را اجرا کنید",
    "how.s1.body": "ویندوز، macOS یا لینوکس — بلندر را پیدا می‌کند و sidecar را آماده می‌کند.",
    "how.s2.title": "مدل را وصل کنید",
    "how.s2.body": "Providers را باز کنید، Ollama یا کلید کلود را تست کنید، پیش‌فرض بگذارید.",
    "how.s3.title": "در N-Panel چت کنید",
    "how.s3.body": "N → BlenderAI → آنچه در صحنه می‌خواهید توصیف کنید.",
    "docs.guide": "راهنمای کامل کاربر →",
    "docs.readme": "README پروژه →",
    "docs.mcp": "راه‌اندازی MCP →",
    "providers.eyebrow": "ارائه‌دهنده‌ها",
    "providers.title": "استودیوی محلی یا قدرت کلود",
    "providers.lead": "مدل را per-chat یا per-skill عوض کنید. Fallback زنجیره‌ای وقتی یکی fail شود.",
    "contribute.eyebrow": "جامعه",
    "contribute.title": "با ما بسازید",
    "contribute.lead": "اسکیل، ارائه‌دهنده، UI، مستندات، امنیت — هر مشارکت هنرمندان را سریع‌تر می‌کند.",
    "contribute.star": "ستاره در گیت‌هاب",
    "contribute.guide": "راهنمای مشارکت",
    "contribute.issues": "ثبت Issue",
    "footer.tag": "مجوز MIT · برای کسانی که صحنه می‌سازند",
    "footer.repo": "ریپوزیتوری",
    "footer.guide": "راهنما",
    "footer.contrib": "مشارکت",
    "footer.license": "مجوز",
  },
};

const guideHref = {
  en: {
    guide: "https://github.com/kakajan/blenderAI/blob/main/GUIDE.md",
    readme: "https://github.com/kakajan/blenderAI/blob/main/README.md",
    contributing: "https://github.com/kakajan/blenderAI/blob/main/CONTRIBUTING.md",
    mcp: "https://github.com/kakajan/blenderAI/blob/main/docs/mcp.md",
  },
  fa: {
    guide: "https://github.com/kakajan/blenderAI/blob/main/GUIDE.fa.md",
    readme: "https://github.com/kakajan/blenderAI/blob/main/README.fa.md",
    contributing: "https://github.com/kakajan/blenderAI/blob/main/CONTRIBUTING.fa.md",
    mcp: "https://github.com/kakajan/blenderAI/blob/main/docs/mcp.fa.md",
  },
};

let lang = "en";
let repoPayload = null;

function formatNumber(n) {
  if (typeof n !== "number") return "—";
  return new Intl.NumberFormat(lang === "fa" ? "fa-IR" : "en-US").format(n);
}

function formatDate(iso) {
  if (!iso) return "—";
  try {
    return new Intl.DateTimeFormat(lang === "fa" ? "fa-IR" : "en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
    }).format(new Date(iso));
  } catch {
    return iso.slice(0, 10);
  }
}

function setText(id, value) {
  const el = document.getElementById(id);
  if (el) el.textContent = value;
}

function applyRepoData(data) {
  if (!data) return;
  const name = data.full_name || REPO;
  const desc =
    data.description ||
    copy[lang]["repo.fallbackDesc"] ||
    copy.en["repo.fallbackDesc"];
  const license = data.license?.spdx_id || data.license?.name || "MIT";
  const author =
    data.owner?.login === "kakajan"
      ? "AsherQelich SayyedMuhammadi · @kakajan"
      : `@${data.owner?.login || "kakajan"}`;

  const nameEl = document.getElementById("repoFullName");
  if (nameEl) {
    nameEl.textContent = name;
    nameEl.href = data.html_url || `https://github.com/${REPO}`;
  }
  setText("repoDescription", desc);
  setText("repoAuthor", author);
  setText("statStars", formatNumber(data.stargazers_count));
  setText("statForks", formatNumber(data.forks_count));
  setText("statIssues", formatNumber(data.open_issues_count));
  setText("statLanguage", data.language || "Python");
  setText("statLicense", license);
  setText("statUpdated", formatDate(data.pushed_at || data.updated_at));
}

function applyDocLinks() {
  const links = guideHref[lang];
  document.querySelectorAll('a[data-i18n="docs.guide"], a[data-i18n="hero.ctaSecondary"]').forEach((a) => {
    a.href = links.guide;
  });
  document.querySelectorAll('a[data-i18n="docs.readme"]').forEach((a) => {
    a.href = links.readme;
  });
  document.querySelectorAll('a[data-i18n="docs.mcp"]').forEach((a) => {
    a.href = links.mcp;
  });
  document.querySelectorAll('a[data-i18n="contribute.guide"], a[data-i18n="footer.contrib"]').forEach((a) => {
    a.href = links.contributing;
  });
  document.querySelectorAll('a[data-i18n="footer.guide"]').forEach((a) => {
    a.href = links.guide;
  });
}

function applyLang(next) {
  lang = next;
  const dict = copy[lang];
  document.documentElement.lang = lang;
  document.body.lang = lang;
  document.body.dir = lang === "fa" ? "rtl" : "ltr";
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    const key = el.getAttribute("data-i18n");
    if (dict[key]) el.textContent = dict[key];
  });
  const btn = document.getElementById("langToggle");
  if (btn) btn.textContent = lang === "en" ? "FA" : "EN";
  applyDocLinks();
  applyRepoData(repoPayload);
  try {
    localStorage.setItem("blenderai-landing-lang", lang);
  } catch {
    /* ignore */
  }
}

async function loadRepo() {
  try {
    const res = await fetch(API, {
      headers: { Accept: "application/vnd.github+json" },
    });
    if (!res.ok) throw new Error(`GitHub API ${res.status}`);
    repoPayload = await res.json();
    applyRepoData(repoPayload);
  } catch {
    applyRepoData({
      full_name: REPO,
      html_url: `https://github.com/${REPO}`,
      description: null,
      stargazers_count: 0,
      forks_count: 0,
      open_issues_count: 0,
      language: "Python",
      license: { spdx_id: "MIT" },
      updated_at: null,
      owner: { login: "kakajan" },
    });
  }
}

document.getElementById("langToggle")?.addEventListener("click", () => {
  applyLang(lang === "en" ? "fa" : "en");
});

try {
  const saved = localStorage.getItem("blenderai-landing-lang");
  if (saved === "fa" || saved === "en") lang = saved;
} catch {
  /* ignore */
}

applyLang(lang);
loadRepo();
