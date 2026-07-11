import { useEffect, useState } from "react";
import { getSkills } from "../api/client";
import { t } from "../i18n";

export default function SkillsPage() {
  const [skills, setSkills] = useState<any[]>([]);
  useEffect(() => {
    getSkills().then((r) => setSkills(r.skills)).catch(console.error);
  }, []);
  return (
    <div>
      <h2 className="page-title">{t("skills.title")}</h2>
      <p className="page-lead">{t("skills.lead")}</p>
      <div className="grid">
        {skills.map((s) => (
          <article key={s.id} className="card">
            <div style={{ display: "flex", alignItems: "center", gap: "0.65rem" }}>
              <span
                className="skill-pulse"
                style={{ width: 10, height: 10, borderRadius: 99, background: "var(--accent)", flexShrink: 0 }}
              />
              <h3 style={{ margin: 0 }}>{s.name || s.id}</h3>
            </div>
            <p className="muted">{s.description}</p>
            <p className="muted" style={{ fontSize: "0.8rem" }}>
              {(s.domains || []).join(", ")} · risk: {s.risk}
            </p>
          </article>
        ))}
      </div>
    </div>
  );
}
