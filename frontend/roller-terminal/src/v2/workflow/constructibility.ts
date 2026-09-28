/**
 * Compatibility wrapper. Authoritative preview is resolveResearchPlan.
 * Server compile/execute remains the authority. Never rewrite SECOND TOUCH → FIRST TOUCH.
 */

import {
  applyPlanToDraft,
  intentFromPlan,
  resolveResearchPlan,
  type ResearchPlan,
} from "./resolveResearchPlan";
import type { WorkflowDraft } from "./types";

export type { ResearchPlan };

/** @deprecated Use resolveResearchPlan. Kept for library/report call sites. */
export function resolveConstructibility(draft: WorkflowDraft): ResearchPlan {
  return resolveResearchPlan(draft);
}

export const intentFromResolution = intentFromPlan;
export const applyResolutionToDraft = applyPlanToDraft;
