import { api } from "./client";
import type { LoginResponse } from "../types/domain";

export function login(username: string, password: string): Promise<LoginResponse> {
  return api.postNoAuth<LoginResponse>("/api/auth/login", { username, password });
}
