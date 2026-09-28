import { emptyIntent } from "../define/recognizedIntent";
import type { EntryCondition, ExitCondition, TeFilters, WorkflowDraft, WorkflowUniverse } from "./types";

export function emptyUniverse(): WorkflowUniverse {
  return {
    sports: [],
    leagues: [],
    seasons: [],
    markets: [],
    marketData: [],
    dataSources: [],
  };
}

export function emptyDraft(): WorkflowDraft {
  return {
    universe: emptyUniverse(),
    entryConditions: [],
    exitConditions: [],
    teFilters: { scoreSide: "any", absDiff: "any" },
    recognizedIntent: emptyIntent(),
    status: "DRAFT",
    exposureEnforcementMode: "strategy_enforced",
    exposureUnit: "GAME",
    maxEntriesPerGame: 1,
  };
}

/** Confirm & Run / warehouse keep one earliest trade per game. Frozen goldens omit this. */
export function applyOneTradePerGame(draft: WorkflowDraft): WorkflowDraft {
  if (
    draft.exposureEnforcementMode === "strategy_enforced" &&
    draft.exposureUnit === "GAME" &&
    draft.maxEntriesPerGame === 1
  ) {
    return draft;
  }
  return {
    ...draft,
    exposureEnforcementMode: "strategy_enforced",
    exposureUnit: "GAME",
    maxEntriesPerGame: 1,
  };
}

export function isOneTradePerGame(draft: WorkflowDraft): boolean {
  return (
    draft.exposureEnforcementMode === "strategy_enforced" &&
    draft.exposureUnit === "GAME" &&
    draft.maxEntriesPerGame === 1
  );
}

export function setOneTradePerGame(draft: WorkflowDraft, on: boolean): WorkflowDraft {
  if (on) return { ...applyOneTradePerGame(draft), status: "DRAFT" };
  if (draft.exposureEnforcementMode === "results_verify_only") return draft;
  return {
    ...draft,
    exposureEnforcementMode: "results_verify_only",
    exposureUnit: draft.exposureUnit ?? "GAME",
    maxEntriesPerGame: draft.maxEntriesPerGame ?? 1,
    status: "DRAFT",
  };
}

export function isCompleteHorizon(e: ExitCondition): boolean {
  return e.kind !== "horizon" || (e.horizonMinutes != null && e.horizonMinutes >= 1);
}

export function isCompletePath(e: ExitCondition): boolean {
  return e.kind !== "path" || e.priceCents != null;
}

export function sanitizeExitConditions(exits: ExitCondition[]): ExitCondition[] {
  const complete = exits.filter((e) => isCompleteHorizon(e) && isCompletePath(e));
  const tagged = complete.some((e) => e.outcome === "win" || e.outcome === "loss");
  const kept = tagged
    ? complete.filter((e) => e.outcome === "win" || e.outcome === "loss")
    : complete;
  if (kept.length === exits.length && kept.every((e, i) => e === exits[i])) return exits;
  return kept;
}

/** Drop incomplete clocks and ghost untagged exits once a WIN/LOSS book exists. */
export function stripIncompleteHorizons(draft: WorkflowDraft): WorkflowDraft {
  const next = sanitizeExitConditions(draft.exitConditions);
  if (next === draft.exitConditions) return draft;
  return { ...draft, exitConditions: next, status: "DRAFT" };
}

export function newConditionId(prefix: string): string {
  return `${prefix}_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 7)}`;
}

export function toggleIn(list: string[], id: string): string[] {
  return list.includes(id) ? list.filter((x) => x !== id) : [...list, id];
}

export function updateUniverse(
  draft: WorkflowDraft,
  patch: Partial<WorkflowUniverse>,
): WorkflowDraft {
  return { ...draft, universe: { ...draft.universe, ...patch }, status: "DRAFT" };
}

export function setEntryConditions(
  draft: WorkflowDraft,
  entryConditions: EntryCondition[],
): WorkflowDraft {
  return { ...draft, entryConditions, status: "DRAFT" };
}

export function setExitConditions(
  draft: WorkflowDraft,
  exitConditions: ExitCondition[],
): WorkflowDraft {
  return { ...draft, exitConditions: sanitizeExitConditions(exitConditions), status: "DRAFT" };
}

export function setTeFilters(draft: WorkflowDraft, teFilters: TeFilters): WorkflowDraft {
  return { ...draft, teFilters, status: "DRAFT" };
}

export function duplicateEntry(cond: EntryCondition): EntryCondition {
  return { ...cond, id: newConditionId("entry") };
}

export function duplicateExit(cond: ExitCondition): ExitCondition {
  return { ...cond, id: newConditionId("exit") };
}

/** Seed a draft that matches the NBA FIRST80 Q3 lock — never invents a spec. */
export function draftMatchingFirst80Q3(): WorkflowDraft {
  return {
    universe: {
      sports: ["basketball"],
      leagues: ["NBA"],
      seasons: ["2025-26"],
      markets: ["kalshi"],
      marketData: ["candles"],
      dataSources: ["espn", "nba_api"],
    },
    entryConditions: [
      {
        id: newConditionId("entry"),
        family: "first_touch",
        priceCents: 80,
        period: "Q3",
      },
    ],
    exitConditions: [
      { id: newConditionId("exit"), kind: "path", family: "reach", priceCents: 40 },
      { id: newConditionId("exit"), kind: "terminal", family: "both" },
    ],
    recognizedIntent: emptyIntent(),
    status: "DRAFT",
    matchedTemplateId: "FIRST80_Q3",
  };
}

export function draftMatchingNcaabP5(): WorkflowDraft {
  return {
    universe: {
      sports: ["basketball"],
      leagues: ["NCAAB"],
      seasons: ["2025-26"],
      markets: ["kalshi"],
      marketData: ["candles"],
      dataSources: [],
    },
    entryConditions: [
      {
        id: newConditionId("entry"),
        family: "first_touch",
        priceCents: 80,
        period: "P5",
      },
    ],
    exitConditions: [
      { id: newConditionId("exit"), kind: "path", family: "reach", priceCents: 40 },
      { id: newConditionId("exit"), kind: "terminal", family: "both" },
    ],
    recognizedIntent: emptyIntent(),
    status: "DRAFT",
    matchedTemplateId: "NCAAB_FIRST80_P5",
  };
}
