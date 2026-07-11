import { NavLink, Route, Routes } from "react-router-dom";
import { useEffect, useState } from "react";
import ChatPage from "./pages/ChatPage";
import ProvidersPage from "./pages/ProvidersPage";
import SkillsPage from "./pages/SkillsPage";
import PresetsPage from "./pages/PresetsPage";
import HistoryPage from "./pages/HistoryPage";
import SettingsPage from "./pages/SettingsPage";
import { getSettings } from "./api/client";
import { t, setLang, resolveDirection, Lang, UiDirection } from "./i18n";
import "./styles/shell.css";

export default function App() {
  const [lang, setLangState] = useState<Lang>("en");
  const [uiDirection, setUiDirection] = useState<UiDirection>("auto");
  const [ready, setReady] = useState(false);
  const [, setTick] = useState(0);

  function applyLocale(nextLang: Lang, nextDir: UiDirection) {
    setLang(nextLang);
    setLangState(nextLang);
    setUiDirection(nextDir);
    setTick((n) => n + 1);
  }

  useEffect(() => {
    getSettings()
      .then((s) => {
        const l = (s.language === "fa" ? "fa" : "en") as Lang;
        const d = (["auto", "ltr", "rtl"].includes(s.ui_direction) ? s.ui_direction : "auto") as UiDirection;
        applyLocale(l, d);
      })
      .catch(() => {
        applyLocale("en", "auto");
      })
      .finally(() => setReady(true));
  }, []);

  if (!ready) {
    return <div className="boot">BlenderAI</div>;
  }

  const dir = resolveDirection(lang, uiDirection);

  return (
    <div className="shell" dir={dir} lang={lang}>
      <header className="shell-header">
        <div className="brand">
          <span className="brand-mark" aria-hidden />
          <div>
            <h1 className="brand-title">BlenderAI</h1>
            <p className="brand-sub">{t("tagline")}</p>
          </div>
        </div>
        <nav className="nav">
          <NavLink to="/">{t("nav.chat")}</NavLink>
          <NavLink to="/skills">{t("nav.skills")}</NavLink>
          <NavLink to="/presets">{t("nav.presets")}</NavLink>
          <NavLink to="/providers">{t("nav.providers")}</NavLink>
          <NavLink to="/history">{t("nav.history")}</NavLink>
          <NavLink to="/settings">{t("nav.settings")}</NavLink>
        </nav>
      </header>
      <main className="shell-main">
        <Routes>
          <Route path="/" element={<ChatPage />} />
          <Route path="/skills" element={<SkillsPage />} />
          <Route path="/presets" element={<PresetsPage />} />
          <Route path="/providers" element={<ProvidersPage />} />
          <Route path="/history" element={<HistoryPage />} />
          <Route
            path="/settings"
            element={
              <SettingsPage
                onLocale={(l, d) => applyLocale(l, d)}
              />
            }
          />
        </Routes>
      </main>
    </div>
  );
}
