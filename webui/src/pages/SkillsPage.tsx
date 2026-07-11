import { useEffect, useMemo, useState } from "react";
import {
  createSkill,
  deleteSkill,
  getSkill,
  getSkills,
  reloadSkills,
  updateSkill,
} from "../api/client";
import { t } from "../i18n";
import "./skills.css";

type SkillForm = {
  id: string;
  name: string;
  description: string;
  domains: string;
  tools: string[];
  prompt: string;
  risk: string;
  requires_confirmation: boolean;
  viewport_capture: string;
};

const emptyForm = (): SkillForm => ({
  id: "",
  name: "",
  description: "",
  domains: "custom",
  tools: ["scene.create_object", "mesh.ops"],
  prompt: "",
  risk: "medium",
  requires_confirmation: false,
  viewport_capture: "optional",
});

export default function SkillsPage() {
  const [skills, setSkills] = useState<any[]>([]);
  const [knownTools, setKnownTools] = useState<string[]>([]);
  const [form, setForm] = useState<SkillForm>(emptyForm);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [showForm, setShowForm] = useState(false);

  const load = async () => {
    const r = await getSkills();
    setSkills(r.skills || []);
    if (r.known_tools?.length) setKnownTools(r.known_tools);
  };

  useEffect(() => {
    load().catch((e) => setError(String(e)));
  }, []);

  const bundled = useMemo(() => skills.filter((s) => s.source !== "user"), [skills]);
  const custom = useMemo(() => skills.filter((s) => s.source === "user"), [skills]);

  const openCreate = () => {
    setEditingId(null);
    setForm(emptyForm());
    setShowForm(true);
    setError("");
    setNotice("");
  };

  const openEdit = async (id: string) => {
    setBusy(true);
    setError("");
    try {
      const { skill } = await getSkill(id);
      setEditingId(id);
      setForm({
        id: skill.id || id,
        name: skill.name || "",
        description: skill.description || "",
        domains: (skill.domains || []).join(", "),
        tools: skill.tools || [],
        prompt: skill.system_prompt_text || "",
        risk: skill.risk || "medium",
        requires_confirmation: !!skill.requires_confirmation,
        viewport_capture: String(skill.viewport_capture || "optional"),
      });
      setShowForm(true);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const toggleTool = (tool: string) => {
    setForm((f) => ({
      ...f,
      tools: f.tools.includes(tool) ? f.tools.filter((x) => x !== tool) : [...f.tools, tool],
    }));
  };

  const save = async () => {
    if (!form.name.trim()) {
      setError(t("skills.errName"));
      return;
    }
    setBusy(true);
    setError("");
    setNotice("");
    const body = {
      id: form.id || undefined,
      name: form.name.trim(),
      description: form.description.trim(),
      domains: form.domains,
      tools: form.tools,
      prompt: form.prompt,
      risk: form.risk,
      requires_confirmation: form.requires_confirmation,
      viewport_capture: form.viewport_capture,
    };
    try {
      if (editingId) await updateSkill(editingId, body);
      else await createSkill(body);
      await load();
      setShowForm(false);
      setEditingId(null);
      setForm(emptyForm());
      setNotice(t("skills.saved"));
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const remove = async (id: string) => {
    if (!window.confirm(t("skills.confirmDelete"))) return;
    setBusy(true);
    setError("");
    try {
      await deleteSkill(id);
      await load();
      setNotice(t("skills.deleted"));
      if (editingId === id) {
        setShowForm(false);
        setEditingId(null);
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const reload = async () => {
    setBusy(true);
    try {
      await reloadSkills();
      await load();
      setNotice(t("skills.reloaded"));
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="skills-page">
      <div className="skills-header">
        <div>
          <h2 className="page-title">{t("skills.title")}</h2>
          <p className="page-lead">{t("skills.lead")}</p>
        </div>
        <div className="skills-actions">
          <button type="button" onClick={reload} disabled={busy}>
            {t("skills.reload")}
          </button>
          <button type="button" className="primary" onClick={openCreate} disabled={busy}>
            {t("skills.add")}
          </button>
        </div>
      </div>

      {error ? <p className="skills-banner err">{error}</p> : null}
      {notice ? <p className="skills-banner ok">{notice}</p> : null}

      {showForm ? (
        <section className="skills-form card">
          <div className="hd-icon-text-row skills-form-title">
            <span className="skills-form-dot" aria-hidden="true" />
            <h3 className="min-w-0">{editingId ? t("skills.edit") : t("skills.create")}</h3>
          </div>
          <div className="skills-form-grid">
            <label>
              {t("skills.fieldName")}
              <input
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="My table builder"
              />
            </label>
            <label>
              {t("skills.fieldId")}
              <input
                value={form.id}
                onChange={(e) => setForm({ ...form, id: e.target.value })}
                placeholder="user.my_table"
                disabled={!!editingId}
              />
            </label>
            <label className="span-2">
              {t("skills.fieldDesc")}
              <input
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
              />
            </label>
            <label>
              {t("skills.fieldDomains")}
              <input
                value={form.domains}
                onChange={(e) => setForm({ ...form, domains: e.target.value })}
                placeholder="modeling, custom"
              />
            </label>
            <label>
              {t("skills.fieldRisk")}
              <select value={form.risk} onChange={(e) => setForm({ ...form, risk: e.target.value })}>
                <option value="low">low</option>
                <option value="medium">medium</option>
                <option value="high">high</option>
              </select>
            </label>
            <label>
              {t("skills.fieldViewport")}
              <select
                value={form.viewport_capture}
                onChange={(e) => setForm({ ...form, viewport_capture: e.target.value })}
              >
                <option value="false">false</option>
                <option value="optional">optional</option>
                <option value="required">required</option>
              </select>
            </label>
            <label className="check-row">
              <input
                type="checkbox"
                checked={form.requires_confirmation}
                onChange={(e) => setForm({ ...form, requires_confirmation: e.target.checked })}
              />
              {t("skills.fieldConfirm")}
            </label>
            <fieldset className="span-2 tools-fieldset">
              <legend>{t("skills.fieldTools")}</legend>
              <div className="tools-grid">
                {knownTools.map((tool) => (
                  <label key={tool} className="tool-chip">
                    <input
                      type="checkbox"
                      checked={form.tools.includes(tool)}
                      onChange={() => toggleTool(tool)}
                    />
                    <span>{tool}</span>
                  </label>
                ))}
              </div>
            </fieldset>
            <label className="span-2">
              {t("skills.fieldPrompt")}
              <textarea
                rows={8}
                value={form.prompt}
                onChange={(e) => setForm({ ...form, prompt: e.target.value })}
                placeholder={t("skills.promptPlaceholder")}
              />
            </label>
          </div>
          <div className="skills-form-actions">
            <button type="button" onClick={() => setShowForm(false)} disabled={busy}>
              {t("skills.cancel")}
            </button>
            <button type="button" className="primary" onClick={save} disabled={busy}>
              {t("skills.save")}
            </button>
          </div>
        </section>
      ) : null}

      <h3 className="skills-section-title">{t("skills.custom")}</h3>
      {custom.length === 0 ? (
        <p className="muted">{t("skills.customEmpty")}</p>
      ) : (
        <div className="grid">
          {custom.map((s) => (
            <article key={s.id} className="card skill-card user">
              <div className="hd-icon-text-row">
                <span className="skill-pulse" aria-hidden="true" />
                <h3 className="min-w-0">{s.name || s.id}</h3>
              </div>
              <p className="muted">{s.description}</p>
              <p className="muted skill-meta">
                {s.id} · {(s.domains || []).join(", ")} · risk: {s.risk}
              </p>
              <div className="skill-card-actions">
                <button type="button" onClick={() => openEdit(s.id)} disabled={busy}>
                  {t("skills.edit")}
                </button>
                <button type="button" className="danger" onClick={() => remove(s.id)} disabled={busy}>
                  {t("skills.delete")}
                </button>
              </div>
            </article>
          ))}
        </div>
      )}

      <h3 className="skills-section-title">{t("skills.bundled")}</h3>
      <div className="grid">
        {bundled.map((s) => (
          <article key={s.id} className="card skill-card">
            <div className="hd-icon-text-row">
              <span className="skill-pulse" aria-hidden="true" />
              <h3 className="min-w-0">{s.name || s.id}</h3>
            </div>
            <p className="muted">{s.description}</p>
            <p className="muted skill-meta">
              {(s.domains || []).join(", ")} · risk: {s.risk}
            </p>
          </article>
        ))}
      </div>
    </div>
  );
}
