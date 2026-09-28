/**
 * Client preview of research status. Server compile/execute is authoritative.
 * Never rewrites SECOND TOUCH → FIRST TOUCH.
 */

import type { IntentClause, RecognizedIntent } from "../define/recognizedIntent";
import { emptyIntent } from "../define/recognizedIntent";
import { dateRangeForSelections } from "./seasonDates";
import { isBaseballFamily, isTennisFamily, mixedClockFamilies } from "./sportFamily";
import type { WorkflowDraft } from "./types";

export type ResearchStatus =
  | "READY"
  | "READY_WITH_LIMITATIONS"
  | "DATA_REQUIRED"
  | "OPERATION_REQUIRED";

export type ExecutionPath = "frozen_reference" | "generic_query" | "none";

const IMPLEMENTED_ENTRY = new Set([
  "first_touch",
  "second_touch",
  "third_touch",
  "fourth_touch",
  "nth_touch",
  "cross",
  "break",
  "reversion",
  "bounce",
  "recovery",
  "above",
  "below",
  "maximum_touch",
  "minimum_touch",
]);
const UNSUPPORTED_ENTRY = new Set<string>();
const UNSUPPORTED_PATH = new Set<string>();
const SUPPORTED_PATH = new Set([
  "reach",
  "drop_to",
  "rise_to",
  "recover",
  "bounce",
  "revert",
  "maximum_move",
  "minimum_move",
  "never_reach",
]);
const NO_DATA_SPORTS = new Set<string>();
const OPTIONAL_MISSING = new Set(["tick", "l2", "kenpom", "ncaa", "wnba_pbp"]);

export type ResearchPlan = {
  status: ResearchStatus;
  executionPath: ExecutionPath;
  referenceMatch?: "FIRST80_Q3" | "NCAAB_FIRST80_P5";
  reasons: string[];
  available: string[];
  unavailable: string[];
  omittedDimensions: string[];
  canRun: boolean;
  /** compat with older call sites */
  matchedTemplate?: "FIRST80_Q3" | "NCAAB_FIRST80_P5";
  blockingReasons: string[];
  recognizedSelections: Array<{ id: string; label: string }>;
  frozenPopulation: boolean;
};

