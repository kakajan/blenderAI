export type Provider = {
  id: string;
  kind: string;
  name: string;
  enabled: boolean;
  base_url?: string;
  default_model?: string;
  has_api_key?: boolean;
  api_key_masked?: string;
  sort_order?: number;
};

export type AppSettings = {
  language: string;
  ui_direction: string;
  autonomy: string;
  local_only: boolean;
  learning_enabled?: boolean;
  fallback_chain: string[];
  default_provider_id: string;
  default_chat_model: string;
  default_skill_model: string;
  mcp_token_masked: string;
  has_mcp_token: boolean;
};

const TOKEN_HEADER = "X-BlenderAI-Token";
const TOKEN_STORAGE_KEY = "blenderai_auth_token";

let cachedToken = "";
let authPromise: Promise<string> | null = null;

function readStoredToken(): string {
  try {
    if (typeof sessionStorage !== "undefined") {
      return sessionStorage.getItem(TOKEN_STORAGE_KEY) || "";
    }
  } catch {
    /* ignore */
  }
  return "";
}

function storeToken(token: string): void {
  cachedToken = token;
  try {
    if (typeof sessionStorage !== "undefined") {
      if (token) sessionStorage.setItem(TOKEN_STORAGE_KEY, token);
      else sessionStorage.removeItem(TOKEN_STORAGE_KEY);
    }
  } catch {
    /* ignore */
  }
}

export function getAuthToken(): string {
  if (cachedToken) return cachedToken;
  const stored = readStoredToken();
  if (stored) cachedToken = stored;
  return cachedToken;
}

/** Loopback bootstrap: GET /api/auth/session → cache token in memory (+ sessionStorage). */
export async function ensureAuth(): Promise<string> {
  const existing = getAuthToken();
  if (existing) return existing;
  if (!authPromise) {
    authPromise = (async () => {
      const res = await fetch("/api/auth/session", {
        headers: { Accept: "application/json" },
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || res.statusText);
      }
      const data = (await res.json()) as { token?: string; mcp_token?: string };
      const token = String(data.token || data.mcp_token || "").trim();
      if (!token) throw new Error("Auth session returned no token");
      storeToken(token);
      return token;
    })().finally(() => {
      authPromise = null;
    });
  }
  return authPromise;
}

// Kick off token fetch as soon as the module loads (non-blocking).
void ensureAuth().catch(() => undefined);

function headersToRecord(init?: HeadersInit): Record<string, string> {
  if (!init) return {};
  if (init instanceof Headers) {
    const out: Record<string, string> = {};
    init.forEach((value, key) => {
      out[key] = value;
    });
    return out;
  }
  if (Array.isArray(init)) {
    return Object.fromEntries(init);
  }
  return { ...init };
}

async function withAuthHeaders(init?: HeadersInit): Promise<Record<string, string>> {
  let token = getAuthToken();
  if (!token) {
    try {
      token = await ensureAuth();
    } catch {
      token = getAuthToken();
    }
  }
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...headersToRecord(init),
  };
  if (token) headers[TOKEN_HEADER] = token;
  return headers;
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = await withAuthHeaders(init?.headers);
  const res = await fetch(path, {
    ...init,
    headers,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }
  return res.json() as Promise<T>;
}

export const getHealth = () => req<{ ok: boolean; blender_connected: boolean }>("/health");
export const getProviders = () => req<{ providers: Provider[] }>("/api/providers");
export const putProvider = (body: Record<string, unknown>) =>
  req<Provider>("/api/providers", { method: "PUT", body: JSON.stringify(body) });
export const testProvider = (id: string) =>
  req<{ ok: boolean; message: string }>(`/api/providers/${id}/test`, { method: "POST" });
export const getModels = (id: string) =>
  req<{ models: { id: string; name?: string }[] }>(`/api/providers/${id}/models`);
export const getSettings = () => req<AppSettings>("/api/settings");
export const putSettings = (body: Record<string, unknown>) =>
  req<AppSettings>("/api/settings", { method: "PUT", body: JSON.stringify(body) });
export const getSkills = () =>
  req<{ skills: any[]; known_tools?: string[] }>("/api/skills");
export const getSkill = (id: string) =>
  req<{ skill: any }>(`/api/skills/${encodeURIComponent(id)}`);
export const createSkill = (body: Record<string, unknown>) =>
  req<{ skill: any }>("/api/skills", { method: "POST", body: JSON.stringify(body) });
export const updateSkill = (id: string, body: Record<string, unknown>) =>
  req<{ skill: any }>(`/api/skills/${encodeURIComponent(id)}`, {
    method: "PUT",
    body: JSON.stringify(body),
  });
export const deleteSkill = (id: string) =>
  req<{ ok: boolean }>(`/api/skills/${encodeURIComponent(id)}`, { method: "DELETE" });
export const reloadSkills = () =>
  req<{ ok: boolean; count: number }>("/api/skills/reload", { method: "POST" });
export const getPresets = () => req<{ presets: any[] }>("/api/presets");
export const getWorkflows = () =>
  req<{ workflows: { id: string; name: string; description?: string; steps: any[] }[] }>("/api/workflows");
