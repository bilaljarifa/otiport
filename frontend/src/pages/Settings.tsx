import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useTheme } from "../theme/ThemeContext";
import { resetAccount } from "../lib/portfolioApi";
import { Button } from "../components/Button";

export function SettingsPage() {
  const { theme, toggleTheme } = useTheme();
  const [confirmed, setConfirmed] = useState(false);
  const [done, setDone] = useState(false);
  const queryClient = useQueryClient();

  const resetMutation = useMutation({
    mutationFn: resetAccount,
    onSuccess: () => {
      setDone(true);
      setConfirmed(false);
      void queryClient.invalidateQueries({ queryKey: ["portfolio", "summary"] });
    },
  });

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-xl font-bold text-ink">Settings</h1>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="rounded-md border border-line p-6">
          <div className="mb-1 text-sm font-bold text-ink">Appearance</div>
          <p className="mb-4 text-sm text-ink-muted">
            Switch between the light and dark interface. This applies to the whole app and
            is remembered on this device.
          </p>
          <div className="flex items-center justify-between rounded border border-line-strong px-4 py-3">
            <span className="text-sm font-medium text-ink">
              Current theme: <span className="font-mono">{theme === "light" ? "Light" : "Dark"}</span>
            </span>
            <Button variant="secondary" onClick={toggleTheme}>
              Switch to {theme === "light" ? "Dark" : "Light"}
            </Button>
          </div>
        </div>

        <div className="rounded-md border border-line p-6">
          <div className="mb-1 text-sm font-bold text-ink">Danger zone</div>
          <p className="mb-4 text-sm text-ink-muted">
            Resets your simulated account back to $250,000 cash. This permanently clears your
            positions, orders, transaction history and alerts. Your watchlist is kept.
          </p>

          <div className="rounded border border-down-soft bg-down-soft px-4 py-3 text-sm text-down">
            This cannot be undone.
          </div>

          <label className="mt-4 flex items-center gap-2 text-sm text-ink">
            <input
              type="checkbox"
              checked={confirmed}
              onChange={(e) => {
                setConfirmed(e.target.checked);
                setDone(false);
              }}
              className="h-4 w-4 rounded border-line-strong"
            />
            I understand this will permanently reset my simulated account.
          </label>

          {done && (
            <p role="status" className="mt-3 rounded bg-up-soft px-3 py-2 text-sm text-up">
              Account reset.
            </p>
          )}
          {resetMutation.isError && (
            <p role="alert" className="mt-3 rounded bg-down-soft px-3 py-2 text-sm text-down">
              Could not reset the account. Please try again.
            </p>
          )}

          <Button
            className="mt-4"
            disabled={!confirmed || resetMutation.isPending}
            onClick={() => resetMutation.mutate()}
          >
            {resetMutation.isPending ? "Resetting…" : "Reset account"}
          </Button>
        </div>
      </div>
    </div>
  );
}
