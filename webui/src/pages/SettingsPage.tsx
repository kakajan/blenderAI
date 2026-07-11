import { useEffect, useState } from "react";
import { getSettings, putSettings } from "../api/client";
import type { AppSettings } from "../api/client";
import Select from "../components/Select";
import { Lang, UiDirection, t } from "../i18n";
import "./providers.css";

export default function SettingsPage({
  onLocale,
}: {
  onLocale: (lang: Lang, direction: UiDirection) => void;
}) {
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [msg, setMsg] = useState("");

  useEffect(() => {
    getSettings().then(setSettings).catch(console.error);
  }, []);

  async function save(patch: Record<string, unknown>) {
    const next = await putSettings(patch);
    setSettings(next);
    const lang = (next.language === "fa" ? "fa" : "en") as Lang;
    const dir = (["auto", "ltr", "rtl"].includes(next.ui_direction) ? next.ui_direction : "auto") as UiDirection;
    onLocale(lang, dir);
    setMsg(t("settings.saved"));
  }

  if (!settings) return <p className="muted">…</p>;

  return (
    <div>
      <h2 className="page-title">{t("settings.title")}</h2>
      <p className="page-lead">{t("settings.blenderNote")}</p>
      <div className="card settings-card">
        <Select
          label={t("settings.language")}
          value={settings.language === "fa" ? "fa" : "en"}
          onChange={(v) => save({ language: v })}
          options={[
            { value: "en", label: "English" },
            { value: "fa", label: "فارسی (Persian)" },
          ]}
        />

        <Select
          label={t("settings.direction")}
          value={settings.ui_direction || "auto"}
          onChange={(v) => save({ ui_direction: v })}
          options={[
            { value: "auto", label: t("settings.direction.auto") },
            { value: "ltr", label: t("settings.direction.ltr") },
            { value: "rtl", label: t("settings.direction.rtl") },
          ]}
        />
        <p className="muted help">{t("settings.direction.help")}</p>

        <Select
          label={t("settings.autonomy")}
          value={settings.autonomy}
          onChange={(v) => save({ autonomy: v })}
          options={[
            { value: "ask", label: "Ask" },
            { value: "auto_safe", label: "Auto-safe" },
            { value: "auto_full", label: "Auto-full" },
          ]}
        />

        <div>
          <div className="ui-label" style={{ marginBottom: "0.4rem" }}>
            {t("settings.mcp")}
          </div>
          <code
            style={{
              display: "inline-block",
              padding: "0.45rem 0.7rem",
              borderRadius: 8,
              background: "var(--control-bg)",
              border: "1px solid var(--border)",
            }}
          >
            {settings.mcp_token_masked || "—"}
          </code>
          <div style={{ marginTop: "0.65rem" }}>
            <button type="button" onClick={() => save({ rotate_mcp_token: true })}>
              {t("settings.rotate")}
            </button>
          </div>
        </div>
        {msg && <p className="ok">{msg}</p>}
      </div>
    </div>
  );
}
