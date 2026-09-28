/**
 * Single runtime API base for the ROLLER Research Terminal.
 *
 * The frontend does not own the API process. If :8791 is healthy, use it.
 * Environment VITE_API_BASE_URL wins. Development default is http://127.0.0.1:8791.
 * Production builds without an override use same-origin /api (existing Vite proxy).
 */

export const DEV_API_ORIGIN = "http://127.0.0.1:8791";

export type ApiAvailability = "API_UNREACHABLE" | "API_REACHABLE" | "API_REQUEST_FAILED";

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

export class ApiTransportError extends Error {
  availability: ApiAvailability;
  constructor(availability: ApiAvailability, message: string) {
    super(message);
    this.name = "ApiTransportError";
    this.availability = availability;
  }
}

export function classifyApiFailure(err: unknown): ApiAvailability {
  if (err instanceof ApiTransportError) return err.availability;
  if (err instanceof TypeError) return "API_UNREACHABLE";
  const msg = err instanceof Error ? err.message : String(err);
  if (/failed to fetch|networkerror|load failed|econnrefused/i.test(msg)) {
    return "API_UNREACHABLE";
  }
  return "API_REQUEST_FAILED";
}

export async function apiFetch(path: string, init?: RequestInit): Promise<Response> {
  try {
    return await fetch(apiUrl(path), init);
  } catch (err) {
    throw new ApiTransportError("API_UNREACHABLE", "API_UNREACHABLE");
  }
}

export async function probeApiHealth(timeoutMs = 2500): Promise<ApiAvailability> {
  const ctrl = new AbortController();
  const timer = window.setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await apiFetch("/health", { signal: ctrl.signal });
    if (!res.ok) return "API_REQUEST_FAILED";
    const body = (await res.json()) as { status?: string };
    return body.status === "ok" ? "API_REACHABLE" : "API_REQUEST_FAILED";
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      return "API_UNREACHABLE";
    }
    return classifyApiFailure(err);
  } finally {
    window.clearTimeout(timer);
  }
}
