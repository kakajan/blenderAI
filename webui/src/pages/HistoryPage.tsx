import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { clearChats, getChats, getMessages, presetFromChat } from "../api/client";
import { clearChatSession } from "../chatSession";
import { t } from "../i18n";
import "./skills.css";

export default function HistoryPage() {
  const navigate = useNavigate();
  const [chats, setChats] = useState<any[]>([]);
  const [active, setActive] = useState<string | null>(null);
  const [messages, setMessages] = useState<any[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function reload() {
    const r = await getChats();
    setChats(r.chats);
  }

  useEffect(() => {
    reload().catch((e) => setError(String(e)));
  }, []);

  async function openChat(id: string) {
    setActive(id);
    setError("");
    setNotice("");
    const r = await getMessages(id);
    setMessages(r.messages);
  }

  async function onClearHistory() {
    if (!window.confirm(t("history.clearConfirm"))) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await clearChats();
      clearChatSession();
      setActive(null);
      setMessages([]);
      setChats([]);
      setNotice(t("history.cleared"));
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function createPresetFromActive() {
    if (!active) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const chat = chats.find((c) => c.id === active);
      const { draft } = await presetFromChat({
        chat_id: active,
        name: chat?.title || undefined,
        category: "workflows",
        save: false,
      });
      navigate("/presets", { state: { draft } });
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="skills-page">
      <div className="skills-header">
        <div>
          <h2 className="page-title">{t("history.title")}</h2>
          <p className="page-lead">{t("history.lead")}</p>
        </div>
        <div className="skills-actions">
          <button type="button" onClick={() => void onClearHistory()} disabled={busy || chats.length === 0}>
            {t("history.clear")}
          </button>
        </div>
      </div>

      {error ? <p className="skills-banner err">{error}</p> : null}
      {notice ? <p className="skills-banner ok">{notice}</p> : null}

      {chats.length === 0 ? <p className="muted">{t("history.empty")}</p> : null}

      <div className="grid">
        {chats.map((c) => (
          <button
            key={c.id}
            type="button"
            className={`card skill-card${active === c.id ? " user" : ""}`}
            style={{ textAlign: "start" }}
            onClick={() => openChat(c.id)}
          >
            <div className="hd-icon-text-row">
              <span className="skill-pulse" aria-hidden="true" />
              <strong className="min-w-0">{c.title || c.id}</strong>
            </div>
            <div className="muted skill-meta">{c.updated_at}</div>
          </button>
        ))}
      </div>

      {active ? (
        <div className="card" style={{ marginTop: "0.25rem" }}>
          <div className="skills-header" style={{ marginBottom: "0.85rem" }}>
            <div className="hd-icon-text-row">
              <span className="skills-form-dot" aria-hidden="true" />
              <h3 className="min-w-0" style={{ margin: 0 }}>
                {chats.find((c) => c.id === active)?.title || t("history.conversation")}
              </h3>
            </div>
            <div className="skills-actions">
              <button type="button" className="primary" onClick={createPresetFromActive} disabled={busy || messages.length === 0}>
                {t("history.saveAsPreset")}
              </button>
            </div>
          </div>
          {messages.length === 0 ? (
            <p className="muted">{t("history.emptyMessages")}</p>
          ) : (
            messages.map((m) => (
              <div key={m.id} style={{ marginBottom: "0.75rem" }}>
                <strong>{m.role}</strong>
                <pre style={{ whiteSpace: "pre-wrap", margin: "0.25rem 0 0", fontFamily: "inherit" }}>{m.content}</pre>
              </div>
            ))
          )}
        </div>
      ) : null}
    </div>
  );
}
