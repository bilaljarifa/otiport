import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { ApiError, setAuthErrorHandler, setAuthToken } from "../lib/apiClient";
import * as authApi from "../lib/authApi";
import type { User } from "../lib/authApi";

const STORAGE_KEY = "optiport_token";

interface AuthContextValue {
  user: User | null;
  isAuthenticated: boolean;
  /** True only while restoring a persisted token on first load — lets the
   * app avoid a login-screen flash before we know whether the stored token
   * is still valid. */
  isLoading: boolean;
  loginWithCredentials: (username: string, password: string) => Promise<void>;
  registerAccount: (
    username: string,
    email: string,
    password: string,
    fullName: string,
  ) => Promise<void>;
  logout: () => Promise<void>;
  /** Sync a freshly updated profile (e.g. after `PATCH /auth/me`) into the
   * shared auth state, so the sidebar and anywhere else reading `user`
   * reflect it immediately without a full reload. */
  updateUser: (user: User) => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem(STORAGE_KEY));
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  // Set only when the initial restore couldn't even reach the backend (not
  // when the backend reached and rejected the token). Lets a stored token
  // keep the visitor "authenticated" through a backend outage instead of
  // bouncing them to the public landing page — every data query on the
  // protected pages still independently shows its own "can't reach the
  // backend" state, which is the correct place for that to surface.
  const [backendUnreachable, setBackendUnreachable] = useState(false);

  // Keep the API client's token in sync, and persist it — this is a real
  // improvement over the Streamlit app's session-only auth: a page refresh
  // (or closing and reopening the tab) here still finds a valid session,
  // as long as the token hasn't actually expired/been revoked.
  useEffect(() => {
    setAuthToken(token);
    if (token) localStorage.setItem(STORAGE_KEY, token);
    else localStorage.removeItem(STORAGE_KEY);
  }, [token]);

  // Any 401 anywhere in the app (expired/revoked/disabled account) clears
  // the session — the backend remains the actual authority on this.
  useEffect(() => {
    setAuthErrorHandler(() => {
      setToken(null);
      setUser(null);
    });
    return () => setAuthErrorHandler(null);
  }, []);

  // On first mount only: if a token was persisted from a previous session,
  // verify it's still valid (and fetch the current profile) before treating
  // the visitor as authenticated.
  useEffect(() => {
    let cancelled = false;
    async function restore() {
      if (!token) {
        setIsLoading(false);
        return;
      }
      try {
        const profile = await authApi.me();
        if (!cancelled) {
          setUser(profile);
          setBackendUnreachable(false);
        }
      } catch (err) {
        if (cancelled) return;
        // ApiError with status 0 is apiClient's signal for "the fetch itself
        // failed" (backend down/unreachable) — the token was never actually
        // evaluated, so it isn't necessarily invalid. Anything else (a 401,
        // surfaced as AuthError; or any other definitive response) means the
        // backend looked at this token and rejected it — that's a real logout.
        if (err instanceof ApiError && err.status === 0) {
          setBackendUnreachable(true);
        } else {
          setToken(null);
        }
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    }
    void restore();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function loginWithCredentials(username: string, password: string) {
    const result = await authApi.login(username, password);
    setToken(result.access_token);
    setUser(result.user);
  }

  async function registerAccount(
    username: string,
    email: string,
    password: string,
    fullName: string,
  ) {
    const result = await authApi.register(username, email, password, fullName);
    setToken(result.access_token);
    setUser(result.user);
  }

  async function logout() {
    try {
      await authApi.logout(); // revokes the token server-side (blocklist) — best effort
    } catch {
      // A network failure here must never block clearing the local session.
    }
    setToken(null);
    setUser(null);
  }

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      isAuthenticated: Boolean(token && (user || backendUnreachable)),
      isLoading,
      loginWithCredentials,
      registerAccount,
      logout,
      updateUser: setUser,
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [token, user, isLoading, backendUnreachable],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}
