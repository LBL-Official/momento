export function text(value: unknown): string {
  if (value === null || value === undefined || value === "") return "UNAVAILABLE";
  return String(value);
}

export function cents(value: unknown): string {
  if (value === null || value === undefined || value === "") return "UNAVAILABLE";
  const n = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(n)) return "UNAVAILABLE";
  const rounded = Math.round(n * 100) / 100;
  return `${rounded}¢`;
}

export function num(value: unknown, digits = 3): string {
  if (value === null || value === undefined || value === "") return "UNAVAILABLE";
  const n = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(n)) return "UNAVAILABLE";
  return n.toFixed(digits);
}

export function loadedQty(loaded: boolean, value: unknown): string {
  if (!loaded) return "UNAVAILABLE";
  if (value === 0) return "0";
  if (value === null || value === undefined || value === "") return "UNAVAILABLE";
  return String(value);
}

export function loadedRho(loaded: boolean, value: unknown): string {
  if (!loaded) return "UNAVAILABLE";
  if (value === 0) return "0%";
  if (value === null || value === undefined || value === "") return "UNAVAILABLE";
  const n = Number(value);
  if (!Number.isFinite(n)) return "UNAVAILABLE";
  return `${(n * 100).toFixed(1)}%`;
}
