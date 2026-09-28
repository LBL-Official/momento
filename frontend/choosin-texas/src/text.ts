export function text(value: unknown): string {
  if (value === null || value === undefined || value === "") return "UNAVAILABLE";
  return String(value);
}

export function width(value: number | undefined): string {
  if (value == null || !Number.isFinite(value)) return "0%";
  const clipped = Math.max(0, Math.min(100, value));
  return `${clipped}%`;
}
