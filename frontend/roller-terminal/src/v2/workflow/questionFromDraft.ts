/**
 * Natural-language research question from WorkflowDraft.
 * Preserves exact human selections. Never rewrites SECOND TOUCH to FIRST TOUCH.
 */

import { catalogItem } from "../catalog/availabilityCatalog";
import { isBaseballFamily } from "./sportFamily";
import {
  NBA_4MIN,
  NBA_PERIODS,
  NCAAB_10MIN,
  NCAAB_5MIN,
  NCAAB_PERIODS,
  TENNIS_GAMES,
  TENNIS_SETS,
  chipMatches,
  windowsFromEntry,
} from "./periodPartitions";
import type { ConstructibilityResolution, TeTennisLeadFilter } from "./types";
import type { EntryCondition, ExitCondition, WorkflowDraft } from "./types";

const PERIOD_CHIPS = [
  ...NBA_PERIODS,
  ...NBA_4MIN,
  ...NCAAB_PERIODS,
  ...NCAAB_10MIN,
  ...NCAAB_5MIN,
  ...TENNIS_SETS,
  ...TENNIS_GAMES,
];

function periodPhrase(e: EntryCondition): string | undefined {
  const labels = windowsFromEntry(e).map((w) => {
    const hit = PERIOD_CHIPS.find((c) => chipMatches(c, w.period, w.clockFrom, w.clockTo));
    if (hit) return hit.label;
    return w.period;
  }).filter((x): x is string => Boolean(x));
  if (!labels.length) return undefined;
  return labels.join(" or ");
}

function sportLabel(id: string): string {
  return catalogItem(id, "sport")?.label ?? id;
}

function leagueLabel(id: string): string {
  return catalogItem(id, "league")?.label ?? id;
}

function seasonLabel(id: string): string {
  return catalogItem(id, "season")?.label ?? id;
}

function marketLabel(id: string): string {
  return catalogItem(id, "market")?.label ?? id;
}

function entryPhrase(e: EntryCondition): string {
  const fam = catalogItem(e.family, "entry")?.label ?? e.family.replace(/_/g, " ");
  const bits = [fam];
  if (e.priceCents != null) bits.push(`${e.priceCents}¢`);
  if (e.priceFrom != null || e.priceTo != null) {
    bits.push(`${e.priceFrom ?? "?"}¢–${e.priceTo ?? "?"}¢`);
  }
  if (e.maxEntryCents != null) bits.push(`accept through ${e.maxEntryCents}¢`);
  const period = periodPhrase(e);
  if (period) bits.push(period);
  if (e.gameFrom != null || e.gameTo != null) {
    bits.push(`games ${e.gameFrom ?? "…"}–${e.gameTo ?? "…"}`);
  }
  if ((e.clockFrom || e.clockTo) && !PERIOD_CHIPS.some((c) => chipMatches(c, e.period, e.clockFrom, e.clockTo))) {
    bits.push(`between ${e.clockFrom || "…"} and ${e.clockTo || "…"}`);
  }
  if (e.direction) bits.push(e.direction);
  if (e.magnitudeCents != null) bits.push(`${e.magnitudeCents}¢`);
  if (e.touchN === "N" && e.touchNValue != null) bits.push(`N=${e.touchNValue}`);
  else if (e.touchN != null && e.touchN !== 1) bits.push(`touch ${e.touchN}`);
  return bits.join(" ");
}

function pathVerb(family: string): string {
  if (family === "drop_to") return "dropping to";
  if (family === "rise_to") return "rising to";
  if (family === "recover") return "recovering to";
  if (family === "reach") return "reaching";
  return (catalogItem(family, "exit_path")?.label ?? family.replace(/_/g, " ")).toLowerCase();
}

function pathPhrase(e: ExitCondition): string {
  const core = e.priceCents != null ? `${pathVerb(e.family)} ${e.priceCents}¢` : pathVerb(e.family);
  return e.outcome ? `${e.outcome.toUpperCase()} by ${core}` : core;
}

function horizonPhrase(e: ExitCondition): string {
  const fam = catalogItem(e.family, "exit_horizon")?.label ?? e.family.replace(/_/g, " ");
  return e.horizonMinutes != null ? `${fam} +${e.horizonMinutes}m` : fam;
}

function terminalPhrase(e: ExitCondition): string {
  if (e.family === "yes" || e.family === "hold_expiration_win") return "hold to expiration for WIN (settle YES)";
  if (e.family === "no" || e.family === "hold_expiration_loss") return "hold to expiration for LOSS (settle NO)";
  return "partition by terminal outcome YES and NO";
}

