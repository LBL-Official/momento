import type { SuperasiBaseResult, SuperasiDebaseResult } from "./types/superasi";

export function matchPhaseAResult(
  results: SuperasiBaseResult[],
  labId: string | null | undefined,
): SuperasiBaseResult | null {
  if (!labId) return null;
  const hits = results.filter((row) => row.source_lab_id === labId);
  if (!hits.length) return null;
  return [...hits].sort((a, b) => String(b.created_at || "").localeCompare(String(a.created_at || "")))[0];
}

export function matchPhaseBResult(
  results: SuperasiDebaseResult[],
  labId: string | null | undefined,
): SuperasiDebaseResult | null {
  if (!labId) return null;
  const hits = results.filter((row) => row.source_lab_id === labId);
  if (!hits.length) return null;
  return [...hits].sort((a, b) => String(b.created_at || "").localeCompare(String(a.created_at || "")))[0];
}
