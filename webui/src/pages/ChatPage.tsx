import { FormEvent, useEffect, useRef, useState, useSyncExternalStore } from "react";
import { useNavigate } from "react-router-dom";
import {
  confirmRun,
  getHealth,
  getProviders,
  getSettings,
  getSkills,
  getWorkflows,
  presetFromChat,
  reportClientLog,
  sendLearningFeedback,
  skillFromChat,
  stopChatStream,
  streamChat,
} from "../api/client";
import type { Provider } from "../api/client";
import Select from "../components/Select";
import {
  applyChatDefaults,
  armChatStream,
  cancelChatStream,
  clearChatSession,
  disarmChatStream,
  getChatSession,
  patchChatSession,
  startNewChatSession,
  subscribeChatSession,
  updateMessages,
} from "../chatSession";
import { t } from "../i18n";
import "./chat.css";

function fileToBase64(file: File): Promise<{ base64: string; mime: string }> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const raw = String(reader.result || "");
      const comma = raw.indexOf(",");
      resolve({
        base64: comma >= 0 ? raw.slice(comma + 1) : raw,
        mime: file.type || "image/png",
      });
    };
    reader.onerror = () => reject(reader.error || new Error("read failed"));
    reader.readAsDataURL(file);
  });
}

export default function ChatPage() {
  const navigate = useNavigate();
  const session = useSyncExternalStore(subscribeChatSession, getChatSession, getChatSession);
  const {
    messages,
    chatId,
    providerId,
    model,
    skillId,
    workflowId,
    workflowStep,
    input,
    busy,
  } = session;
  const [providers, setProviders] = useState<Provider[]>([]);
  const [skills, setSkills] = useState<any[]>([]);
  const [workflows, setWorkflows] = useState<any[]>([]);
  const [blenderConnected, setBlenderConnected] = useState<boolean | null>(null);
  const [presetBusy, setPresetBusy] = useState(false);
  const [presetError, setPresetError] = useState("");
  const [pendingImage, setPendingImage] = useState<{ base64: string; mime: string; name: string } | null>(null);
  const [pendingConfirm, setPendingConfirm] = useState<{ runId: string; tool: string; reason?: string } | null>(null);
  const [feedbackBusy, setFeedbackBusy] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const activeRunId = useRef<string | null>(null);

  useEffect(() => {
    Promise.all([getProviders(), getSkills(), getSettings(), getWorkflows()])
      .then(([p, s, settings, w]) => {
        setProviders(p.providers.filter((x) => x.enabled));
        setSkills(s.skills);
        setWorkflows(w.workflows || []);
        applyChatDefaults(settings.default_provider_id || "ollama", settings.default_chat_model || "");
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    let cancelled = false;
    const poll = () => {
      getHealth()
        .then((h) => {
          if (!cancelled) setBlenderConnected(!!h.blender_connected);
        })
        .catch(() => {
          if (!cancelled) setBlenderConnected(null);
        });
    };
    poll();
    const id = window.setInterval(poll, 4000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function saveAsPreset() {
    const usable = messages.filter((m) => m.role === "user" || m.role === "assistant");
    if (usable.length === 0 || presetBusy) return;
    setPresetBusy(true);
    setPresetError("");
    try {
      const firstUser = usable.find((m) => m.role === "user")?.content || "";
      const title = firstUser.slice(0, 60) || "Chat preset";
      const { draft } = await presetFromChat({
        chat_id: chatId || null,
        messages: usable.map((m) => ({ role: m.role, content: m.content })),
        name: title,
        category: "workflows",
        save: false,
      });
      navigate("/presets", { state: { draft } });
    } catch (err: any) {
      setPresetError(String(err.message || err));
    } finally {
      setPresetBusy(false);
    }
  }

  function appendToAssistant(text: string, streaming = true) {
    updateMessages((m) => {
      const copy = [...m];
      const last = copy[copy.length - 1];
      if (last?.role === "assistant") {
        copy[copy.length - 1] = { ...last, content: last.content + text, streaming };
      }
      return copy;
    });
  }

  function finalizeAssistant(stopped = false) {
    patchChatSession({ workflowStep: "" });
    updateMessages((m) => {
      const copy = [...m];
      const last = copy[copy.length - 1];
      if (last?.role === "assistant") {
        copy[copy.length - 1] = {
          ...last,
          streaming: false,
          content: last.content || (stopped ? "[Stopped]" : last.content),
        };
      }
      return copy;
    });
  }

  function onStop() {
    if (!busy) return;
    cancelChatStream();
    void stopChatStream(activeRunId.current || undefined).catch(() => undefined);
    finalizeAssistant(true);
    patchChatSession({ busy: false });
    setPendingConfirm(null);
  }

  async function onFeedback(rating: "up" | "down") {
    if (!chatId || feedbackBusy) return;
    setFeedbackBusy(true);
    try {
      await sendLearningFeedback({
        chat_id: chatId,
        skill_id: skillId || null,
        rating,
        user_goal: messages.find((m) => m.role === "user")?.content || "",
      });
    } catch (err: any) {
      setPresetError(String(err.message || err));
    } finally {
      setFeedbackBusy(false);
    }
  }

  async function onPromoteSkill() {
    if (!chatId || feedbackBusy) return;
    setFeedbackBusy(true);
    setPresetError("");
    try {
      const draft = await skillFromChat({ chat_id: chatId, save: false });
      if (!window.confirm(`Promote skill draft "${draft.draft?.name || "learned"}"?`)) return;
      await skillFromChat({ chat_id: chatId, save: true, name: draft.draft?.name });
      navigate("/skills");
    } catch (err: any) {
      setPresetError(String(err.message || err));
    } finally {
      setFeedbackBusy(false);
    }
  }

  async function onConfirmTool(approved: boolean) {
    if (!pendingConfirm) return;
    const { runId } = pendingConfirm;
    setPendingConfirm(null);
    try {
      await confirmRun(runId, approved);
    } catch (err: any) {
      setPresetError(String(err.message || err));
    }
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if ((!input.trim() && !pendingImage) || busy) return;
    const text = input.trim() || (pendingImage ? "Please look at this reference image." : "");
    const image = pendingImage;
    patchChatSession({ input: "" });
    setPendingImage(null);
    updateMessages((m) => [
      ...m,
      { role: "user", content: image ? `${text}\n[image: ${image.name}]` : text },
      { role: "assistant", content: "", streaming: true },
    ]);
    patchChatSession({ busy: true });
    const signal = armChatStream();
    activeRunId.current = null;
    try {
      await streamChat(
        {
          message: text,
          provider_id: providerId,
          model: model || null,
          skill_id: workflowId ? null : skillId || null,
          workflow_id: workflowId || null,
          chat_id: chatId || null,
          image_base64: image?.base64 || null,
          image_mime: image?.mime || "image/png",
        },
        (ev) => {
          if (ev.type === "status" && ev.data?.chat_id) patchChatSession({ chatId: ev.data.chat_id });
          if (ev.type === "status" && ev.data?.run_id) activeRunId.current = String(ev.data.run_id);
          if (ev.type === "status" && ev.content === "workflow_step") {
            const d = ev.data || {};
            patchChatSession({
              workflowStep: `${(d.index ?? 0) + 1}/${d.total || "?"} ${d.name || d.skill_id || ""}`,
            });
          }
          if (ev.type === "status" && ev.content === "confirm_request") {
            const runId = String(ev.data?.run_id || activeRunId.current || "");
            if (runId) {
              setPendingConfirm({
                runId,
                tool: String(ev.data?.tool || ev.content),
                reason: String(ev.data?.reason || ""),
              });
            }
            appendToAssistant(`\n⏸ Confirm required: ${ev.data?.tool || "tool"}\n`);
          }
          if (ev.type === "status" && ev.content === "stopped") {
            finalizeAssistant(true);
          }
          if (ev.type === "token") {
            appendToAssistant(ev.content);
          }
          if (ev.type === "tool_call") {
            if (ev.data?.run_id) activeRunId.current = String(ev.data.run_id);
            appendToAssistant(`\n⚙ ${ev.content}\n`);
          }
          if (ev.type === "error") {
            appendToAssistant(`\n⚠ ${ev.content}`, false);
            reportClientLog("error", String(ev.content || "chat error"), undefined, "chat");
          }
          if (ev.type === "status" && ev.content === "tool_result") {
            const result = ev.data || {};
            if (result.ok) {
              appendToAssistant(`\n✓ tool ok${result.name ? `: ${result.name}` : ""}\n`);
            } else {
              appendToAssistant(`\n⚠ tool failed: ${result.error || "unknown error"}\n`);
              reportClientLog("warning", `tool failed: ${result.error || "unknown"}`, result, "chat");
            }
          }
          if (ev.type === "done") {
            finalizeAssistant(!!ev.data?.stopped);
          }
        },
        signal
      );
    } catch (err: any) {
      if (signal.aborted || err?.name === "AbortError") return;
      const msg = String(err.message || err);
      updateMessages((m) => [...m, { role: "system", content: msg }]);
      reportClientLog("error", msg, undefined, "chat");
    } finally {
      disarmChatStream();
      patchChatSession({ busy: false });
    }
  }

  const bridgeLabel =
    blenderConnected === null
      ? t("chat.bridge.unknown")
      : blenderConnected
        ? t("chat.bridge.connected")
        : t("chat.bridge.disconnected");

  return (
    <div className="chat-page">
      <div className="chat-head">
        <div>
          <div className="chat-title-row">
            <h2 className="page-title">{t("chat.title")}</h2>
            <span
              className={`bridge-pill ${
                blenderConnected === null ? "unknown" : blenderConnected ? "ok" : "bad"
              }`}
              title={blenderConnected ? undefined : t("chat.bridge.hint")}
            >
              {bridgeLabel}
            </span>
          </div>
          <p className="page-lead">{t("chat.lead")}</p>
          {blenderConnected === false && <p className="bridge-warn">{t("chat.bridge.hint")}</p>}
        </div>
        <div className="chat-controls">
          <Select
            label={t("chat.provider")}
            value={providerId}
            onChange={(value) => patchChatSession({ providerId: value })}
            options={providers.map((p) => ({ value: p.id, label: p.name }))}
          />
          <div className="ui-field">
            <span className="ui-label">{t("chat.model")}</span>
            <input value={model} onChange={(e) => patchChatSession({ model: e.target.value })} placeholder="auto" />
          </div>
          <Select
            label={t("chat.skill")}
            value={skillId}
            onChange={(value) => patchChatSession({ skillId: value })}
            options={[{ value: "", label: "—" }, ...skills.map((s) => ({ value: s.id, label: s.name || s.id }))]}
          />
          <Select
            label="Workflow"
            value={workflowId}
            onChange={(value) => patchChatSession({ workflowId: value })}
            options={[
              { value: "", label: "—" },
              ...workflows.map((w) => ({ value: w.id, label: w.name || w.id })),
            ]}
          />
          {workflowStep ? <span className="bridge-pill ok">{workflowStep}</span> : null}
          <button
            type="button"
            className="chat-preset-btn primary"
            onClick={() => {
              if (busy) return;
              if ((messages.length > 0 || chatId) && !window.confirm(t("chat.newChatConfirm"))) return;
              startNewChatSession();
              setPresetError("");
            }}
            disabled={busy}
          >
            {t("chat.newChat")}
          </button>
          <button
            type="button"
            className="chat-preset-btn"
            onClick={saveAsPreset}
            disabled={presetBusy || busy || messages.filter((m) => m.role === "user" || m.role === "assistant").length === 0}
          >
            {t("chat.saveAsPreset")}
          </button>
          <button
            type="button"
            className="chat-preset-btn"
            onClick={() => {
              if (busy) return;
              if (messages.length > 0 && !window.confirm(t("chat.clearConfirm"))) return;
              clearChatSession();
              setPresetError("");
            }}
            disabled={busy || messages.length === 0}
          >
            {t("chat.clearHistory")}
          </button>
        </div>
      </div>

      {presetError ? <p className="bridge-warn">{presetError}</p> : null}
      {pendingConfirm ? (
        <div className="bridge-warn confirm-bar">
          Confirm tool <code>{pendingConfirm.tool}</code>
          {pendingConfirm.reason ? ` — ${pendingConfirm.reason}` : ""}
          <button type="button" className="chat-preset-btn primary" onClick={() => onConfirmTool(true)}>
            Approve
          </button>
          <button type="button" className="chat-preset-btn" onClick={() => onConfirmTool(false)}>
            Deny
          </button>
        </div>
      ) : null}

      <div className="chat-log card">
        {messages.length === 0 && <p className="empty-hint">BlenderAI ready.</p>}
        {messages.map((m, i) => (
          <div key={i} className={`bubble ${m.role} ${m.streaming ? "stream-cursor" : ""}`}>
            <pre>{m.content}</pre>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      <div className="chat-feedback-row">
        <button type="button" className="chat-preset-btn" disabled={!chatId || feedbackBusy || busy} onClick={() => onFeedback("up")}>
          Helpful
        </button>
        <button type="button" className="chat-preset-btn" disabled={!chatId || feedbackBusy || busy} onClick={() => onFeedback("down")}>
          Not helpful
        </button>
        <button type="button" className="chat-preset-btn" disabled={!chatId || feedbackBusy || busy} onClick={onPromoteSkill}>
          Promote skill
        </button>
      </div>

      <form className="chat-form" onSubmit={onSubmit}>
        <textarea
          rows={3}
          value={input}
          onChange={(e) => patchChatSession({ input: e.target.value })}
          placeholder={t("chat.placeholder")}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              onSubmit(e as any);
            }
          }}
        />
        <label className="chat-attach">
          <input
            type="file"
            accept="image/*"
            disabled={busy}
            onChange={async (e) => {
              const file = e.target.files?.[0];
              e.target.value = "";
              if (!file) return;
              try {
                const parsed = await fileToBase64(file);
                setPendingImage({ ...parsed, name: file.name });
              } catch (err: any) {
                setPresetError(String(err.message || err));
              }
            }}
          />
          {pendingImage ? pendingImage.name : "Attach image"}
        </label>
        {busy ? (
          <button type="button" className="chat-stop-btn" onClick={onStop}>
            {t("chat.stop")}
          </button>
        ) : (
          <button className="primary" disabled={!input.trim() && !pendingImage}>
            {t("chat.send")}
          </button>
        )}
      </form>
    </div>
  );
}
