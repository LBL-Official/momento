/** Browser session for the current study + last run. UI convenience only. */

import {
  snapshotMatchesDraft,
  type ResultSnapshot,
  type ValidationSnapshot,
} from "../researchFreshness";
import type { Spec } from "../researchTypes";
import { blankSpec } from "../researchTypes";
import { emptyIntent, type RecognizedIntent } from "./define/recognizedIntent";
import { emptyDraft, draftMatchingFirst80Q3, draftMatchingNcaabP5, stripIncompleteHorizons } from "./workflow/draft";
import { compactResultSnapshot } from "./results/savedSnapshot";
import type { WorkflowDraft } from "./workflow/types";

export const SESSION_STORAGE_KEY = "roller.v2.research_session.v1";

export type ResearchSession = {
  version: 1;
  spec: Spec;
  validationSnapshot: ValidationSnapshot | null;
  resultSnapshot: ResultSnapshot | null;
  activeLibraryId: string | null;
  activeTemplateId: string | null;
  recognizedIntent?: RecognizedIntent;
  workflowDraft?: WorkflowDraft;
};

export function emptySession(): ResearchSession {
  return {
    version: 1,
    spec: blankSpec(),
    validationSnapshot: null,
    resultSnapshot: null,
    activeLibraryId: null,
    activeTemplateId: null,
    recognizedIntent: emptyIntent(),
    workflowDraft: emptyDraft(),
  };
}

function seedDraft(parsed: ResearchSession): WorkflowDraft {
  if (parsed.workflowDraft) return parsed.workflowDraft;
  if (parsed.activeTemplateId === "FIRST80_Q3") return draftMatchingFirst80Q3();
  if (parsed.activeTemplateId === "NCAAB_FIRST80_P5") return draftMatchingNcaabP5();
  return emptyDraft();
}

export function loadSession(): ResearchSession {
  try {
    const raw = localStorage.getItem(SESSION_STORAGE_KEY);
    if (!raw) return emptySession();
    const parsed = JSON.parse(raw) as ResearchSession;
    if (!parsed || parsed.version !== 1 || !parsed.spec || typeof parsed.spec !== "object") {
      return emptySession();
    }
    const workflowDraft = stripIncompleteHorizons(seedDraft(parsed));
    const resultSnapshot = parsed.resultSnapshot ?? null;
    return {
      version: 1,
      spec: parsed.spec,
      validationSnapshot: parsed.validationSnapshot ?? null,
      resultSnapshot: snapshotMatchesDraft(resultSnapshot, workflowDraft) ? resultSnapshot : null,
      activeLibraryId: parsed.activeLibraryId ?? null,
      activeTemplateId: parsed.activeTemplateId ?? null,
      recognizedIntent: parsed.recognizedIntent ?? emptyIntent(),
      workflowDraft,
    };
  } catch {
    return emptySession();
  }
}

export function saveSession(session: ResearchSession): void {
  try {
    localStorage.setItem(
      SESSION_STORAGE_KEY,
      JSON.stringify({
        ...session,
        version: 1,
        resultSnapshot: session.resultSnapshot
          ? compactResultSnapshot(session.resultSnapshot)
          : null,
      } satisfies ResearchSession),
    );
  } catch {
    // Quota or private-mode — keep in-memory state only.
  }
}
