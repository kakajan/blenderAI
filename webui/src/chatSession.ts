export type ChatMsg = {
  role: "user" | "assistant" | "system";
  content: string;
  streaming?: boolean;
};

let abortController: AbortController | null = null;

export function armChatStream(): AbortSignal {
  abortController?.abort();
  abortController = new AbortController();
  return abortController.signal;
}

export function disarmChatStream() {
  abortController = null;
}

export function cancelChatStream() {
  abortController?.abort();
  abortController = null;
}

type SessionState = {
  messages: ChatMsg[];
  chatId: string | undefined;
  providerId: string;
  model: string;
  skillId: string;
  workflowId: string;
  workflowStep: string;
  input: string;
  busy: boolean;
};

const state: SessionState = {
  messages: [],
  chatId: undefined,
  providerId: "ollama",
  model: "",
  skillId: "modeling.create_mesh",
  workflowId: "",
  workflowStep: "",
  input: "",
  busy: false,
};

function cloneState(source: SessionState): SessionState {
  return {
    ...source,
    messages: [...source.messages],
  };
}

let snapshot = cloneState(state);

type Listener = () => void;
const listeners = new Set<Listener>();

function publish() {
  snapshot = cloneState(state);
  listeners.forEach((l) => l());
}

export function getChatSession(): Readonly<SessionState> {
  return snapshot;
}

export function patchChatSession(patch: Partial<SessionState>) {
  Object.assign(state, patch);
  publish();
}

export function updateMessages(updater: ChatMsg[] | ((prev: ChatMsg[]) => ChatMsg[])) {
  state.messages = typeof updater === "function" ? updater(state.messages) : updater;
  publish();
}

export function clearChatSession() {
  cancelChatStream();
  state.messages = [];
  state.chatId = undefined;
  state.workflowStep = "";
  state.input = "";
  state.busy = false;
  publish();
}

/** Start a fresh conversation; keeps provider/model/skill settings. */
export function startNewChatSession() {
  cancelChatStream();
  state.messages = [];
  state.chatId = undefined;
  state.workflowStep = "";
  state.input = "";
  state.busy = false;
  publish();
}

export function subscribeChatSession(listener: Listener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

let defaultsApplied = false;
export function applyChatDefaults(providerId: string, model: string) {
  if (defaultsApplied) return;
  defaultsApplied = true;
  patchChatSession({ providerId, model });
}
