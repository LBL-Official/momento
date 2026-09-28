export function text(value: unknown): string {
  if (value === null || value === undefined || value === "") return "UNAVAILABLE";
  return String(value);
}

export function cents(value: unknown): string {
  if (value === null || value === undefined || value === "") return "UNAVAILABLE";
  const n = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(n)) return "UNAVAILABLE";
  return `${n}¢`;
}

export function signedCents(value: unknown): string {
  if (value === null || value === undefined || value === "") return "UNAVAILABLE";
  const n = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(n)) return "UNAVAILABLE";
  const rounded = Math.round(n * 100) / 100;
  const sign = rounded > 0 ? "+" : "";
  return `${sign}${rounded}¢`;
}

export function width(value: number | undefined): string {
  if (value == null || !Number.isFinite(value)) return "0%";
  const clipped = Math.max(0, Math.min(100, value));
  return `${clipped}%`;
}