export function resolveResearchPlan(
  draft: WorkflowDraft,
  opts?: { acceptLimitations?: boolean },
): ResearchPlan {
  const u = draft.universe;
  const reasons: string[] = [];
  const unavailable: string[] = [];
  const omitted: string[] = [];
  const rec: Array<{ id: string; label: string }> = [];

  for (const s of u.sports) {
    if (NO_DATA_SPORTS.has(s)) {
      reasons.push(`No authoritative ROLLER dataset currently exists for ${s}.`);
      unavailable.push(s);
    }
  }
  if (mixedClockFamilies(u)) {
    reasons.push("Mixed sport families do not share a clock. Select one sport family.");
    unavailable.push("mixed_sport_clock");
  }
  if (isTennisFamily(u)) {
    for (const x of draft.exitConditions) {
      if (x.kind === "horizon" && x.horizonKind === "game") {
        reasons.push(
          "Tennis has no basketball game clock. Game-clock horizons are OPERATION_REQUIRED. Use Reach or Hold to settlement.",
        );
        unavailable.push("horizon_game");
      }
    }
  }
  if (u.markets.includes("polymarket")) {
    reasons.push(
      "Polymarket 1-minute warehouse series is last-trade price history, not tradable top-of-book bid/ask. Kalshi cannot be substituted automatically.",
    );
    unavailable.push("polymarket");
  }
  for (const e of draft.entryConditions) {
    if (UNSUPPORTED_ENTRY.has(e.family)) {
      reasons.push(
        `${e.family} has no approved candle-close definition. The system will not invent one.`,
      );
      unavailable.push(e.family);
      rec.push({ id: e.family, label: e.family });
    }
    if (e.family === "recovery" && draft.entryConditions[0]?.id === e.id && e.direction !== "up" && e.direction !== "down") {
      reasons.push("Standalone Recovery requires an explicit direction.");
      unavailable.push("recovery");
    }
  }
  const entryRef = draft.entryConditions[0]?.priceCents ?? draft.entryConditions[0]?.priceFrom;
  for (const x of draft.exitConditions) {
    if (x.kind !== "path" || x.priceCents == null || entryRef == null || !x.outcome) continue;
    if (x.outcome === "win" && x.priceCents < entryRef) {
      reasons.push(`WIN exit ${x.family} ${x.priceCents}¢ is under the entry reference ${entryRef}¢.`);
      unavailable.push(x.family);
    }
    if (x.outcome === "loss" && x.priceCents > entryRef) {
      reasons.push(`LOSS exit ${x.family} ${x.priceCents}¢ is over the entry reference ${entryRef}¢.`);
      unavailable.push(x.family);
    }
  }
  for (const x of draft.exitConditions) {
    if (x.kind === "path" && UNSUPPORTED_PATH.has(x.family)) {
      reasons.push(`${x.family} has no approved candle-close definition.`);
      unavailable.push(x.family);
    }
    if (x.kind === "horizon") {
      if (x.horizonMinutes == null || x.horizonMinutes < 1) {
        reasons.push(
          `${x.family || "horizon"} is incomplete — pick +N minutes. Until then the clock is not in the question. Game/Market clock is never silently dropped into Reach-only.`,
        );
        unavailable.push(x.family || "horizon");
      }
    }
  }

  for (const d of u.marketData) {
    if (OPTIONAL_MISSING.has(d)) omitted.push(d);
  }
  for (const d of u.dataSources) {
    if (OPTIONAL_MISSING.has(d)) omitted.push(d);
  }

  const accept = Boolean(opts?.acceptLimitations);
  const baseballCandles =
    isBaseballFamily(u) &&
    u.marketData.includes("candles") &&
    !u.marketData.includes("last_trade");
  if (baseballCandles) {
    reasons.push(
      "MLB Kalshi candles cannot pass frozen quality() without positive volume. Volume is not invented from print count. LAST TRADE remains the runnable path. This is not an empty FIRST_TOUCH population.",
    );
    unavailable.push("UNTRADABLE_CANDLES");
  }
  if (unavailable.some((x) => NO_DATA_SPORTS.has(x))) {
    return pack("DATA_REQUIRED", "none", reasons, [], unavailable, omitted, rec, undefined, accept);
  }
  if (unavailable.includes("UNTRADABLE_CANDLES")) {
    return pack("DATA_REQUIRED", "none", reasons, [], unavailable, omitted, rec, undefined, accept);
  }
  if (unavailable.includes("polymarket")) {
    return pack("OPERATION_REQUIRED", "none", reasons, [], unavailable, omitted, rec, undefined, accept);
  }
  if (unavailable.length) {
    return pack("OPERATION_REQUIRED", "none", reasons, [], unavailable, omitted, rec, undefined, accept);
  }

  const ref = exactLock(draft);
  if (omitted.length && !accept) {
    return pack(
      "READY_WITH_LIMITATIONS",
      ref ? "frozen_reference" : "generic_query",
      [
        "Optional requested dimensions are unavailable. Acknowledge omitted dimensions to run the reduced question.",
      ],
      ["kalshi_1m_candles"],
      [],
      omitted,
      rec,
      ref,
      accept,
    );
  }

  const hasEntry = draft.entryConditions.some((e) => IMPLEMENTED_ENTRY.has(e.family));
  const pathOk = draft.exitConditions
    .filter((e) => e.kind === "path")
    .every((e) => SUPPORTED_PATH.has(e.family));
  if (!hasEntry) {
    reasons.push("Define a supported entry operation.");
    return pack("OPERATION_REQUIRED", "none", reasons, [], ["entry"], omitted, rec, undefined, accept);
  }
  if (!pathOk && draft.exitConditions.some((e) => e.kind === "path")) {
    return pack("OPERATION_REQUIRED", "none", reasons, [], unavailable, omitted, rec, undefined, accept);
  }

  if (ref) {
    return pack(
      "READY",
      "frozen_reference",
      [],
      ["warehouse_frozen_v1", ref],
      [],
      omitted,
      [],
      ref,
      accept,
    );
  }
  const lastTrade =
    u.marketData.includes("last_trade") && !u.marketData.includes("candles");
  return pack(
    "READY",
    "generic_query",
    [],
    lastTrade
      ? ["kalshi_1m_last_trade", "last_trade_close_cross", "pbp_snap"]
      : ["kalshi_1m_candles", "tradable_yes_bid_close_cross", "pbp_snap"],
    [],
    omitted,
    [],
    undefined,
    accept,
  );
}

