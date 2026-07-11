import { useEffect, useState } from "react";
import { getChats, getMessages } from "../api/client";
import { t } from "../i18n";

export default function HistoryPage() {
  const [chats, setChats] = useState<any[]>([]);
  const [active, setActive] = useState<string | null>(null);
  const [messages, setMessages] = useState<any[]>([]);

  useEffect(() => {
    getChats().then((r) => setChats(r.chats)).catch(console.error);
  }, []);

  async function openChat(id: string) {
    setActive(id);
    const r = await getMessages(id);
    setMessages(r.messages);
  }

  return (
    <div>
      <h2 className="page-title">{t("history.title")}</h2>
      <div className="grid">
        {chats.map((c) => (
          <button key={c.id} className="card" style={{ textAlign: "start" }} onClick={() => openChat(c.id)}>
            <strong>{c.title}</strong>
            <div className="muted">{c.updated_at}</div>
          </button>
        ))}
      </div>
      {active && (
        <div className="card" style={{ marginTop: "1rem" }}>
          {messages.map((m) => (
            <div key={m.id} style={{ marginBottom: "0.75rem" }}>
              <strong>{m.role}</strong>
              <pre style={{ whiteSpace: "pre-wrap", margin: "0.25rem 0 0", fontFamily: "inherit" }}>{m.content}</pre>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
