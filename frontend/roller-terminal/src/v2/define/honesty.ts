/**
 * Chip honesty: overlays and season filters cannot become runnable
 * and must not rewrite a question to FIRST80.
 */

import { asObj, type Spec } from "../../researchTypes";
import { lockedTemplateKind } from "./defineCatalog";
import { intentBlocksRun, type RecognizedIntent } from "./recognizedIntent";

/** Season on a locked template is STRUCTURAL — never write it onto the spec. */
export function specWithoutInventedSeasons(spec: Spec): Spec {
  const lock = lockedTemplateKind(spec);
  if (!lock) return spec;
  const pop = asObj(spec.population_binding);
  if (!("seasons" in pop) && !("months" in pop) && !("weeks" in pop)) return spec;
  const next = structuredClone(spec);
  const binding = asObj(next.population_binding);
  delete binding.seasons;
  delete binding.months;
  delete binding.weeks;
  next.population_binding = binding;
  return next;
}

export function overlayBlocksReadyToRun(intent: RecognizedIntent): boolean {
  return intentBlocksRun(intent);
}

export function readyToRun(canRunFromValidation: boolean, intent: RecognizedIntent): boolean {
  return canRunFromValidation && !overlayBlocksReadyToRun(intent);
}

/** Selecting a recognized chip must not invent path_conditions. */
export function specUnchangedByOverlay(before: Spec, after: Spec): boolean {
  return JSON.stringify(before.path_conditions) === JSON.stringify(after.path_conditions);
}
