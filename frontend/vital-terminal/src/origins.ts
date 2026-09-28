/** Cross-product dashboard origins. Vital is a separate Vite instance. */

export const ROLLER_ORIGIN = (
  import.meta.env.VITE_ROLLER_ORIGIN || "http://127.0.0.1:5179"
).replace(/\/$/, "");

export const VITAL_ORIGIN = (
  import.meta.env.VITE_VITAL_ORIGIN || "http://127.0.0.1:5180"
).replace(/\/$/, "");

export function openRoller(): void {
  window.location.assign(`${ROLLER_ORIGIN}/`);
}

export function openJump(): void {
  window.location.assign(`${ROLLER_ORIGIN}/?app=jump`);
}

export function openSuperASI(): void {
  window.location.assign(`${ROLLER_ORIGIN}/?app=superasi`);
}
