import type { LsHealth, LsSnapshot } from "./types";

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(path, { headers: { Accept: "application/json" } });
  if (!res.ok) {
    throw new Error(`HTTP ${res.status} ${path}`);
  }
  return (await res.json()) as T;
}

export function fetchHealth(): Promise<LsHealth> {
  return getJson<LsHealth>("/api/health");
}

export function fetchObserve(): Promise<LsSnapshot> {
  return getJson<LsSnapshot>("/api/observe");
}
