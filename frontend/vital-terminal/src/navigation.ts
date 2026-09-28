export type VitalRoute = "home" | "live" | "bots" | "detail" | "bankroll";

export const VITAL_NAV: { id: VitalRoute; label: string; hint: string }[] = [
  { id: "home", label: "Desk", hint: "Two books + blotter" },
  { id: "live", label: "Live", hint: "momento-live.service" },
  { id: "bots", label: "Bots", hint: "Sport / book / unit" },
  { id: "detail", label: "Unit", hint: "Parameters + ledger" },
  { id: "bankroll", label: "Books", hint: "Shard 3 ≠ top-level" },
];
