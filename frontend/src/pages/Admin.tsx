import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "../auth/AuthContext";
import { useAdminStats, useAdminUsers, adminUsersKey } from "../lib/queries";
import { deleteUser, updateUser } from "../lib/adminApi";
import { ApiError } from "../lib/apiClient";
import { money } from "../lib/format";
import { StatTile } from "../components/StatTile";
import { QueryState } from "../components/QueryState";

/**
 * Client-side convenience only, matching `ProtectedRoute`'s own doc comment:
 * the sidebar already hides the Admin link from non-admins, but a non-admin
 * could still type the URL directly. Every `/admin/*` call independently
 * re-checks the caller's role server-side (`backend/deps.py::require_admin`)
 * regardless of what this shows.
 */
function NotAuthorized() {
  return (
    <div className="flex flex-col items-center justify-center rounded-md border border-dashed border-line px-6 py-16 text-center">
      <h1 className="text-lg font-bold text-ink">Administration</h1>
      <p className="mt-2 max-w-sm text-sm text-ink-muted">
        You don't have access to this page.
      </p>
    </div>
  );
}

export function AdminPage() {
  const { user: currentUser } = useAuth();

  if (currentUser && currentUser.role !== "admin") {
    return <NotAuthorized />;
  }

  return <AdminContent currentUserId={currentUser?.id ?? null} />;
}

