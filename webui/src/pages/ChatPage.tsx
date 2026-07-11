import { FormEvent, useEffect, useRef, useState } from "react";
import { getProviders, getSettings, getSkills, streamChat } from "../api/client";
import type { Provider } from "../api/client";
import Select from "../components/Select";
import { t } from "../i18n";
import "./chat.css";

type Msg = { role: "user" | "assistant" | "system"; content: string; streaming?: boolean };

export default function ChatPage() {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [skills, setSkills] = useState<any[]>([]);
  const [providerId, setProviderId] = useState("ollama");
  const [model, setModel] = useState("");
  const [skillId, setSkillId] = useState("");
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Msg[]>([]);
  const [busy, setBusy] = useState(false);
  const [chatId, setChatId] = useState<string | undefined>();
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    Promise.all([getProviders(), getSkills(), getSettings()])
      .then(([p, s, settings]) => {
        setProviders(p.providers.filter((x) => x.enabled));
        setSkills(s.skills);
        setProviderId(settings.default_provider_id || "ollama");
        setModel(settings.default_chat_model || "");
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!input.trim() || busy) return;
    const text = input.trim();
    setInput("");
    setMessages((m) => [...m, { role: "user", content: text }, { role: "assistant", content: "", streaming: true }]);
    setBusy(true);
    try {
      await streamChat(
        {
          message: text,
          provider_id: providerId,
          model: model || null,
          skill_id: skillId || null,
          chat_id: chatId || null,
        },
        (ev) => {
          if (ev.type === "status" && ev.data?.chat_id) setChatId(ev.data.chat_id);
          if (ev.type === "token") {
            setMessages((m) => {
              const copy = [...m];
              const last = copy[copy.length - 1];
              if (last?.role === "assistant") {
                copy[copy.length - 1] = { ...last, content: last.content + ev.content, streaming: true };
              }
              return copy;
            });
          }
          if (ev.type === "tool_call") {
            setMessages((m) => {
              const copy = [...m];
              const last = copy[copy.length - 1];
              if (last?.role === "assistant") {
                copy[copy.length - 1] = {
                  ...last,
                  content: last.content + `\n⚙ ${ev.content}\n`,
                  streaming: true,
                };
              }
              return copy;
            });
          }
          if (ev.type === "error") {
            setMessages((m) => {
              const copy = [...m];
              const last = copy[copy.length - 1];
              if (last?.role === "assistant") {
                copy[copy.length - 1] = { ...last, content: last.content + `\n⚠ ${ev.content}`, streaming: false };
              }
              return copy;
            });
          }
          if (ev.type === "done") {
            setMessages((m) => {
              const copy = [...m];
              const last = copy[copy.length - 1];
              if (last?.role === "assistant") copy[copy.length - 1] = { ...last, streaming: false };
              return copy;
            });
          }
        }
      );
    } catch (err: any) {
      setMessages((m) => [...m, { role: "system", content: String(err.message || err) }]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="chat-page">
      <div className="chat-head">
        <div>
          <h2 className="page-title">{t("chat.title")}</h2>
          <p className="page-lead">{t("chat.lead")}</p>
        </div>
        <div className="chat-controls">
          <Select
            label={t("chat.provider")}
            value={providerId}
            onChange={setProviderId}
            options={providers.map((p) => ({ value: p.id, label: p.name }))}
          />
          <div className="ui-field">
            <span className="ui-label">{t("chat.model")}</span>
            <input value={model} onChange={(e) => setModel(e.target.value)} placeholder="auto" />
          </div>
          <Select
            label={t("chat.skill")}
            value={skillId}
            onChange={setSkillId}
            options={[{ value: "", label: "—" }, ...skills.map((s) => ({ value: s.id, label: s.name || s.id }))]}
          />
        </div>
      </div>

      <div className="chat-log card">
        {messages.length === 0 && <p className="empty-hint">BlenderAI ready.</p>}
        {messages.map((m, i) => (
          <div key={i} className={`bubble ${m.role} ${m.streaming ? "stream-cursor" : ""}`}>
            <pre>{m.content}</pre>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      <form className="chat-form" onSubmit={onSubmit}>
        <textarea
          rows={3}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={t("chat.placeholder")}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              onSubmit(e as any);
            }
          }}
        />
        <button className="primary" disabled={busy || !input.trim()}>
          {t("chat.send")}
        </button>
      </form>
    </div>
  );
}
