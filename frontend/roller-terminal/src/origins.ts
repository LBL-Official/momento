/** Cross-product dashboard origins. Vital is a separate Vite instance. */

export const ROLLER_ORIGIN = (
  import.meta.env.VITE_ROLLER_ORIGIN || "http://127.0.0.1:5179"
).replace(/\/$/, "");

export const VITAL_ORIGIN = (
  import.meta.env.VITE_VITAL_ORIGIN || "http://127.0.0.1:5180"
).replace(/\/$/, "");

export function openVitalDashboard(path?: string): void {
  const raw = typeof path === "string" && path.length > 0 ? path : "/#/bots/mlb-001";
  const suffix = raw.startsWith("/") ? raw : `/${raw}`;
  window.location.assign(`${VITAL_ORIGIN}${suffix}`);
}
