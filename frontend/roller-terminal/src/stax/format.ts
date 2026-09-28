import type { CanonicalUniverse } from "./types";

export function leagueLabel(uni?: CanonicalUniverse | null): string {
  const leagues = uni?.league_set || [];
  if (!leagues.length) return "—";
  return leagues.join(" + ");
}

export function seasonLabel(uni?: CanonicalUniverse | null): string {
  const seasons = uni?.seasons || [];
  if (!seasons.length) return "—";
  return seasons.map((s) => s.replace("2025-2026", "2025–26").replace("2024-2025", "2024–25")).join(" · ");
}

export function timeframeLabel(uni?: CanonicalUniverse | null): string {
  if (!uni?.date_from && !uni?.date_to) return seasonLabel(uni);
  return `${uni?.date_from || "—"} → ${uni?.date_to || "—"}`;
}

export function pct(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  return `${(value * 100).toFixed(2)}%`;
}

export function fmtN(n: number | null | undefined): string {
  if (n == null) return "—";
  return n.toLocaleString("en-US");
}
