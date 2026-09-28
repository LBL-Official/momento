/** Wilson score interval. DERIVED from authoritative successes / denominator. */

export function wilsonCi(
  successes: number,
  n: number,
  z = 1.959963984540054,
): { lower: number; upper: number; p: number } | null {
  if (n <= 0) return null;
  const p = successes / n;
  const z2 = z * z;
  const denom = 1 + z2 / n;
  const center = p + z2 / (2 * n);
  const margin = z * Math.sqrt((p * (1 - p) + z2 / (4 * n)) / n);
  return {
    p,
    lower: (center - margin) / denom,
    upper: (center + margin) / denom,
  };
}

export function formatPct(v: number | null | undefined, digits = 1): string {
  if (v == null || !Number.isFinite(v)) return "—";
  return `${(v * 100).toFixed(digits)}%`;
}
