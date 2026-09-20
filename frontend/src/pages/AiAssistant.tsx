import { useState, type FormEvent } from "react";
import { useMutation } from "@tanstack/react-query";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
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

/**
 * Renders the assistant's Markdown reply as real UI — headings, bold,
 * lists, tables and links — instead of literal `**`/`|`/`#` characters.
 * The backend's system prompt (`backend/routers/assistant.py`) asks the
 * model for clean Markdown (GFM tables for multi-row/multi-ticker data);
 * this is the other half of that contract. Styled to match Optiport's
 * existing card/table conventions, not a generic chat-bubble look.
 */
function AssistantMarkdown({ content }: { content: string }) {
  return (
    <div className="flex flex-col gap-2 text-sm text-ink [&>*:first-child]:mt-0 [&>*:last-child]:mb-0">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ children }) => <div className="mt-2 text-sm font-bold text-ink">{children}</div>,
          h2: ({ children }) => (
            <div className="mt-2 text-xs font-bold uppercase tracking-wide text-ink-faint">{children}</div>
          ),
          h3: ({ children }) => <div className="mt-1 text-sm font-semibold text-ink">{children}</div>,
          p: ({ children }) => <p className="leading-relaxed">{children}</p>,
          strong: ({ children }) => <strong className="font-semibold text-ink">{children}</strong>,
          ul: ({ children }) => <ul className="flex list-disc flex-col gap-1 pl-5">{children}</ul>,
          ol: ({ children }) => <ol className="flex list-decimal flex-col gap-1 pl-5">{children}</ol>,
          li: ({ children }) => <li>{children}</li>,
          a: ({ href, children }) => (
            <a
              href={href}
              target="_blank"
              rel="noreferrer"
              className="font-medium text-accent underline underline-offset-2 hover:text-accent-hover"
            >
              {children}
            </a>
          ),
          code: ({ children }) => (
            <code className="rounded bg-surface-alt px-1 py-0.5 font-mono text-xs text-ink">{children}</code>
          ),
          blockquote: ({ children }) => (
            <blockquote className="border-l-2 border-line-strong pl-3 text-ink-muted italic">
              {children}
            </blockquote>
          ),
          hr: () => <hr className="border-line-soft" />,
          table: ({ children }) => (
            <div className="overflow-x-auto rounded border border-line">
              <table className="w-full min-w-[360px] text-xs">{children}</table>
            </div>
          ),
          thead: ({ children }) => <thead className="bg-surface-alt">{children}</thead>,
          th: ({ children }) => (
            <th className="border-b border-line px-2.5 py-1.5 text-left font-semibold uppercase tracking-wide text-ink-faint">
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td className="border-b border-line-soft px-2.5 py-1.5 align-top">{children}</td>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}

const SUGGESTED_PROMPTS = [
  "What's my portfolio value?",
  "Show my current positions",
  "What's the latest forecast for SPY?",
  "Any news on QQQ?",
];

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

  function submitMessage(content: string) {
    if (!content || mutation.isPending) return;
    setError(null);
    const next = [...messages, { role: "user" as const, content }];
    setMessages(next);
    setDraft("");
    mutation.mutate(next);
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    submitMessage(draft.trim());
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex min-h-[24rem] flex-col gap-3 rounded-md border border-line p-4">
        {messages.length === 0 && (
          <div className="my-auto flex flex-col items-center gap-4 text-center">
            <p className="text-sm text-ink-faint">
              Ask about your positions, cash, or orders — answered from your real account data.
            </p>
            <div className="flex flex-wrap justify-center gap-2">
              {SUGGESTED_PROMPTS.map((prompt) => (
                <button
                  key={prompt}
                  type="button"
                  onClick={() => submitMessage(prompt)}
                  disabled={mutation.isPending}
                  className="rounded-full border border-line-strong px-3 py-1.5 text-xs font-medium text-ink-muted transition-colors hover:border-ink hover:text-ink disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {prompt}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((m, i) =>
          m.role === "user" ? (
            <div key={i} className="flex justify-end">
              <div className="max-w-[75%] whitespace-pre-wrap rounded-md bg-accent-soft px-3 py-2 text-sm text-ink">
                {m.content}
              </div>
            </div>
          ) : (
            <div key={i} className="flex justify-start">
              <div className="max-w-[92%] rounded-md border border-line px-3 py-2 sm:max-w-[85%]">
                <AssistantMarkdown content={m.content} />
              </div>
            </div>
          ),
        )}
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
