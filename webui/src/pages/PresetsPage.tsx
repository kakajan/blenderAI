import { useEffect, useState } from "react";
import { getPresets } from "../api/client";
import { t } from "../i18n";

export default function PresetsPage() {
  const [presets, setPresets] = useState<any[]>([]);
  useEffect(() => {
    getPresets().then((r) => setPresets(r.presets)).catch(console.error);
  }, []);
  return (
    <div>
      <h2 className="page-title">{t("presets.title")}</h2>
      <p className="page-lead">{t("presets.lead")}</p>
      <div className="grid">
        {presets.map((p) => (
          <article key={p.id || p.path} className="card">
            <div style={{ display: "flex", alignItems: "center", gap: "0.65rem" }}>
              <span
                style={{
                  width: 28,
                  height: 28,
                  borderRadius: 8,
                  background: "linear-gradient(135deg,#d4a574,#b87333)",
                  flexShrink: 0,
                }}
              />
              <h3 style={{ margin: 0 }}>{p.name || p.id}</h3>
            </div>
            <p className="muted" style={{ whiteSpace: "pre-wrap", fontSize: "0.85rem" }}>
              {(p.prompt || "").slice(0, 220)}
            </p>
          </article>
        ))}
      </div>
    </div>
  );
}
