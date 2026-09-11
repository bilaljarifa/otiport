import { useEffect, useState, type FormEvent } from "react";
import { useMutation } from "@tanstack/react-query";
import { useAuth } from "../auth/AuthContext";
import { updateProfile } from "../lib/authApi";
import { ApiError } from "../lib/apiClient";
import { usePortfolioSummary, useQuotes } from "../lib/queries";
import { computeValuation } from "../lib/valuation";
import { money, signedMoney, signedPercent } from "../lib/format";
import { StatTile } from "../components/StatTile";
import { QueryState } from "../components/QueryState";
import { Button } from "../components/Button";

const INPUT_CLASS =
  "rounded border border-line-strong bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-ink focus:ring-1 focus:ring-ink/10";

export function ProfilePage() {
  const { user, updateUser } = useAuth();
  const summary = usePortfolioSummary();
  const tickers = summary.data?.positions.map((p) => p.ticker) ?? [];
  const quotes = useQuotes(tickers);
  const hasPositions = tickers.length > 0;

  const [fullName, setFullName] = useState(user?.full_name ?? "");
  const [jobTitle, setJobTitle] = useState(user?.job_title ?? "");
  const [desk, setDesk] = useState(user?.desk ?? "");
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [formInitialized, setFormInitialized] = useState(Boolean(user));

  // `user` is still null on the very first render after a hard reload
  // (AuthContext hasn't finished re-fetching `/auth/me` yet) — the `useState`
  // initializers above only run once, so without this the fields would be
  // stuck empty even after the profile loads. Runs once, the first time a
  // user becomes available; a later update (e.g. this page's own save)
  // shouldn't re-clobber whatever is currently in the fields.
  useEffect(() => {
    if (user && !formInitialized) {
      setFullName(user.full_name);
      setJobTitle(user.job_title);
      setDesk(user.desk);
      setFormInitialized(true);
    }
  }, [user, formInitialized]);

  const mutation = useMutation({
    mutationFn: updateProfile,
    onSuccess: (updated) => {
      updateUser(updated);
      setSaved(true);
      setError(null);
    },
    onError: (err) => {
      setSaved(false);
      setError(err instanceof ApiError ? (err.detail ?? err.message) : "Could not update profile.");
    },
  });

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setSaved(false);
    const trimmedName = fullName.trim();
    if (!trimmedName) {
      setError("Display name is required.");
      return;
    }
    mutation.mutate({ full_name: trimmedName, job_title: jobTitle.trim(), desk: desk.trim() });
  }

  const valuation =
    summary.data && (!hasPositions || quotes.data)
      ? computeValuation(
          summary.data.positions,
          quotes.data?.quotes ?? {},
          summary.data.account.cash,
          summary.data.account.initial_cash,
        )
      : null;

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-xl font-bold text-ink">Profile</h1>

      <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
        <div className="flex flex-col gap-6">
          <div className="rounded-md border border-line p-6">
            <div className="mb-6 flex items-center gap-4">
              <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-full border border-line-strong bg-surface-alt text-lg font-bold text-ink">
                {(user?.full_name || user?.username || "?").slice(0, 1).toUpperCase()}
              </div>
              <div className="min-w-0">
                <div className="truncate text-lg font-bold text-ink">{user?.full_name}</div>
                <div className="truncate text-sm text-ink-muted">
                  @{user?.username} · {user?.email}
                </div>
              </div>
            </div>

            <form onSubmit={handleSubmit} className="flex flex-col gap-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <label className="flex flex-col gap-1.5 text-sm font-medium text-ink">
                  Display name
                  <input
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    className={INPUT_CLASS}
                  />
                </label>
                <label className="flex flex-col gap-1.5 text-sm font-medium text-ink">
                  Job title
                  <input
                    value={jobTitle}
                    onChange={(e) => setJobTitle(e.target.value)}
                    className={INPUT_CLASS}
                  />
                </label>
              </div>
              <label className="flex flex-col gap-1.5 text-sm font-medium text-ink">
                Desk / scope
                <input value={desk} onChange={(e) => setDesk(e.target.value)} className={INPUT_CLASS} />
              </label>

              <p className="text-xs text-ink-faint">
                Username, email and password can't be changed from this page.
              </p>

              {error && (
                <p role="alert" className="rounded bg-down-soft px-3 py-2 text-sm text-down">
                  {error}
                </p>
              )}
              {saved && !error && (
                <p role="status" className="rounded bg-up-soft px-3 py-2 text-sm text-up">
                  Profile updated.
                </p>
              )}

              <Button type="submit" disabled={mutation.isPending} className="self-start">
                {mutation.isPending ? "Saving…" : "Save changes"}
              </Button>
            </form>
          </div>

          <div className="rounded-md border border-line p-6">
            <div className="mb-4 text-sm font-bold text-ink">Security</div>
            <dl className="flex flex-col gap-2 text-sm">
              <div className="flex items-center justify-between">
                <dt className="text-ink-muted">Role</dt>
                <dd className="font-mono font-semibold text-ink">{user?.role}</dd>
              </div>
              <div className="flex items-center justify-between">
                <dt className="text-ink-muted">Password</dt>
                <dd className="text-ink">Hashed (bcrypt), never stored in plain text</dd>
              </div>
              <div className="flex items-center justify-between">
                <dt className="text-ink-muted">Real orders</dt>
                <dd className="text-ink">Never sent — simulated trading only</dd>
              </div>
              <div className="flex items-center justify-between">
                <dt className="text-ink-muted">Member since</dt>
                <dd className="text-ink">
                  {user?.created_at ? new Date(user.created_at).toLocaleDateString() : "—"}
                </dd>
              </div>
            </dl>
          </div>
        </div>

        <div className="rounded-md border border-line p-6">
          <div className="mb-4 text-sm font-bold text-ink">Account</div>
          <QueryState
            isLoading={summary.isLoading || (hasPositions && quotes.isLoading)}
            isError={summary.isError}
            error={summary.error}
            onRetry={() => void summary.refetch()}
          >
            {valuation && (
              <div className="grid grid-cols-2 gap-3">
                <StatTile label="Total Value" value={money(valuation.equity)} />
                <StatTile label="Cash" value={money(valuation.cash)} />
                <StatTile
                  label="Total P&L"
                  value={signedMoney(valuation.totalReturn)}
                  delta={{
                    value: signedPercent(valuation.totalReturnPct),
                    positive: valuation.totalReturn >= 0,
                  }}
                />
                <StatTile label="Positions" value={String(valuation.holdings.length)} />
              </div>
            )}
          </QueryState>
        </div>
      </div>
    </div>
  );
}
