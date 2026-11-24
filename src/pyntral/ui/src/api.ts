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

export interface ApiOptions extends RequestInit {
  /** Use a same-origin host route instead of the mounted admin API. */
  scope?: "admin" | "host";
}

export async function api<T>(path: string, options: ApiOptions = {}): Promise<T> {
  const { scope = "admin", ...request } = options;
  if (!path.startsWith("/") || path.startsWith("//") || path.includes("\\") || [...path].some(char => char.charCodeAt(0) < 32)) throw new ApiError(0, "invalid_path", "Expected a same-origin absolute path");
  const url = new URL(scope === "host" ? path : base + path, window.location.origin);
  if (url.origin !== window.location.origin || (scope === "admin" && !url.pathname.startsWith(base + "/"))) throw new ApiError(0, "invalid_path", "Path escapes the configured API scope");
  const method = (options.method || "GET").toUpperCase();
  const headers = new Headers(options.headers);
  if (typeof options.body === "string" && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  if (scope === "admin" && !["GET", "HEAD", "OPTIONS"].includes(method) && csrf) headers.set("X-CSRF-Token", csrf);
  let response: Response;
  try {
    response = await fetch(url, { ...request, credentials: "same-origin", headers });
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
