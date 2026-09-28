/** Helpers for locked template populations — presentation only; does not invent bindings. */

import { asObj, type Spec } from "../researchTypes";

/** When a frozen definition family is present, leagues must match the template. */
export function lockedTemplateLeagues(spec: Spec): string[] | null {
  const defs = asObj(spec.definition_versions);
  if (typeof defs.NCAAB_FIRST80_P5 === "string") return ["NCAAB"];
  if (typeof defs.FIRST80 === "string") return ["NBA"];
  return null;
}

export function leaguesMatchLock(spec: Spec): boolean {
  const locked = lockedTemplateLeagues(spec);
  if (!locked) return true;
  const leagues = asObj(spec.population_binding).leagues;
  if (!Array.isArray(leagues)) return false;
  if (leagues.length !== locked.length) return false;
  const set = new Set(leagues.map(String));
  return locked.every((l) => set.has(l));
}