export function composeQuestionFromDraft(
  draft: WorkflowDraft,
  resolution?: ConstructibilityResolution,
): string {
  const u = draft.universe;
  const sports = u.sports.map(sportLabel);
  const leagues = u.leagues.map(leagueLabel);
  const universeBits = [...new Set([...leagues, ...sports.filter((s) => s !== "Basketball")])];
  const universe =
    universeBits.length > 0
      ? universeBits.join(" and ")
      : sports.length
        ? sports.join(" and ")
        : "the selected universe";

  const markets = u.markets.map(marketLabel);
  const marketBit = markets.length ? `${markets.join(" and ")} market ` : "";

  const frozen = Boolean(resolution?.frozenPopulation || resolution?.matchedTemplate);
  const seasonBit =
    u.seasons.length === 0
      ? frozen
        ? "the selected frozen"
        : "the selected"
      : `${u.seasons.map(seasonLabel).join(" and ")}`;

  const entries = draft.entryConditions;
  const entryBit = entries.length
    ? entries.map(entryPhrase).join(", and ")
    : "the selected entry event";

  const visible = visibleExitConditions(draft);
  const paths = visible.filter((e) => e.kind === "path");
  const horizons = visible.filter((e) => e.kind === "horizon");
  const terms = visible.filter((e) => e.kind === "terminal");
  const observe = [
    ...paths.map(pathPhrase),
    ...horizons.map(horizonPhrase),
  ];
  const hasTagged = paths.some((p) => p.outcome) || horizons.some((h) => h.outcome);
  const pathBit = observe.length
    ? observe.join(paths.some((p) => p.sequential) ? ", then " : hasTagged ? " or " : " and ")
    : "the selected path observation";
  const termBit = terminalSummary(terms) || "partition by terminal outcome";
  const pathClause = hasTagged
    ? `how frequently the first later exit is ${pathBit}`
    : `how frequently does the subsequent candle path ${pathBit}`;

  const teBit = teFilterPhrase(draft);
  const exposureBit =
    draft.exposureEnforcementMode === "strategy_enforced" &&
    draft.exposureUnit === "GAME" &&
    draft.maxEntriesPerGame === 1
      ? ", keeping only the first chronological trade per game"
      : "";

  const dateBit =
    u.dateFrom || u.dateTo
      ? ` between ${u.dateFrom || "…"} and ${u.dateTo || "…"}`
      : "";

  // Lock wording is only a fallback when no chips exist (SuperASI seed).
  // Confirm / Quick Start always compose from the entered sequence.
  if (!entries.length && resolution?.status === "READY" && resolution.matchedTemplate === "FIRST80_Q3") {
    return "Across the selected frozen NBA population, when the first observed Kalshi market touch reaches 80¢ during Q3, how frequently does the subsequent candle path reach 40¢, and how do those observations partition by terminal outcome?";
  }
  if (!entries.length && resolution?.status === "READY" && resolution.matchedTemplate === "NCAAB_FIRST80_P5") {
    return "Across the selected frozen NCAAB population, when the first observed Kalshi market touch reaches 80¢ during P5, how frequently does the subsequent candle path reach 40¢, and how do those observations partition by terminal outcome?";
  }

  return `Across ${seasonBit} ${universe} population${dateBit}, when the ${entryBit} on the ${marketBit}path occurs${teBit}${exposureBit}, ${pathClause}, and how do those observations ${termBit}?`;
}

function visibleExitConditions(draft: WorkflowDraft): ExitCondition[] {
  const tagged = draft.exitConditions.filter((e) => e.outcome === "win" || e.outcome === "loss");
  return tagged.length ? tagged : draft.exitConditions;
}

function terminalSummary(terms: ExitCondition[]): string {
  const winHold = terms.some(
    (t) => t.family === "hold_expiration_win" || (t.outcome === "win" && t.family === "yes"),
  );
  const lossHold = terms.some(
    (t) => t.family === "hold_expiration_loss" || (t.outcome === "loss" && t.family === "no"),
  );
  if (winHold || lossHold) {
    return [
      winHold ? "hold to expiration for WIN (settle YES)" : null,
      lossHold ? "hold to expiration for LOSS (settle NO)" : null,
    ]
      .filter(Boolean)
      .join(" and ");
  }
  if (!terms.length) return "";
  return terminalPhrase(terms[0]);
}

function tennisLeadPhrase(label: string, lead?: TeTennisLeadFilter): string | undefined {
  if (!lead) return undefined;
  const bits: string[] = [];
  const side = lead.scoreSide ?? "any";
  if (side === "leading") bits.push("leading");
  if (side === "tied") bits.push("tied");
  if (side === "trailing") bits.push("trailing");
  if (lead.exactDiffs?.length) bits.push(`exact ${lead.exactDiffs.join(",")}`);
  const abs = lead.absDiff ?? "any";
  if (abs === "1_5") bits.push("1–5");
  if (abs === "6_10") bits.push("6–10");
  if (abs === "11_plus") bits.push("11+");
  if (lead.customRange?.min != null || lead.customRange?.max != null) {
    bits.push(`custom ${lead.customRange.min ?? "…"}–${lead.customRange.max ?? "…"}`);
  }
  return bits.length ? `${label} ${bits.join(" ")}` : undefined;
}

