import { useState, type FormEvent } from "react";
import { useMutation } from "@tanstack/react-query";
import { useAssistantStatus } from "../lib/queries";
import { sendAssistantChat } from "../lib/assistantApi";
import type { AssistantMessage } from "../lib/assistantApi";
import { ApiError } from "../lib/apiClient";
import { QueryState } from "../components/QueryState";
import { Button } from "../components/Button";

/**
 * Grounded in the caller's real account data server-side (see
 * `backend/routers/assistant.py`) — this component never fabricates a
 * reply itself; it only ever renders what `POST /assistant/chat` returns,
 * or a plain unavailable state when the currently configured AI provider
 * (Groq, OpenAI, ...) isn't reachable. The exact reason comes from the
 * backend (`status.reason`) so this page never has to hardcode which
 * provider/env var is active — it stays accurate if that ever changes.
 */
export function AiAssistantPage() {
  const status = useAssistantStatus();

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-xl font-bold text-ink">AI Assistant</h1>

      <QueryState
        isLoading={status.isLoading}
        isError={status.isError}
        error={status.error}
        onRetry={() => void status.refetch()}
      >
        {status.data?.available ? (
          <Chat />
        ) : (
          <div className="flex flex-col items-center justify-center rounded-md border border-dashed border-line px-6 py-16 text-center">
            <h2 className="text-lg font-bold text-ink">AI Assistant unavailable</h2>
            <p className="mt-2 max-w-sm text-sm text-ink-muted">
              {status.data?.reason ??
                "The AI Assistant isn't configured on the server, so it can't answer right now."}
            </p>
          </div>
        )}
      </QueryState>
    </div>
  );
}

function Chat() {
  const [messages, setMessages] = useState<AssistantMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: sendAssistantChat,
    onSuccess: (result) => {
      setError(null);
      setMessages((prev) => [...prev, { role: "assistant", content: result.reply }]);
    },
    onError: (err) => {
      setError(err instanceof ApiError ? (err.detail ?? err.message) : "The assistant could not reply.");
    },
  });

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const content = draft.trim();
    if (!content || mutation.isPending) return;
    setError(null);
    const next = [...messages, { role: "user" as const, content }];
    setMessages(next);
    setDraft("");
    mutation.mutate(next);
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex min-h-[24rem] flex-col gap-3 rounded-md border border-line p-4">
        {messages.length === 0 && (
          <p className="my-auto text-center text-sm text-ink-faint">
            Ask about your positions, cash, or orders — answered from your real account data.
          </p>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
            <div
              className={`max-w-[75%] whitespace-pre-wrap rounded-md px-3 py-2 text-sm ${
                m.role === "user" ? "bg-accent-soft text-ink" : "border border-line text-ink"
              }`}
            >
              {m.content}
            </div>
          </div>
        ))}
        {mutation.isPending && (
          <div className="flex justify-start">
            <div className="max-w-[75%] rounded-md border border-line px-3 py-2 text-sm text-ink-faint">
              Thinking…
            </div>
          </div>
        )}
      </div>

      {error && (
        <p role="alert" className="rounded bg-down-soft px-3 py-2 text-sm text-down">
          {error}
        </p>
      )}

      <form onSubmit={handleSubmit} className="flex items-center gap-2">
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Ask about your portfolio…"
          disabled={mutation.isPending}
          className="flex-1 rounded border border-line-strong bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-ink focus:ring-1 focus:ring-ink/10"
        />
        <Button type="submit" disabled={mutation.isPending || !draft.trim()}>
          Send
        </Button>
      </form>
    </div>
  );
}
