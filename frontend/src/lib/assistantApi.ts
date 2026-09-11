import { apiRequest } from "./apiClient";

export interface AssistantMessage {
  role: "user" | "assistant";
  content: string;
}

export interface AssistantStatus {
  available: boolean;
  // Additive fields the backend already sends (see
  // `backend/routers/assistant.py::AssistantStatusOut`) — `reason` is a
  // ready-to-display, provider-accurate explanation (e.g. "GROQ_API_KEY is
  // not configured on the server.") so this page never has to hardcode
  // which provider/env var is currently active.
  provider?: string | null;
  reason?: string | null;
}

export function getAssistantStatus(): Promise<AssistantStatus> {
  return apiRequest<AssistantStatus>("/assistant/status");
}

export function sendAssistantChat(messages: AssistantMessage[]): Promise<{ reply: string }> {
  return apiRequest<{ reply: string }>("/assistant/chat", {
    method: "POST",
    body: { messages },
  });
}