export const getPreset = (id: string) =>
  req<{ preset: any }>(`/api/presets/${encodeURIComponent(id)}`);
export const createPreset = (body: Record<string, unknown>) =>
  req<{ preset: any }>("/api/presets", { method: "POST", body: JSON.stringify(body) });
export const updatePreset = (id: string, body: Record<string, unknown>) =>
  req<{ preset: any }>(`/api/presets/${encodeURIComponent(id)}`, {
    method: "PUT",
    body: JSON.stringify(body),
  });
export const deletePreset = (id: string) =>
  req<{ ok: boolean }>(`/api/presets/${encodeURIComponent(id)}`, { method: "DELETE" });
export const reloadPresets = () =>
  req<{ ok: boolean; count: number }>("/api/presets/reload", { method: "POST" });
export const presetFromChat = (body: Record<string, unknown>) =>
  req<{ draft: any; preset?: any }>("/api/presets/from-chat", {
    method: "POST",
    body: JSON.stringify(body),
  });
export const getChats = () => req<{ chats: any[] }>("/api/chats");
export const getMessages = (id: string) => req<{ messages: any[] }>(`/api/chats/${id}/messages`);
export const clearChats = () => req<{ ok: boolean; deleted: number }>("/api/chats", { method: "DELETE" });

export type LogEntry = {
  id?: string;
  ts: string;
  level: string;
  source: string;
  component?: string;
  message: string;
  detail?: Record<string, unknown>;
};

export type ReportEntry = {
  id: string;
  ts: string;
  kind: string;
  source: string;
  summary: string;
  detail?: Record<string, unknown>;
  file_path?: string;
};

export const getLogs = (params?: { level?: string; source?: string; limit?: number }) => {
  const q = new URLSearchParams();
  if (params?.level) q.set("level", params.level);
  if (params?.source) q.set("source", params.source);
  if (params?.limit) q.set("limit", String(params.limit));
  const qs = q.toString();
  return req<{ logs: LogEntry[] }>(`/api/logs${qs ? `?${qs}` : ""}`);
};

export const postLog = (body: {
  level: string;
  source?: string;
  component?: string;
  message: string;
  detail?: Record<string, unknown>;
}) =>
  req<LogEntry>("/api/logs", {
    method: "POST",
    body: JSON.stringify({ source: "webui", ...body }),
  });

export const clearLogs = () => req<{ ok: boolean; deleted: number }>("/api/logs", { method: "DELETE" });

export const getReports = (limit = 50) =>
  req<{ reports: ReportEntry[] }>(`/api/reports?limit=${limit}`);

export const postReport = (body: {
  kind?: string;
  source?: string;
  summary: string;
  note?: string;
  detail?: Record<string, unknown>;
}) =>
  req<ReportEntry>("/api/reports", {
    method: "POST",
    body: JSON.stringify({ source: "webui", kind: "error", ...body }),
  });

/** Fire-and-forget client log (never throws). */
export function reportClientLog(
  level: "warning" | "error" | "crash",
  message: string,
  detail?: Record<string, unknown>,
  component = "webui"
) {
  void postLog({ level, message, component, detail }).catch(() => undefined);
}

export const stopChatStream = (runId?: string) =>
  req<{ ok: boolean; stopped: boolean }>("/api/chat/stop", {
    method: "POST",
    body: JSON.stringify({ run_id: runId || null }),
  });

export const confirmRun = (runId: string, approved = true) =>
  req<{ ok: boolean }>(`/api/runs/${encodeURIComponent(runId)}/confirm`, {
    method: "POST",
    body: JSON.stringify({ approved }),
  });

export const sendLearningFeedback = (body: {
  chat_id?: string | null;
  skill_id?: string | null;
  rating: "up" | "down" | "positive" | "negative";
  note?: string;
  user_goal?: string;
}) =>
  req<{ ok: boolean; learning: any }>("/api/learnings/feedback", {
    method: "POST",
    body: JSON.stringify(body),
  });

export const clearLearnings = (skillId?: string) => {
  const q = skillId ? `?skill_id=${encodeURIComponent(skillId)}` : "";
  return req<{ ok: boolean; deleted: number }>(`/api/learnings${q}`, { method: "DELETE" });
};

export const skillFromChat = (body: Record<string, unknown>) =>
  req<{ draft: any; skill?: any; eval?: any }>("/api/skills/from-chat", {
    method: "POST",
    body: JSON.stringify(body),
  });

export async function streamChat(
  body: Record<string, unknown>,
  onEvent: (ev: any) => void,
  signal?: AbortSignal
): Promise<void> {
  const headers = await withAuthHeaders({
    "Content-Type": "application/json",
    Accept: "text/event-stream",
  });
  const res = await fetch("/api/chat/stream", {
    method: "POST",
    headers,
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok || !res.body) throw new Error(await res.text());
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split("\n\n");
      buffer = parts.pop() || "";
      for (const part of parts) {
        const line = part.trim();
        if (!line.startsWith("data:")) continue;
        try {
          onEvent(JSON.parse(line.slice(5).trim()));
        } catch {
          /* ignore */
        }
      }
    }
  } catch (err: any) {
    if (signal?.aborted || err?.name === "AbortError") return;
    throw err;
  }
}
