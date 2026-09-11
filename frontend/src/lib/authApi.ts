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
