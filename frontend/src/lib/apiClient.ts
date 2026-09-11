/**
 * Thin fetch wrapper around the FastAPI backend.
 *
 * Mirrors `services/api_client.py` on the Streamlit side: attaches the
 * bearer token automatically, never invents data on failure, and turns a
 * 401 into a distinct `AuthError` the app reacts to by clearing the session
 * — the backend is still the actual security boundary (every endpoint
 * re-checks the token itself); this only decides what the UI shows.
 */

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  detail: string | null;

  constructor(status: number, message: string, detail: string | null = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

export class AuthError extends Error {
  constructor(message = "Session expired — please log in again.") {
    super(message);
    this.name = "AuthError";
  }
}

let authToken: string | null = null;
let onAuthError: (() => void) | null = null;

/** Called once from AuthContext so the client always has the current token
 * without every call site having to pass it explicitly. */
export function setAuthToken(token: string | null): void {
  authToken = token;
}

/** Called once from AuthContext: what to do when any request comes back
 * unauthenticated (token expired/revoked/disabled) — clears the session. */
export function setAuthErrorHandler(handler: (() => void) | null): void {
  onAuthError = handler;
}

interface RequestOptions {
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  body?: unknown;
  auth?: boolean; // default true — false for register/login/public config endpoints
  signal?: AbortSignal;
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, auth = true, signal } = options;

  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (auth && authToken) headers["Authorization"] = `Bearer ${authToken}`;

  let response: Response;
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal,
    });
  } catch (cause) {
    throw new ApiError(0, `Could not reach the backend at ${BASE_URL}.`, String(cause));
  }

  if (response.status === 401 && auth) {
    onAuthError?.();
    throw new AuthError();
  }

  if (!response.ok) {
    let detail: string | null = null;
    try {
      const body = await response.json();
      detail = body?.detail ?? null;
    } catch {
      detail = null;
    }
    throw new ApiError(response.status, detail ?? `${path} returned HTTP ${response.status}.`, detail);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}
