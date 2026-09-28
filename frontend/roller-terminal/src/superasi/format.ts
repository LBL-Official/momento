import type { Frac } from "./types/superasi";

export function fracValue(f?: Frac | null): number | null {
  if (!f || f.numer == null || !f.denom) return null;
  return f.numer / f.denom;
}

export function fmtFrac(f?: Frac | null): string {
  if (!f) return "—";
  if (f.status === "UNAVAILABLE" || f.numer == null || !f.denom) {
    return f.status === "UNAVAILABLE" ? "UNAVAILABLE" : "—";
  }
  return `${f.numer}/${f.denom}`;
}

export function fmtPct(f?: Frac | null, digits = 2): string {
  if (f?.status === "UNAVAILABLE") return "UNAVAILABLE";
  const v = fracValue(f);
  if (v == null) return "—";
  return `${(v * 100).toFixed(digits)}%`;
}

export function fmtCents(f?: Frac | null, digits = 2): string {
  const v = fracValue(f);
  if (v == null) return "—";
  return `${v.toFixed(digits)}¢`;
}

export function shortHash(value?: string | null, head = 12): string {
  if (!value) return "—";
  return value.length > head + 1 ? `${value.slice(0, head)}…` : value;
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
