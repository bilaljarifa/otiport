import { useMemo, useState, type ReactNode } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "../auth/AuthContext";
import { useAdminStats, useAdminUsers, adminUsersKey } from "../lib/queries";
import { deleteUser, updateUser } from "../lib/adminApi";
import { ApiError } from "../lib/apiClient";
import { money } from "../lib/format";
import type { User } from "../lib/authApi";
import { StatTile } from "../components/StatTile";
import { QueryState } from "../components/QueryState";
import { FilterGroup } from "../components/FilterGroup";

type RoleFilter = "all" | "admin" | "user";
type StatusFilter = "all" | "active" | "disabled";

/**
 * Client-side convenience only, matching `ProtectedRoute`'s own doc comment:
 * the sidebar already hides the Admin link from non-admins, but a non-admin
 * could still type the URL directly. Every `/admin/*` call independently
 * re-checks the caller's role server-side (`backend/deps.py::require_admin`)
 * regardless of what this shows — this page never makes an authorization
 * decision the backend doesn't also enforce.
 */
function NotAuthorized() {
  return (
    <div className="flex flex-col items-center justify-center rounded-md border border-dashed border-line px-6 py-20 text-center">
      <ShieldIcon className="mb-4 h-9 w-9 text-ink-faint" />
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
  const [pendingDelete, setPendingDelete] = useState<User | null>(null);
  const [detailUser, setDetailUser] = useState<User | null>(null);

  const [search, setSearch] = useState("");
  const [roleFilter, setRoleFilter] = useState<RoleFilter>("all");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");

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
      setPendingDelete(null);
      invalidate();
    },
    onError: (err, id) => {
      setError(id, err instanceof ApiError ? (err.detail ?? err.message) : "Could not delete user.");
    },
  });

  const filteredUsers = useMemo(() => {
    const q = search.trim().toLowerCase();
    return (users.data ?? []).filter((u) => {
      if (roleFilter !== "all" && u.role !== roleFilter) return false;
      if (statusFilter === "active" && !u.is_active) return false;
      if (statusFilter === "disabled" && u.is_active) return false;
      if (q && !`${u.full_name} ${u.username} ${u.email}`.toLowerCase().includes(q)) return false;
      return true;
    });
  }, [users.data, search, roleFilter, statusFilter]);

  return (
    <div className="flex flex-col gap-7">
      {/* 1. HEADER */}
      <div className="flex items-start gap-3">
        <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-line bg-surface-alt">
          <ShieldIcon className="h-4.5 w-4.5 text-ink" />
        </span>
        <div>
          <h1 className="text-xl font-bold tracking-tight text-ink">Administration</h1>
          <p className="mt-1 max-w-xl text-sm text-ink-muted">
            Manage Optiport user accounts, roles and platform access. Actions here take
            effect immediately and are enforced by the backend on every request.
          </p>
        </div>
      </div>

      {/* 2. OVERVIEW KPI CARDS */}
      <QueryState
        isLoading={stats.isLoading}
        isError={stats.isError}
        error={stats.error}
        onRetry={() => void stats.refetch()}
      >
        {stats.data && (
          <div className="flex flex-col gap-3">
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <StatTile label="Total users" value={String(stats.data.total_users)} />
              <StatTile
                label="Active users"
                value={String(stats.data.active_users)}
                delta={{ value: `${stats.data.disabled_users} disabled`, positive: stats.data.disabled_users === 0 }}
              />
              <StatTile label="Admin users" value={String(stats.data.admin_users)} />
              <StatTile label="Accounts" value={String(stats.data.total_accounts)} />
            </div>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <StatTile label="Total simulated cash" value={money(stats.data.total_cash)} />
              <StatTile label="Total orders" value={String(stats.data.total_orders)} />
              <StatTile label="Open orders" value={String(stats.data.total_open_orders)} />
              <StatTile label="Backend version" value={stats.data.backend_version} />
            </div>
          </div>
        )}
      </QueryState>

      {/* 3 & 4. USER MANAGEMENT + SEARCH/FILTERS */}
      <div className="overflow-hidden rounded-md border border-line">
        <div className="flex flex-col gap-3 border-b border-line p-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="text-sm font-bold text-ink">Users</div>
            <p className="text-xs text-ink-faint">
              {users.data ? `${filteredUsers.length} of ${users.data.length} shown` : " "}
            </p>
          </div>
          <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center">
            <div className="relative">
              <SearchIcon className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-ink-faint" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search name, username or email"
                className="h-8 w-full rounded-md border border-line-strong bg-surface pl-8 pr-3 text-sm text-ink outline-none transition-colors focus:border-ink focus:ring-1 focus:ring-ink/10 sm:w-64"
              />
            </div>
            <FilterGroup
              value={roleFilter}
              onChange={setRoleFilter}
              options={[
                { value: "all", label: "All roles" },
                { value: "admin", label: "Admin" },
                { value: "user", label: "User" },
              ]}
            />
            <FilterGroup
              value={statusFilter}
              onChange={setStatusFilter}
              options={[
                { value: "all", label: "All status" },
                { value: "active", label: "Active" },
                { value: "disabled", label: "Disabled" },
              ]}
            />
          </div>
        </div>

        <QueryState
          isLoading={users.isLoading}
          isError={users.isError}
          error={users.error}
          onRetry={() => void users.refetch()}
        >
          {users.data && users.data.length === 0 ? (
            <EmptyState message="No users exist yet." />
          ) : filteredUsers.length === 0 ? (
            <EmptyState message="No users match your search or filters." />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-faint">
                    <th className="px-4 py-2.5 font-semibold">User</th>
                    <th className="px-4 py-2.5 font-semibold">Email</th>
                    <th className="px-4 py-2.5 font-semibold">Role</th>
                    <th className="px-4 py-2.5 font-semibold">Status</th>
                    <th className="px-4 py-2.5 font-semibold">Created</th>
                    <th className="px-4 py-2.5 font-semibold text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line-soft">
                  {filteredUsers.map((u) => {
                    const isSelf = u.id === currentUserId;
                    const busy =
                      (roleMutation.isPending && roleMutation.variables?.id === u.id) ||
                      (activeMutation.isPending && activeMutation.variables?.id === u.id) ||
                      (deleteMutation.isPending && deleteMutation.variables === u.id);
                    return (
                      <tr key={u.id} className="transition-colors hover:bg-surface-alt">
                        <td className="px-4 py-3">
                          <button
                            onClick={() => setDetailUser(u)}
                            className="flex items-center gap-2.5 text-left"
                          >
                            <Avatar name={u.full_name || u.username} />
                            <span>
                              <span className="block font-semibold text-ink">
                                {u.full_name}
                                {isSelf && <span className="ml-1.5 text-xs font-normal text-ink-faint">(you)</span>}
                              </span>
                              <span className="block font-mono text-xs text-ink-muted">@{u.username}</span>
                            </span>
                          </button>
                        </td>
                        <td className="px-4 py-3 text-ink-muted">{u.email}</td>
                        <td className="px-4 py-3">
                          <RoleBadge role={u.role} />
                        </td>
                        <td className="px-4 py-3">
                          <StatusBadge active={u.is_active} />
                        </td>
                        <td className="px-4 py-3 text-xs text-ink-faint">
                          {new Date(u.created_at).toLocaleDateString()}
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex flex-wrap items-center justify-end gap-1.5">
                            <ActionButton
                              tone="neutral"
                              disabled={isSelf || busy}
                              onClick={() =>
                                roleMutation.mutate({ id: u.id, role: u.role === "admin" ? "user" : "admin" })
                              }
                            >
                              {u.role === "admin" ? "Make user" : "Make admin"}
                            </ActionButton>
                            <ActionButton
                              tone={u.is_active ? "warning" : "positive"}
                              disabled={isSelf || busy}
                              onClick={() => activeMutation.mutate({ id: u.id, is_active: !u.is_active })}
                            >
                              {u.is_active ? "Disable" : "Enable"}
                            </ActionButton>
                            <ActionButton
                              tone="danger"
                              disabled={isSelf || busy}
                              onClick={() => setPendingDelete(u)}
                            >
                              Delete
                            </ActionButton>
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
          )}
        </QueryState>
      </div>

      {/* 5. USER DETAILS */}
      {detailUser && (
        <UserDetailModal user={detailUser} isSelf={detailUser.id === currentUserId} onClose={() => setDetailUser(null)} />
      )}

      {/* Confirmation dialog for the destructive action */}
      {pendingDelete && (
        <ConfirmDeleteModal
          user={pendingDelete}
          isPending={deleteMutation.isPending}
          error={rowError[pendingDelete.id] ?? null}
          onCancel={() => {
            setError(pendingDelete.id, null);
            setPendingDelete(null);
          }}
          onConfirm={() => deleteMutation.mutate(pendingDelete.id)}
        />
      )}
    </div>
  );
}


type ActionTone = "neutral" | "positive" | "warning" | "danger";

const ACTION_TONE_CLASS: Record<ActionTone, string> = {
  neutral:
    "border-line-strong bg-surface text-ink-muted hover:border-ink hover:text-ink focus-visible:border-ink",
  positive:
    "border-line-strong bg-surface text-ink-muted hover:border-up hover:bg-up-soft hover:text-up focus-visible:border-up",
  warning:
    "border-line-strong bg-surface text-ink-muted hover:border-down hover:bg-down-soft hover:text-down focus-visible:border-down",
  danger:
    "border-down bg-down-soft text-down hover:bg-down hover:text-white focus-visible:border-down",
};

/** One consistent compact control for every row-level admin action — same
 * height/padding/radius/typography regardless of tone, so "Make admin",
 * "Disable"/"Enable" and "Delete" read as a coherent set rather than
 * unrelated text links. Tone only changes color, never layout. */
function ActionButton({
  tone,
  disabled,
  onClick,
  children,
}: {
  tone: ActionTone;
  disabled?: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className={`inline-flex h-7 items-center justify-center whitespace-nowrap rounded-md border px-2.5 text-xs font-semibold transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ink/20 disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-40 ${ACTION_TONE_CLASS[tone]}`}
    >
      {children}
    </button>
  );
}

function RoleBadge({ role }: { role: "admin" | "user" }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded px-2 py-0.5 text-xs font-semibold ${
        role === "admin" ? "bg-accent-soft text-ink" : "bg-surface-alt text-ink-muted"
      }`}
    >
      {role === "admin" && <ShieldIcon className="h-3 w-3" />}
      {role === "admin" ? "Admin" : "User"}
    </span>
  );
}

function StatusBadge({ active }: { active: boolean }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded px-2 py-0.5 text-xs font-semibold ${
        active ? "bg-up-soft text-up" : "bg-down-soft text-down"
      }`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${active ? "bg-up" : "bg-down"}`} />
      {active ? "Active" : "Disabled"}
    </span>
  );
}

function Avatar({ name }: { name: string }) {
  const initial = name.trim().charAt(0).toUpperCase() || "?";
  return (
    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-line bg-surface-alt text-xs font-bold text-ink-muted">
      {initial}
    </span>
  );
}

function EmptyState({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center justify-center px-4 py-14 text-center">
      <SearchIcon className="mb-3 h-6 w-6 text-ink-faint" />
      <p className="text-sm text-ink-muted">{message}</p>
    </div>
  );
}

function ModalShell({
  onClose,
  children,
  labelledBy,
}: {
  onClose: () => void;
  children: ReactNode;
  labelledBy: string;
}) {
  return (
    <div
      role="presentation"
      className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 px-4"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={labelledBy}
        onClick={(e) => e.stopPropagation()}
        className="hero-enter w-full max-w-md rounded-xl border border-line bg-surface p-6 shadow-[0_30px_60px_-20px_rgb(0_0_0_/_0.35)]"
      >
        {children}
      </div>
    </div>
  );
}

function UserDetailModal({ user, isSelf, onClose }: { user: User; isSelf: boolean; onClose: () => void }) {
  const fields: { label: string; value: string }[] = [
    { label: "Full name", value: user.full_name || "—" },
    { label: "Username", value: `@${user.username}` },
    { label: "Email", value: user.email },
    { label: "Role", value: user.role === "admin" ? "Admin" : "User" },
    { label: "Status", value: user.is_active ? "Active" : "Disabled" },
    { label: "Job title", value: user.job_title || "—" },
    { label: "Desk", value: user.desk || "—" },
    { label: "User ID", value: String(user.id) },
    { label: "Created", value: new Date(user.created_at).toLocaleString() },
  ];
  return (
    <ModalShell onClose={onClose} labelledBy="user-detail-title">
      <div className="mb-5 flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <Avatar name={user.full_name || user.username} />
          <div>
            <h2 id="user-detail-title" className="text-base font-bold text-ink">
              {user.full_name}
              {isSelf && <span className="ml-1.5 text-xs font-normal text-ink-faint">(you)</span>}
            </h2>
            <p className="font-mono text-xs text-ink-muted">@{user.username}</p>
          </div>
        </div>
        <button
          onClick={onClose}
          aria-label="Close"
          className="rounded p-1 text-ink-faint transition-colors hover:text-ink"
        >
          <CloseIcon className="h-4 w-4" />
        </button>
      </div>

      <dl className="flex flex-col gap-3">
        {fields.map((f) => (
          <div key={f.label} className="flex items-baseline justify-between gap-4 border-b border-line-soft pb-2 text-sm last:border-0 last:pb-0">
            <dt className="text-ink-faint">{f.label}</dt>
            <dd className="truncate text-right font-medium text-ink">{f.value}</dd>
          </div>
        ))}
      </dl>

      <p className="mt-5 text-xs text-ink-faint">
        Account credentials, tokens and password data are never exposed here or by any backend endpoint.
      </p>
    </ModalShell>
  );
}

function ConfirmDeleteModal({
  user,
  isPending,
  error,
  onCancel,
  onConfirm,
}: {
  user: User;
  isPending: boolean;
  error: string | null;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  return (
    <ModalShell onClose={onCancel} labelledBy="confirm-delete-title">
      <div className="mb-4 flex items-center gap-3">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-down-soft">
          <WarningIcon className="h-4.5 w-4.5 text-down" />
        </span>
        <h2 id="confirm-delete-title" className="text-base font-bold text-ink">
          Delete this user?
        </h2>
      </div>
      <p className="text-sm text-ink-muted">
        This permanently deletes <strong className="text-ink">{user.full_name}</strong>{" "}
        (@{user.username}) and everything tied to their account — positions, orders,
        transactions, watchlist and alerts. This cannot be undone.
      </p>
      {error && (
        <p role="alert" className="mt-3 rounded-md bg-down-soft px-3 py-2 text-sm text-down">
          {error}
        </p>
      )}
      <div className="mt-6 flex justify-end gap-2">
        <button
          onClick={onCancel}
          disabled={isPending}
          className="rounded-md border border-line-strong px-4 py-2 text-sm font-semibold text-ink-muted transition-colors hover:text-ink disabled:cursor-not-allowed disabled:opacity-50"
        >
          Cancel
        </button>
        <button
          onClick={onConfirm}
          disabled={isPending}
          className="rounded-md bg-down px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-down/90 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {isPending ? "Deleting…" : "Delete user"}
        </button>
      </div>
    </ModalShell>
  );
}

function ShieldIcon({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={className} aria-hidden="true">
      <path
        d="M12 3l7 3v5c0 4.5-3 8.5-7 10-4-1.5-7-5.5-7-10V6l7-3Z"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
      <path d="M9 12l2 2 4-4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function SearchIcon({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={className} aria-hidden="true">
      <circle cx="11" cy="11" r="7" stroke="currentColor" strokeWidth="1.8" />
      <path d="M21 21l-4.3-4.3" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

function CloseIcon({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={className} aria-hidden="true">
      <path d="M6 6l12 12M18 6L6 18" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

function WarningIcon({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={className} aria-hidden="true">
      <path
        d="M12 3.5 21 19.5H3L12 3.5Z"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
      <path d="M12 10v4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      <circle cx="12" cy="17" r="0.9" fill="currentColor" />
    </svg>
  );
}
