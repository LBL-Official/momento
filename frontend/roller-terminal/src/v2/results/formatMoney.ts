/** Display-only sign conventions. Do not use for computation. */

const MINUS = "\u2212";

function moneyAbs(v: number, places = 2): string {
  return Math.abs(v).toLocaleString("en-US", {
    minimumFractionDigits: places,
    maximumFractionDigits: places,
  });
}

export function fmtCents(v: number | null | undefined, digits = 2): string {
  if (v == null || !Number.isFinite(v)) return "—";
  if (v > 0) return `+${v.toFixed(digits)}¢`;
  if (v < 0) return `${MINUS}${Math.abs(v).toFixed(digits)}¢`;
  return `${v.toFixed(digits)}¢`;
}

export function fmtDollars(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return "—";
  if (v > 0) return `+$${moneyAbs(v)}`;
  if (v < 0) return `${MINUS}$${moneyAbs(v)}`;
  return `$${moneyAbs(v)}`;
}

export function fmtAbsDollars(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return "—";
  return `$${moneyAbs(v)}`;
}

export function fmtPValue(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return "—";
  if (v === 0) return "0";
  if (v < 0.001) return v.toExponential(2);
  return Number(v.toPrecision(3)).toString();
}

export function fmtSharpe(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return "—";
  return v.toFixed(3);
}
