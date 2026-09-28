export function ageText(iso: string | null | undefined, nowMs = Date.now()): string {
  if (!iso) return "UNREAD";
  const ms = Date.parse(iso);
  if (!Number.isFinite(ms)) return "UNREAD";
  const delta = Math.max(0, nowMs - ms);
  if (delta < 1000) return "now";
  if (delta < 60_000) return `${Math.floor(delta / 1000)}s`;
  if (delta < 3_600_000) return `${Math.floor(delta / 60_000)}m`;
  if (delta < 86_400_000) return `${Math.floor(delta / 3_600_000)}h`;
  return `${Math.floor(delta / 86_400_000)}d`;
}

export function toneForProof(status: string | undefined | null): string {
  const value = String(status || "").toUpperCase();
  if (value === "CONFIRMED" || value === "NOT_TRIPPED" || value === "ACCEPTED") return "is-live";
  if (value === "NOT_CLAIMED") return "is-idle";
  if (value === "FAILED" || value === "REJECTED") return "is-risk";
  return "is-unread";
}

export function toneForLifecycle(lifecycle: string | undefined | null): string {
  const value = String(lifecycle || "").toUpperCase();
  if (value === "RUNNING") return "is-live";
  if (value === "RUNNING_DEMO") return "is-demo";
  if (value === "KILLED" || value === "FAILED" || value === "UNHEALTHY") return "is-risk";
  if (value === "OBSERVATION_UNAVAILABLE" || value === "UNKNOWN" || !value) return "is-unread";
  return "is-idle";
}

export function errorMessage(err: unknown): string {
  if (err && typeof err === "object") {
    const o = err as { code?: string; message?: string; status?: string };
    const code = o.code || o.status;
    if (code && o.message) return `${code}: ${o.message}`;
    if (o.message) return o.message;
  }
  return err instanceof Error ? err.message : String(err);
}
