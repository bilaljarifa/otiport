import { apiRequest } from "./apiClient";
import type { User } from "./authApi";

export interface SystemStats {
  total_users: number;
  active_users: number;
  disabled_users: number;
  admin_users: number;
  total_accounts: number;
  total_cash: number;
  total_orders: number;
  total_open_orders: number;
  backend_version: string;
}

export function listUsers(): Promise<User[]> {
  return apiRequest<User[]>("/admin/users");
}

export function getStats(): Promise<SystemStats> {
  return apiRequest<SystemStats>("/admin/stats");
}

export interface UpdateUserRoleRequest {
  role?: "user" | "admin";
  is_active?: boolean;
}

export function updateUser(userId: number, req: UpdateUserRoleRequest): Promise<User> {
  return apiRequest<User>(`/admin/users/${userId}`, { method: "PATCH", body: req });
}

export function deleteUser(userId: number): Promise<void> {
  return apiRequest<void>(`/admin/users/${userId}`, { method: "DELETE" });
}
