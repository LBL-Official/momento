import type { StaxRoute } from "./types";

export const STAX_NAV: { id: StaxRoute; label: string; hint: string }[] = [
  { id: "overview", label: "STAX", hint: "Multi-strategy stack" },
  { id: "strategies", label: "Strategies", hint: "Independent research objects" },
  { id: "results", label: "Results", hint: "Per-strategy measurements" },
  { id: "history", label: "History", hint: "Immutable versions" },
  { id: "automation", label: "Automation", hint: "Daily re-execution" },
];
