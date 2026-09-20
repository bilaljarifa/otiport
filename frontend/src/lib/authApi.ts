import { apiRequest } from "./apiClient";

export interface User {
  id: number;
  username: string;
  email: string;
  full_name: string;
  job_title: string;
  desk: string;
  role: "user" | "admin";
  is_active: boolean;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: "bearer";
  user: User;
}

export function login(username: string, password: string): Promise<TokenResponse> {
  return apiRequest<TokenResponse>("/auth/login", {
    method: "POST",
    body: { username, password },
    auth: false,
  });
}

export function register(
  username: string,
  email: string,
  password: string,
  full_name: string,
): Promise<TokenResponse> {
  return apiRequest<TokenResponse>("/auth/register", {
    method: "POST",
    body: { username, email, password, full_name },
    auth: false,
  });
}

export function logout(): Promise<void> {
  return apiRequest<void>("/auth/logout", { method: "POST" });
}

export interface GoogleConfig {
  enabled: boolean;
  client_id: string | null;
  redirect_uri: string | null;
}

/** Public, unauthenticated — the Login page calls this to decide whether to
 * show "Continue with Google" at all, and to build the Google authorize URL
 * from the same client_id/redirect_uri the backend will use to verify the
 * code it gets back (so the two can never drift apart). */
export function googleConfig(): Promise<GoogleConfig> {
  return apiRequest<GoogleConfig>("/auth/google/config", { auth: false });
}

export function googleLogin(code: string, redirectUri: string): Promise<TokenResponse> {
  return apiRequest<TokenResponse>("/auth/google", {
    method: "POST",
    body: { code, redirect_uri: redirectUri },
    auth: false,
  });
}

export function me(): Promise<User> {
  return apiRequest<User>("/auth/me");
}

export interface UpdateProfileRequest {
  full_name?: string;
  job_title?: string;
  desk?: string;
}

export function updateProfile(req: UpdateProfileRequest): Promise<User> {
  return apiRequest<User>("/auth/me", { method: "PATCH", body: req });
}
