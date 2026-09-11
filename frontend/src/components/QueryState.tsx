import type { ReactNode } from "react";
import { ApiError } from "../lib/apiClient";

/**
 * Every data-driven page routes through this instead of ad hoc
 * `if (isLoading) ...` scattered around — one place that guarantees a
 * loading, error and empty state always exist, per the "never silently
 * fail, never show fake data to hide a failure" requirement.
 */
export function QueryState({
  isLoading,
  isError,
  error,
  isEmpty,
  emptyMessage = "No data.",
  onRetry,
  children,
}: {
  isLoading: boolean;
  isError: boolean;
  error?: unknown;
  isEmpty?: boolean;
  emptyMessage?: string;
  onRetry?: () => void;
  children: ReactNode;
}) {
  if (isLoading) {
    return <div className="py-10 text-center text-sm text-ink-muted">Loading…</div>;
  }

  if (isError) {
    const message =
      error instanceof ApiError
        ? error.status === 0
          ? "Could not reach the backend."
          : error.detail ?? error.message
        : "Something went wrong.";
    return (
      <div className="rounded-md border border-down-soft bg-down-soft px-4 py-3 text-sm text-down">
        <p className="font-semibold">{message}</p>
        {onRetry && (
          <button onClick={onRetry} className="mt-2 font-semibold underline underline-offset-2">
            Retry
          </button>
        )}
      </div>
    );
  }

  if (isEmpty) {
    return (
      <div className="rounded-md border border-dashed border-line px-4 py-8 text-center text-sm text-ink-muted">
        {emptyMessage}
      </div>
    );
  }

  return <>{children}</>;
}