function AdminContent({ currentUserId }: { currentUserId: number | null }) {
  const stats = useAdminStats();
  const users = useAdminUsers();
  const queryClient = useQueryClient();
  const [rowError, setRowError] = useState<Record<number, string>>({});
  const [confirmingDelete, setConfirmingDelete] = useState<number | null>(null);

  function invalidate() {
    void queryClient.invalidateQueries({ queryKey: adminUsersKey });
    void queryClient.invalidateQueries({ queryKey: ["admin", "stats"] });
  }

  function setError(userId: number, message: string | null) {
    setRowError((prev) => {
      const next = { ...prev };
      if (message) next[userId] = message;
      else delete next[userId];
      return next;
    });
  }

  const roleMutation = useMutation({
    mutationFn: ({ id, role }: { id: number; role: "user" | "admin" }) => updateUser(id, { role }),
    onSuccess: (_, { id }) => {
      setError(id, null);
      invalidate();
    },
    onError: (err, { id }) => {
      setError(id, err instanceof ApiError ? (err.detail ?? err.message) : "Could not update role.");
    },
  });

  const activeMutation = useMutation({
    mutationFn: ({ id, is_active }: { id: number; is_active: boolean }) => updateUser(id, { is_active }),
    onSuccess: (_, { id }) => {
      setError(id, null);
      invalidate();
    },
    onError: (err, { id }) => {
      setError(id, err instanceof ApiError ? (err.detail ?? err.message) : "Could not update status.");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteUser(id),
    onSuccess: (_, id) => {
      setError(id, null);
      setConfirmingDelete(null);
      invalidate();
    },
    onError: (err, id) => {
      setConfirmingDelete(null);
      setError(id, err instanceof ApiError ? (err.detail ?? err.message) : "Could not delete user.");
    },
  });

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-xl font-bold text-ink">Administration</h1>

      <QueryState
        isLoading={stats.isLoading}
        isError={stats.isError}
        error={stats.error}
        onRetry={() => void stats.refetch()}
      >
        {stats.data && (
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <StatTile label="Total Users" value={String(stats.data.total_users)} />
            <StatTile
              label="Active / Disabled"
              value={`${stats.data.active_users} / ${stats.data.disabled_users}`}
            />
            <StatTile label="Admins" value={String(stats.data.admin_users)} />
            <StatTile label="Total Simulated Cash" value={money(stats.data.total_cash)} />
            <StatTile label="Total Orders" value={String(stats.data.total_orders)} />
            <StatTile label="Open Orders" value={String(stats.data.total_open_orders)} />
            <StatTile label="Accounts" value={String(stats.data.total_accounts)} />
            <StatTile label="Backend Version" value={stats.data.backend_version} />
          </div>
        )}
      </QueryState>

      <div className="rounded-md border border-line">
        <div className="border-b border-line px-4 py-2.5 text-sm font-bold text-ink">Users</div>
        <QueryState
          isLoading={users.isLoading}
          isError={users.isError}
          error={users.error}
          onRetry={() => void users.refetch()}
          isEmpty={users.data?.length === 0}
          emptyMessage="No users."
        >
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-faint">
                  <th className="px-4 py-2 font-semibold">User</th>
                  <th className="px-4 py-2 font-semibold">Email</th>
                  <th className="px-4 py-2 font-semibold">Role</th>
                  <th className="px-4 py-2 font-semibold">Status</th>
                  <th className="px-4 py-2 font-semibold">Joined</th>
                  <th className="px-4 py-2 font-semibold"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line-soft">
                {users.data?.map((u) => {
                  const isSelf = u.id === currentUserId;
                  const busy =
                    (roleMutation.isPending && roleMutation.variables?.id === u.id) ||
                    (activeMutation.isPending && activeMutation.variables?.id === u.id) ||
                    (deleteMutation.isPending && deleteMutation.variables === u.id);
                  return (
                    <tr key={u.id}>
                      <td className="px-4 py-2.5">
                        <div className="font-semibold text-ink">
                          {u.full_name} {isSelf && <span className="text-xs text-ink-faint">(you)</span>}
                        </div>
                        <div className="font-mono text-xs text-ink-muted">@{u.username}</div>
                      </td>
                      <td className="px-4 py-2.5 text-ink-muted">{u.email}</td>
                      <td className="px-4 py-2.5">
                        <span
                          className={`rounded px-2 py-0.5 text-xs font-semibold ${
                            u.role === "admin" ? "bg-accent-soft text-ink" : "bg-surface-alt text-ink-muted"
                          }`}
                        >
                          {u.role}
                        </span>
                      </td>
                      <td className="px-4 py-2.5">
                        <span
                          className={`rounded px-2 py-0.5 text-xs font-semibold ${
                            u.is_active ? "bg-up-soft text-up" : "bg-down-soft text-down"
                          }`}
                        >
                          {u.is_active ? "Active" : "Disabled"}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 text-xs text-ink-faint">
                        {new Date(u.created_at).toLocaleDateString()}
                      </td>
                      <td className="px-4 py-2.5">
                        <div className="flex items-center justify-end gap-3 text-xs font-semibold">
                          <button
                            disabled={isSelf || busy}
                            onClick={() =>
                              roleMutation.mutate({ id: u.id, role: u.role === "admin" ? "user" : "admin" })
                            }
                            className="text-ink-muted hover:text-ink disabled:cursor-not-allowed disabled:opacity-40"
                          >
                            {u.role === "admin" ? "Make user" : "Make admin"}
                          </button>
                          <button
                            disabled={isSelf || busy}
                            onClick={() => activeMutation.mutate({ id: u.id, is_active: !u.is_active })}
                            className="text-ink-muted hover:text-ink disabled:cursor-not-allowed disabled:opacity-40"
                          >
                            {u.is_active ? "Disable" : "Enable"}
                          </button>
                          {confirmingDelete === u.id ? (
                            <button
                              disabled={busy}
                              onClick={() => deleteMutation.mutate(u.id)}
                              className="text-down hover:underline disabled:cursor-not-allowed disabled:opacity-40"
                            >
                              Confirm delete?
                            </button>
                          ) : (
                            <button
                              disabled={isSelf || busy}
                              onClick={() => setConfirmingDelete(u.id)}
                              className="text-ink-muted hover:text-down disabled:cursor-not-allowed disabled:opacity-40"
                            >
                              Delete
                            </button>
                          )}
                        </div>
                        {rowError[u.id] && (
                          <div className="mt-1 text-right text-xs text-down">{rowError[u.id]}</div>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </QueryState>
      </div>
    </div>
  );
}
