import type { Principal } from "./types";

export interface AuthState { user: Principal | null; csrf: string | null }
let csrf: string | null = null;
export function setCsrf(value: string | null) { csrf = value; }
const mount = document.querySelector<HTMLBaseElement>("base[data-pyntral-base]");
export const base = (mount ? new URL(mount.href).pathname : import.meta.env.BASE_URL).replace(/\/$/, "");

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string, public details?: unknown) {
    super(message);
  }
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const method = (options.method || "GET").toUpperCase();
  const headers = new Headers(options.headers);
  if (typeof options.body === "string" && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  if (!["GET", "HEAD", "OPTIONS"].includes(method) && csrf) headers.set("X-CSRF-Token", csrf);
  let response: Response;
  try {
    response = await fetch(base + path, { ...options, credentials: "same-origin", headers });
  } catch {
    throw new ApiError(0, "network_error", "Unable to contact the admin server");
  }
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = body?.error;
    throw new ApiError(response.status, error?.code || "http_error", error?.message || `HTTP ${response.status}`, error?.details);
  }
  return body as T;
}

export async function getAuth(): Promise<AuthState> {
  const state = await api<AuthState>("/auth/me");
  setCsrf(state.csrf);
  return state;
}

export function buildQuery(values: Record<string, string | number | boolean | undefined>) {
  const params = new URLSearchParams();
  Object.entries(values).forEach(([key, value]) => {
    if (value !== undefined && value !== "") params.set(key, String(value));
  });
  const search = params.toString();
  return search ? `?${search}` : "";
}