function datesAreCustomSubset(draft: WorkflowDraft): boolean {
  const u = draft.universe;
  if (!u.dateFrom && !u.dateTo) return false;
  const filled = dateRangeForSelections(u.leagues, u.seasons);
  return !(filled.dateFrom && u.dateFrom === filled.dateFrom && u.dateTo === filled.dateTo);
}

function exactLock(draft: WorkflowDraft): "FIRST80_Q3" | "NCAAB_FIRST80_P5" | undefined {
  const u = draft.universe;
  if (datesAreCustomSubset(draft)) return undefined;
  if (u.markets.length !== 1 || u.markets[0] !== "kalshi") return undefined;
  if (!u.marketData.includes("candles")) return undefined;
  if (u.marketData.some((d) => d !== "candles")) return undefined;
  if (u.seasons.length && u.seasons.some((s) => s !== "2025-26")) return undefined;
  if (draft.entryConditions.length !== 1) return undefined;
  const e = draft.entryConditions[0];
  if (e.family !== "first_touch" || e.priceCents !== 80) return undefined;
  if (e.priceFrom != null || e.priceTo != null) return undefined;
  if (e.maxEntryCents != null) return undefined;
  if (e.clockFrom || e.clockTo) return undefined;
  if (e.periodWindows?.length) return undefined;
  if (draft.exitConditions.some((x) => x.kind === "horizon")) return undefined;
  if (draft.exitConditions.some((x) => x.outcome)) return undefined;
  const paths = draft.exitConditions.filter((x) => x.kind === "path");
  if (paths.length !== 1) return undefined;
  const p = paths[0];
  if (p.family !== "reach" || p.priceCents !== 40 || p.sequential) return undefined;
  if (u.leagues.length === 1 && u.leagues[0] === "NBA" && e.period === "Q3") return "FIRST80_Q3";
  if (u.leagues.length === 1 && u.leagues[0] === "NCAAB" && e.period === "P5") return "NCAAB_FIRST80_P5";
  return undefined;
}

function pack(
  status: ResearchStatus,
  executionPath: ExecutionPath,
  reasons: string[],
  available: string[],
  unavailable: string[],
  omitted: string[],
  rec: Array<{ id: string; label: string }>,
  ref: "FIRST80_Q3" | "NCAAB_FIRST80_P5" | undefined,
  accept: boolean,
): ResearchPlan {
  const canRun = status === "READY" || (status === "READY_WITH_LIMITATIONS" && accept);
  return {
    status,
    executionPath,
    referenceMatch: ref,
    reasons,
    available,
    unavailable,
    omittedDimensions: omitted,
    canRun,
    matchedTemplate: ref,
    blockingReasons: reasons,
    recognizedSelections: rec,
    frozenPopulation: executionPath === "frozen_reference",
  };
}

export function intentFromPlan(plan: ResearchPlan): RecognizedIntent {
  if (plan.status === "READY" || plan.status === "READY_WITH_LIMITATIONS") return emptyIntent();
  const clauses: IntentClause[] = plan.recognizedSelections.map((s) => ({
    id: s.id,
    family: "search",
    label: s.label,
    constructible: false as const,
  }));
  return { clauses, customizeUnlocked: false, selectedSeason: null };
}

export function applyPlanToDraft(draft: WorkflowDraft, plan: ResearchPlan): WorkflowDraft {
  return {
    ...draft,
    recognizedIntent: intentFromPlan(plan),
    status: plan.canRun ? "CONSTRUCTIBLE" : "DRAFT",
    matchedTemplateId: plan.referenceMatch,
  };
}
