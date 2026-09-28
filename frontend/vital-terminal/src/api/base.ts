/**
 * Vital dashboard talks to the ROLLER terminal API for /vital/* only.
 * The browser does not submit Kalshi orders.
 */

export const DEV_API_ORIGIN = "http://127.0.0.1:8791";

export type ApiEnv = {
  VITE_API_BASE_URL?: string;
  DEV?: boolean;
};

export function resolveApiBaseUrl(env: ApiEnv = {}): string {
  const override = String(env.VITE_API_BASE_URL ?? "").trim().replace(/\/$/, "");
  if (override) return override;
  if (env.DEV === false) return "/api";
  return DEV_API_ORIGIN;
}

export const API_BASE_URL = resolveApiBaseUrl({
  VITE_API_BASE_URL: import.meta.env.VITE_API_BASE_URL,
  DEV: import.meta.env.DEV,
});

export function apiUrl(path: string): string {
  const p = path.startsWith("/") ? path : `/${path}`;
  if (API_BASE_URL === "/api" || API_BASE_URL.endsWith("/api")) {
    return `${API_BASE_URL}${p}`;
  }
  return `${API_BASE_URL}${p}`;
}

export async function apiFetch(path: string, init?: RequestInit): Promise<Response> {
  return fetch(apiUrl(path), init);
}
