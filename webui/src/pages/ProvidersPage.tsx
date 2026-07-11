import { useEffect, useMemo, useState } from "react";
import {
  getProviders,
  putProvider,
  testProvider,
  getModels,
  getSettings,
  putSettings,
} from "../api/client";
import type { Provider, AppSettings } from "../api/client";
import { t } from "../i18n";
import Toggle from "../components/Toggle";
import "./providers.css";

type Draft = Provider & { api_key?: string; models?: string[]; testMsg?: string; testOk?: boolean };

export default function ProvidersPage() {
  const [items, setItems] = useState<Draft[]>([]);
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [showOnboarding, setShowOnboarding] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [customName, setCustomName] = useState("");

  async function reload() {
    const [p, s] = await Promise.all([getProviders(), getSettings()]);
    setItems(p.providers);
    setSettings(s);
    const anyKey = p.providers.some((x) => x.has_api_key || x.id === "ollama");
    setShowOnboarding(!anyKey && !localStorage.getItem("blenderai_onboarded"));
  }

  useEffect(() => {
    reload().catch(console.error);
  }, []);

  function updateLocal(id: string, patch: Partial<Draft>) {
    setItems((list) => list.map((p) => (p.id === id ? { ...p, ...patch } : p)));
  }

  async function save(p: Draft) {
    setBusyId(p.id);
    try {
      await putProvider({
        id: p.id,
        kind: p.kind,
        name: p.name,
        enabled: p.enabled,
        base_url: p.base_url,
        default_model: p.default_model,
        api_key: p.api_key || undefined,
        sort_order: p.sort_order,
      });
      await reload();
    } finally {
      setBusyId(null);
    }
  }

  async function test(p: Draft) {
    setBusyId(p.id);
    try {
      if (p.api_key || p.base_url !== undefined) await save(p);
      const res = await testProvider(p.id);
      updateLocal(p.id, { testOk: res.ok, testMsg: res.message });
    } catch (e: any) {
      updateLocal(p.id, { testOk: false, testMsg: String(e.message || e) });
    } finally {
      setBusyId(null);
    }
  }

  async function refreshModels(p: Draft) {
    setBusyId(p.id);
    try {
      const res = await getModels(p.id);
      updateLocal(p.id, { models: res.models.map((m) => m.id) });
    } catch (e: any) {
      updateLocal(p.id, { testOk: false, testMsg: String(e.message || e) });
    } finally {
      setBusyId(null);
    }
  }

  async function setDefault(p: Draft) {
    await putSettings({
      default_provider_id: p.id,
      default_chat_model: p.default_model || "",
    });
    await reload();
  }

  async function toggleLocalOnly(v: boolean) {
    await putSettings({ local_only: v });
    await reload();
  }

  async function saveFallback(chain: string[]) {
    await putSettings({ fallback_chain: chain });
    await reload();
  }

  async function addCustom() {
    const id = `custom_${Date.now()}`;
    const name = customName.trim() || "Custom OpenAI-compatible";
    await putProvider({
      id,
      kind: "openai_compatible",
      name,
      enabled: true,
      base_url: "http://127.0.0.1:1234/v1",
      default_model: "",
      sort_order: 99,
    });
    setCustomName("");
    await reload();
  }

  const fallback = settings?.fallback_chain || [];

  const onboarding = useMemo(() => {
    if (!showOnboarding) return null;
    return (
      <div className="card onboarding">
        <h3>{t("providers.onboarding")}</h3>
        <ol>
          <li>{t("providers.onboarding.1")}</li>
          <li>{t("providers.onboarding.2")}</li>
          <li>{t("providers.onboarding.3")}</li>
        </ol>
        <button
          className="primary"
          onClick={() => {
            localStorage.setItem("blenderai_onboarded", "1");
            setShowOnboarding(false);
          }}
        >
          OK
        </button>
      </div>
    );
  }, [showOnboarding]);

  return (
    <div>
      <h2 className="page-title">{t("providers.title")}</h2>
      <p className="page-lead">{t("providers.lead")}</p>
      {onboarding}

      <div className="card global-bar">
        <Toggle
          checked={!!settings?.local_only}
          onChange={(v) => toggleLocalOnly(v)}
          label={t("providers.localOnly")}
        />
        <div className="fallback">
          <span className="muted">{t("providers.fallback")}</span>
          <input
            value={fallback.join(", ")}
            onChange={(e) =>
              setSettings((s) =>
                s
                  ? {
                      ...s,
                      fallback_chain: e.target.value
                        .split(",")
                        .map((x) => x.trim())
                        .filter(Boolean),
                    }
                  : s
              )
            }
            onBlur={() => settings && saveFallback(settings.fallback_chain)}
            placeholder="ollama, deepseek, openai"
          />
        </div>
        <div className="muted">
          Default: <strong>{settings?.default_provider_id}</strong> / {settings?.default_chat_model || "—"}
        </div>
      </div>

      <div className="provider-grid">
        {items.map((p) => (
          <article key={p.id} className={`card provider-card ${p.enabled ? "" : "dim"}`}>
            <header className="row between">
              <div className="row gap">
                <span className="provider-icon" />
                <h3>{p.name}</h3>
              </div>
              <div className="provider-enable">
                <Toggle
                  size="sm"
                  checked={p.enabled}
                  onChange={(v) => updateLocal(p.id, { enabled: v })}
                  label={p.enabled ? "ON" : "OFF"}
                />
              </div>
            </header>

            <label>
              Base URL
              <input
                value={p.base_url || ""}
                onChange={(e) => updateLocal(p.id, { base_url: e.target.value })}
              />
            </label>

            {p.kind !== "ollama" && (
              <label>
                API Key {p.has_api_key ? <span className="muted">({p.api_key_masked})</span> : null}
                <input
                  type="password"
                  placeholder={p.has_api_key ? "••••••••" : "sk-..."}
                  value={p.api_key || ""}
                  onChange={(e) => updateLocal(p.id, { api_key: e.target.value })}
                />
              </label>
            )}

            <label>
              Default model
              <input
                list={`models-${p.id}`}
                value={p.default_model || ""}
                onChange={(e) => updateLocal(p.id, { default_model: e.target.value })}
              />
              <datalist id={`models-${p.id}`}>
                {(p.models || []).map((m) => (
                  <option key={m} value={m} />
                ))}
              </datalist>
            </label>

            {p.testMsg && <p className={p.testOk ? "ok" : "err"}>{p.testMsg}</p>}

            <div className="actions">
              <button disabled={busyId === p.id} onClick={() => test(p)}>
                {t("providers.test")}
              </button>
              <button disabled={busyId === p.id} onClick={() => refreshModels(p)}>
                {t("providers.refresh")}
              </button>
              <button disabled={busyId === p.id} onClick={() => save(p)}>
                {t("providers.save")}
              </button>
              <button className="primary" disabled={busyId === p.id} onClick={() => setDefault(p)}>
                {t("providers.default")}
              </button>
            </div>
          </article>
        ))}
      </div>

      <div className="card add-custom row gap">
        <input
          placeholder="Custom provider name"
          value={customName}
          onChange={(e) => setCustomName(e.target.value)}
        />
        <button className="primary" onClick={addCustom}>
          + OpenAI-compatible
        </button>
      </div>
    </div>
  );
}
