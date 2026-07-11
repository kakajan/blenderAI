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
  fallback_chain: string[];
  default_provider_id: string;
  default_chat_model: string;
  default_skill_model: string;
  mcp_token_masked: string;
  has_mcp_token: boolean;
};

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    ...init,
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
export const getChats = () => req<{ chats: any[] }>("/api/chats");
export const getMessages = (id: string) => req<{ messages: any[] }>(`/api/chats/${id}/messages`);

export async function streamChat(
  body: Record<string, unknown>,
  onEvent: (ev: any) => void
): Promise<void> {
  const res = await fetch("/api/chat/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok || !res.body) throw new Error(await res.text());
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
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
}
