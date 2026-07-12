import { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import {
  createPreset,
  deletePreset,
  getPreset,
  getPresets,
  reloadPresets,
  updatePreset,
} from "../api/client";
import { t } from "../i18n";
import "./skills.css";

type PresetForm = {
  id: string;
  name: string;
  description: string;
  category: string;
  prompt: string;
};

const emptyForm = (): PresetForm => ({
  id: "",
  name: "",
  description: "",
  category: "custom",
  prompt: "",
});

const CATEGORIES = ["custom", "general", "styles", "workflows", "modeling", "materials", "lighting"];

function formFromDraft(draft: Record<string, unknown> | null | undefined): PresetForm {
  if (!draft) return emptyForm();
  return {
    id: String(draft.id || ""),
    name: String(draft.name || ""),
    description: String(draft.description || ""),
    category: String(draft.category || "workflows"),
    prompt: String(draft.prompt || ""),
  };
}

export default function PresetsPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const [presets, setPresets] = useState<any[]>([]);
  const [form, setForm] = useState<PresetForm>(emptyForm);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [showForm, setShowForm] = useState(false);

  const load = async () => {
    const r = await getPresets();
    setPresets(r.presets || []);
  };

  useEffect(() => {
    load().catch((e) => setError(String(e)));
  }, []);

  useEffect(() => {
    const draft = (location.state as { draft?: Record<string, unknown> } | null)?.draft;
    if (!draft) return;
    setEditingId(null);
    setForm(formFromDraft(draft));
    setShowForm(true);
    setError("");
    setNotice(t("presets.fromChatReady"));
    navigate(location.pathname, { replace: true, state: null });
  }, [location.state, location.pathname, navigate]);

  const bundled = useMemo(() => presets.filter((p) => p.source !== "user"), [presets]);
  const custom = useMemo(() => presets.filter((p) => p.source === "user"), [presets]);

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
      const { preset } = await getPreset(id);
      setEditingId(id);
      setForm({
        id: preset.id || id,
        name: preset.name || "",
        description: preset.description || "",
        category: preset.category || "custom",
        prompt: preset.prompt || "",
      });
      setShowForm(true);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const save = async () => {
    if (!form.name.trim()) {
      setError(t("presets.errName"));
      return;
    }
    setBusy(true);
    setError("");
    setNotice("");
    const body = {
      id: form.id || undefined,
      name: form.name.trim(),
      description: form.description.trim(),
      category: form.category,
      prompt: form.prompt,
    };
    try {
      if (editingId) await updatePreset(editingId, body);
      else await createPreset(body);
      await load();
      setShowForm(false);
      setEditingId(null);
      setForm(emptyForm());
      setNotice(t("presets.saved"));
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const remove = async (id: string) => {
    if (!window.confirm(t("presets.confirmDelete"))) return;
    setBusy(true);
    setError("");
    try {
      await deletePreset(id);
      await load();
      setNotice(t("presets.deleted"));
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
      await reloadPresets();
      await load();
      setNotice(t("presets.reloaded"));
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const preview = (p: any) =>
    (p.prompt_preview || p.prompt || (p.steps ? JSON.stringify(p.steps) : "") || "").slice(0, 220);

  return (
    <div className="skills-page">
      <div className="skills-header">
        <div>
          <h2 className="page-title">{t("presets.title")}</h2>
          <p className="page-lead">{t("presets.lead")}</p>
        </div>
        <div className="skills-actions">
          <button type="button" onClick={reload} disabled={busy}>
            {t("presets.reload")}
          </button>
          <button type="button" className="primary" onClick={openCreate} disabled={busy}>
            {t("presets.add")}
          </button>
        </div>
      </div>

      {error ? <p className="skills-banner err">{error}</p> : null}
      {notice ? <p className="skills-banner ok">{notice}</p> : null}

      {showForm ? (
        <section className="skills-form card">
          <div className="hd-icon-text-row skills-form-title">
            <span className="skills-form-dot" aria-hidden="true" />
            <h3 className="min-w-0">{editingId ? t("presets.edit") : t("presets.create")}</h3>
          </div>
          <div className="skills-form-grid">
            <label>
              {t("presets.fieldName")}
              <input
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="My product look"
              />
            </label>
            <label>
              {t("presets.fieldId")}
              <input
                value={form.id}
                onChange={(e) => setForm({ ...form, id: e.target.value })}
                placeholder="user.my_look"
                disabled={!!editingId}
              />
            </label>
            <label className="span-2">
              {t("presets.fieldDesc")}
              <input
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
              />
            </label>
            <label>
              {t("presets.fieldCategory")}
              <select
                value={form.category}
                onChange={(e) => setForm({ ...form, category: e.target.value })}
              >
                {CATEGORIES.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </label>
            <label className="span-2">
              {t("presets.fieldPrompt")}
              <textarea
                rows={8}
                value={form.prompt}
                onChange={(e) => setForm({ ...form, prompt: e.target.value })}
                placeholder={t("presets.promptPlaceholder")}
              />
            </label>
          </div>
          <div className="skills-form-actions">
            <button type="button" onClick={() => setShowForm(false)} disabled={busy}>
              {t("presets.cancel")}
            </button>
            <button type="button" className="primary" onClick={save} disabled={busy}>
              {t("presets.save")}
            </button>
          </div>
        </section>
      ) : null}

      <h3 className="skills-section-title">{t("presets.custom")}</h3>
      {custom.length === 0 ? (
        <p className="muted">{t("presets.customEmpty")}</p>
      ) : (
        <div className="grid">
          {custom.map((p) => (
            <article key={p.id} className="card skill-card user">
              <div className="hd-icon-text-row">
                <span className="skill-pulse" aria-hidden="true" />
                <h3 className="min-w-0">{p.name || p.id}</h3>
              </div>
              <p className="muted">{p.description}</p>
              <p className="muted skill-meta">
                {p.id} · {p.category || "custom"}
              </p>
              <p className="muted" style={{ whiteSpace: "pre-wrap", fontSize: "0.85rem" }}>
                {preview(p)}
              </p>
              <div className="skill-card-actions">
                <button type="button" onClick={() => openEdit(p.id)} disabled={busy}>
                  {t("presets.edit")}
                </button>
                <button type="button" className="danger" onClick={() => remove(p.id)} disabled={busy}>
                  {t("presets.delete")}
                </button>
              </div>
            </article>
          ))}
        </div>
      )}

      <h3 className="skills-section-title">{t("presets.bundled")}</h3>
      <div className="grid">
        {bundled.map((p) => (
          <article key={p.id || p.path} className="card skill-card">
            <div className="hd-icon-text-row">
              <span className="skill-pulse" aria-hidden="true" />
              <h3 className="min-w-0">{p.name || p.id}</h3>
            </div>
            <p className="muted skill-meta">
              {p.category || p.path} · {p.id}
            </p>
            <p className="muted" style={{ whiteSpace: "pre-wrap", fontSize: "0.85rem" }}>
              {preview(p)}
            </p>
          </article>
        ))}
      </div>
    </div>
  );
}
