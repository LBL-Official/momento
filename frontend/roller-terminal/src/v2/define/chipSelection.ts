import { asObj, type Spec } from "../../researchTypes";
import { lockedTemplateKind } from "./defineCatalog";
import { hasClause, type RecognizedIntent } from "./recognizedIntent";

export function isChipSelected(chipId: string, spec: Spec, intent: RecognizedIntent): boolean {
  const lock = lockedTemplateKind(spec);
  const leagues = Array.isArray(asObj(spec.population_binding).leagues)
    ? (asObj(spec.population_binding).leagues as string[])
    : [];

  if (chipId === "nba") return lock === "FIRST80_Q3" || (leagues.includes("NBA") && lock !== "NCAAB_FIRST80_P5");
  if (chipId === "ncaab") return lock === "NCAAB_FIRST80_P5" || leagues.includes("NCAAB");
  if (chipId === "wnba") return hasClause(intent, "wnba");
  if (chipId === "FIRST80_Q3") return lock === "FIRST80_Q3" && !hasClause(intent, "SECOND80");
  if (chipId === "NCAAB_FIRST80_P5") return lock === "NCAAB_FIRST80_P5";
  if (chipId === "FIRST80") return lock === "FIRST80_Q3" && !hasClause(intent, "SECOND80");
  if (chipId === "frozen") return !intent.selectedSeason && lock != null;
  if (chipId === "2023-24" || chipId === "2024-25") return intent.selectedSeason === chipId;
  if (chipId === "lock-event") return lock != null && !hasClause(intent, "SECOND80");
  if (chipId === "Q3") return lock === "FIRST80_Q3" && !hasClause(intent, "Q4") && !hasClause(intent, "Q1") && !hasClause(intent, "OT");
  if (chipId === "P5") return lock === "NCAAB_FIRST80_P5";
  if (chipId === "NONE") {
    return !hasClause(intent, "reversion") && !hasClause(intent, "drop10");
  }
  if (chipId === "T40") {
    return lock != null && !hasClause(intent, "bounce") && !hasClause(intent, "recover") && !hasClause(intent, "rebound15");
  }
  if (chipId === "YES" || chipId === "NO") return lock != null;
  return hasClause(intent, chipId);
}
