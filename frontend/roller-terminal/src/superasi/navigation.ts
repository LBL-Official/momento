import type { SuperasiRoute } from "./types/superasi";

export const SUPERASI_NAV: { id: SuperasiRoute; label: string; hint: string }[] = [
  { id: "sources", label: "Roller CSVs", hint: "Run SuperASI A — Base" },
  { id: "run", label: "SuperASI A — Base", hint: "Composition, grading, validation" },
  { id: "labs_phase_a", label: "Results Labs (phase a)", hint: "A already ran. This runs B." },
  { id: "run_debase", label: "SuperASI B — Debase", hint: "DeComposition, DeGrading, DeValidation" },
  { id: "labs_phase_b", label: "Final Results", hint: "Selected strategy B. Inspect other folders." },
  { id: "iti", label: "Ian Taleb Index", hint: "25-slot research catalog after Final" },
];