function teFilterPhrase(draft: WorkflowDraft): string {
  const filters = draft.teFilters;
  const baseball = isBaseballFamily(draft.universe);
  const bits: string[] = [];
  if (filters?.tennisPointScores?.length) {
    bits.push(`point score ${filters.tennisPointScores.join(" or ")}`);
  }
  if (filters?.tennisServe?.length) {
    bits.push(filters.tennisServe.map((s) => (s === "serving" ? "YES serving" : "YES returning")).join(" or "));
  }
  if (filters?.tennisEventStates?.length) {
    bits.push(filters.tennisEventStates.map((s) => s.replace(/_/g, " ")).join(" or "));
  }
  const setLead = tennisLeadPhrase("set lead", filters?.tennisSetLead);
  const gameLead = tennisLeadPhrase("game lead", filters?.tennisGameLead);
  const pointLead = tennisLeadPhrase("point lead", filters?.tennisPointLead);
  if (setLead) bits.push(setLead);
  if (gameLead) bits.push(gameLead);
  if (pointLead) bits.push(pointLead);

  const side = filters?.scoreSide ?? "any";
  const abs = filters?.absDiff ?? "any";
  if (side === "leading") bits.push("the YES side leading");
  if (side === "tied") bits.push("the score tied");
  if (side === "trailing") bits.push("the YES side trailing");
  if (filters?.exactDiffs?.length) bits.push(`exact lead ${filters.exactDiffs.join(",")}`);
  if (abs === "1_5") bits.push("|differential| 1–5");
  if (abs === "6_10") bits.push("|differential| 6–10");
  if (abs === "11_plus") bits.push("|differential| 11+");
  if (filters?.customRange?.min != null || filters?.customRange?.max != null) {
    bits.push(`custom ${filters.customRange.min ?? "…"}–${filters.customRange.max ?? "…"}`);
  }
  if (filters?.half && filters.half !== "any") bits.push(filters.half);
  if (baseball && filters?.yesBatting && filters.yesBatting !== "any") bits.push(`YES ${filters.yesBatting}`);
  if (baseball && filters?.outs?.length) bits.push(`${filters.outs.join("/")} outs`);
  if (baseball && filters?.count && filters.count !== "any") bits.push(`count ${filters.count}`);
  if (baseball && filters?.runners && filters.runners !== "any") bits.push(filters.runners);
  if (!bits.length) return "";
  return `, with Base Terminal Efficiency scoped to ${bits.join(" and ")}`;
}

export function universeSummaryLines(draft: WorkflowDraft): Array<{ k: string; v: string }> {
  const u = draft.universe;
  const line = (ids: string[], kind: "sport" | "league" | "season" | "market" | "market_data" | "pbp") =>
    ids
      .map((id) => catalogItem(id, kind)?.label ?? id)
      .join(" · ") || "—";
  return [
    { k: "Sport", v: line(u.sports, "sport") },
    { k: "League", v: line(u.leagues, "league") },
    { k: "Seasons", v: u.seasons.length ? line(u.seasons, "season") : "Full selected seasons" },
    {
      k: "Date range",
      v: u.dateFrom || u.dateTo ? `${u.dateFrom || "…"} → ${u.dateTo || "…"}` : "Full selected seasons",
    },
    { k: "Market", v: line(u.markets, "market") },
    { k: "Market data", v: line(u.marketData, "market_data") },
    { k: "Game data", v: line(u.dataSources, "pbp") },
  ];
}

export function entrySummary(draft: WorkflowDraft): string {
  if (!draft.entryConditions.length) return "No entry condition yet.";
  const core = draft.entryConditions.map(entryPhrase).join(" AND ");
  const te = teFilterPhrase(draft);
  const exposure =
    draft.exposureEnforcementMode === "strategy_enforced" &&
    draft.exposureUnit === "GAME" &&
    draft.maxEntriesPerGame === 1
      ? " · one trade per game"
      : "";
  return `${core}${te}${exposure}` || core;
}

export function exitSummary(draft: WorkflowDraft): string {
  const visible = visibleExitConditions(draft);
  if (!visible.length) return "No observation yet.";
  const paths = visible.filter((e) => e.kind === "path");
  const horizons = visible.filter((e) => e.kind === "horizon");
  const terms = visible.filter((e) => e.kind === "terminal");
  const pathBit = [...paths.map(pathPhrase), ...horizons.map(horizonPhrase)].join(
    paths.some((p) => p.sequential) ? " → " : " · ",
  );
  return [pathBit, terminalSummary(terms)].filter(Boolean).join(" · ");
}
