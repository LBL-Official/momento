/**
 * Human workflow draft. This is not a research_spec.
 * resolveResearchPlan / server compile maps the draft onto frozen or generic execution.
 */

import type { RecognizedIntent } from "../define/recognizedIntent";

export type WorkflowStatus =
  | "DRAFT"
  | "CONSTRUCTIBLE"
  | "REQUIRES_ATTENTION"
  | "VALIDATING"
  | "READY_TO_RUN"
  | "RUNNING"
  | "COMPLETE";

export type WorkflowUniverse = {
  sports: string[];
  leagues: string[];
  seasons: string[];
  dateFrom?: string;
  dateTo?: string;
  markets: string[];
  marketData: string[];
  dataSources: string[];
};

export type EntryFamily =
  | "first_touch"
  | "second_touch"
  | "third_touch"
  | "fourth_touch"
  | "nth_touch"
  | "cross"
  | "break"
  | "reversion"
  | "bounce"
  | "recovery"
  | "above"
  | "below"
  | "maximum_touch"
  | "minimum_touch"
  | "clock";

export type PeriodWindowSel = {
  period?: string;
  clockFrom?: string;
  clockTo?: string;
};

export type EntryCondition = {
  id: string;
  family: EntryFamily;
  priceCents?: number;
  priceFrom?: number;
  priceTo?: number;
  /** Farthest observed close accepted after the First Touch trigger. Not a fill at the trigger. */
  maxEntryCents?: number;
  touchN?: number | "N";
  touchNValue?: number;
  period?: string;
  clockFrom?: string;
  clockTo?: string;
  /** Two or more windows are OR. A single window stays on period/clock. */
  periodWindows?: PeriodWindowSel[];
  /** Tennis-only: custom game-range window (structural entry, not TE). */
  gameFrom?: number;
  gameTo?: number;
  direction?: "up" | "down";
  magnitudeCents?: number;
};

export type ExitFamily =
  | "reach"
  | "drop_to"
  | "rise_to"
  | "bounce"
  | "recover"
  | "revert"
  | "maximum_move"
  | "minimum_move"
  | "never_reach"
  | "yes"
  | "no"
  | "both"
  | "hold_expiration_win"
  | "hold_expiration_loss"
  | "horizon_game_win"
  | "horizon_game_loss"
  | "horizon_market_win"
  | "horizon_market_loss";

export type ExitOutcome = "win" | "loss";

export type TeScoreSide = "any" | "leading" | "tied" | "trailing";
export type TeAbsDiff = "any" | "1_5" | "6_10" | "11_plus";
export type TeHalf = "any" | "top" | "bottom";
export type TeYesBatting = "any" | "batting" | "pitching";
export type TeRunners =
  | "any"
  | "empty"
  | "1st"
  | "2nd"
  | "3rd"
  | "1st+2nd"
  | "1st+3rd"
  | "2nd+3rd"
  | "loaded"
  | "risp"
  | "any_on";

/** Tennis point score within a game (OR within group). */
export type TeTennisPointScore =
  | "0-0"
  | "15-0"
  | "30-0"
  | "40-0"
  | "15-15"
  | "30-30"
  | "40-40"
  | "DEUCE"
  | "ADVANTAGE";

export type TeTennisServe = "serving" | "returning";

export type TeTennisEventState = "break_point" | "set_point" | "match_point" | "tiebreak";

/** Lead filter on one tennis score layer — never collapsed across set/game/point. */
export type TeTennisLeadFilter = {
  scoreSide?: TeScoreSide;
  exactDiffs?: number[];
  absDiff?: TeAbsDiff;
  customRange?: { min?: number; max?: number };
};

export type TeFilters = {
  scoreSide?: TeScoreSide;
  absDiff?: TeAbsDiff;
  exactDiffs?: number[];
  customRange?: { min?: number; max?: number };
  half?: TeHalf;
  yesBatting?: TeYesBatting;
  outs?: number[];
  count?: string;
  runners?: TeRunners;
  /** Tennis-only: point score state (OR within group). SEQUENCE-ONLY PBP is not PIT-joinable. */
  tennisPointScores?: TeTennisPointScore[];
  /** Tennis-only: YES serving or returning (OR within group). */
  tennisServe?: TeTennisServe[];
  /** Tennis-only: break/set/match point, tiebreak (OR within group). */
  tennisEventStates?: TeTennisEventState[];
  /** Tennis-only: set-score lead dimension. */
  tennisSetLead?: TeTennisLeadFilter;
  /** Tennis-only: game-score lead within current set. */
  tennisGameLead?: TeTennisLeadFilter;
  /** Tennis-only: point-score lead within current game. */
  tennisPointLead?: TeTennisLeadFilter;
};

export type ExitCondition = {
  id: string;
  kind: "path" | "terminal" | "horizon";
  family: ExitFamily;
  priceCents?: number;
  sequential?: boolean;
  horizonKind?: "game" | "market";
  horizonMinutes?: number;
  outcome?: ExitOutcome;
};

export type WorkflowDraft = {
  universe: WorkflowUniverse;
  entryConditions: EntryCondition[];
  exitConditions: ExitCondition[];
  teFilters?: TeFilters;
  recognizedIntent: RecognizedIntent;
  status: WorkflowStatus;
  matchedTemplateId?: string;
  /** Confirm & Run: keep the earliest entry per game. Omitted on frozen goldens. */
  exposureEnforcementMode?: "strategy_enforced" | "results_verify_only";
  exposureUnit?: "GAME" | "TICKER" | "TEAM" | "EVENT";
  maxEntriesPerGame?: number;
  maxEntriesPerUnit?: number;
};

export type ConstructibilityStatus =
  | "READY"
  | "READY_WITH_LIMITATIONS"
  | "DATA_REQUIRED"
  | "OPERATION_REQUIRED";

export type ConstructibilityResolution = {
  status: ConstructibilityStatus;
  matchedTemplate?: "FIRST80_Q3" | "NCAAB_FIRST80_P5";
  referenceMatch?: "FIRST80_Q3" | "NCAAB_FIRST80_P5";
  executionPath?: "frozen_reference" | "generic_query" | "none";
  blockingReasons: string[];
  reasons?: string[];
  recognizedSelections: Array<{ id: string; label: string }>;
  frozenPopulation: boolean;
  canRun?: boolean;
  omittedDimensions?: string[];
  available?: string[];
  unavailable?: string[];
};
