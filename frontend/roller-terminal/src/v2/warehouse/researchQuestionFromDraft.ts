/**
 * Construct a backend ResearchQuestion from the existing workflow chips.
 * Serialization only — no CROSS / BREAK / PIT / settlement math.
 */

import type { EntryCondition, ExitCondition, TeFilters, WorkflowDraft } from "../workflow/types";

export type PeriodWindowJson = {
  period: string | null;
  clock: { remaining_from_s: number; remaining_to_s: number } | null;
};

export type ResearchQuestionJson = {
  universe: {
    sports: string[];
    leagues: string[];
    seasons: string[];
    markets: string[];
    market_data: string[];
    game_data: string[];
    date_from: string | null;
    date_to: string | null;
  };
  entry_conditions: Array<{
    id: string;
    ordinal: string;
    price_e4: number;
    period: string | null;
    clock: { remaining_from_s: number; remaining_to_s: number } | null;
    period_windows?: PeriodWindowJson[];
    nth: number | null;
    event_definition: string;
    price_field: string;
    operation?: string;
    direction?: string;
    max_entry_e4?: number;
  }>;
  path_conditions: Array<{
    id: string;
    op: string;
    price_e4: number;
    sequential: boolean;
    outcome: "win" | "loss";
  }>;
  terminal: "YES" | "NO" | "BOTH";
  requested_dimensions: string[];
  accept_limitations: boolean;
  win_hold?: boolean;
  loss_hold?: boolean;
};

export type SyntacticError =
  | "missing_entry"
  | "missing_threshold"
  | "missing_win_exit"
  | "missing_loss_exit"
  | "invalid_period"
  | "invalid_clock"
  | "invalid_entry"
  | "invalid_max_entry"
  | "malformed_date_range";

const VALID_PERIODS = new Set([
  "Q1",
  "Q2",
  "Q3",
  "Q4",
  "OT",
  "H1",
  "H2",
  "H1_1",
  "H1_2",
  "H2_1",
  "H2_2",
  "P5",
  "S1",
  "S2",
  "S3",
  "S4",
  "S5",
  "G1-3",
  "G4-6",
  "G7-9",
  "G10+",
  "T1",
  "T2",
  "T3",
  "T4",
  "T5",
  "T6",
  "T7",
  "T8",
  "T9",
  "B1",
  "B2",
  "B3",
  "B4",
  "B5",
  "B6",
  "B7",
  "B8",
  "B9",
  "TX",
  "BX",
  "I7",
]);

const ENTRY_FAMILY: Record<string, { ordinal: string; operation: string }> = {
  first_touch: { ordinal: "FIRST_TOUCH", operation: "FIRST_TOUCH" },
  second_touch: { ordinal: "SECOND_TOUCH", operation: "SECOND_TOUCH" },
  third_touch: { ordinal: "THIRD_TOUCH", operation: "THIRD_TOUCH" },
  fourth_touch: { ordinal: "FOURTH_TOUCH", operation: "FOURTH_TOUCH" },
  nth_touch: { ordinal: "NTH_TOUCH", operation: "NTH_TOUCH" },
  cross: { ordinal: "FIRST_TOUCH", operation: "CROSS" },
  touch: { ordinal: "FIRST_TOUCH", operation: "FIRST_TOUCH" },
  break: { ordinal: "FIRST_TOUCH", operation: "BREAK" },
  reversion: { ordinal: "FIRST_TOUCH", operation: "REVERSION" },
  bounce: { ordinal: "FIRST_TOUCH", operation: "BOUNCE" },
  recovery: { ordinal: "FIRST_TOUCH", operation: "RECOVERY" },
  above: { ordinal: "FIRST_TOUCH", operation: "ABOVE" },
  below: { ordinal: "FIRST_TOUCH", operation: "BELOW" },
  maximum_touch: { ordinal: "FIRST_TOUCH", operation: "MAXIMUM_TOUCH" },
  minimum_touch: { ordinal: "FIRST_TOUCH", operation: "MINIMUM_TOUCH" },
};

const PATH_FAMILY: Record<string, string> = {
  reach: "REACH",
  drop: "DROP_TO",
  drop_to: "DROP_TO",
  rise: "RISE_TO",
  rise_to: "RISE_TO",
  recover: "RECOVER",
  bounce: "BOUNCE",
  revert: "REVERT",
  maximum_move: "MAXIMUM_MOVE",
  minimum_move: "MINIMUM_MOVE",
  never_reach: "NEVER_REACH",
};

const MARKET_DATA: Record<string, string> = {
  candles: "candles",
  candle: "candles",
  tradable_yes_bid: "candles",
  last_trade: "last_trade",
  last_trade_print: "last_trade",
  tick: "historical_tick",
  ticks: "historical_tick",
  historical_tick: "historical_tick",
  l2: "historical_l2",
  historical_l2: "historical_l2",
  orderbook: "orderbook",
};

function token(value: unknown): string {
  return String(value ?? "")
    .trim()
    .toLowerCase()
    .replace(/\s+/g, "_")
    .replace(/-/g, "_");
}

function season(value: unknown): string {
  const raw = String(value ?? "")
    .trim()
    .replace(/[–_]/g, "-");
  if (raw === "2025-26" || raw === "2025-2026") return "2025-2026";
  return raw;
}

function centsToE4(value: unknown): number | null {
  if (value == null || value === "") return null;
  const n = Number(value);
  if (!Number.isFinite(n)) return null;
  return Math.round(n * 100);
}

function clockSecs(raw: string): number | null {
  if (!raw) return null;
  if (/^\d+$/.test(raw)) return Number(raw);
  const parts = raw.replace(".", ":").split(":");
  if (parts.length !== 2) return null;
  const m = Number(parts[0]);
  const s = Number(parts[1]);
  if (!Number.isFinite(m) || !Number.isFinite(s)) return null;
  return m * 60 + s;
}

function canonicalNbaUniverse(sports: string[], leagues: string[]): { sports: string[]; leagues: string[] } {
  const s = sports.map((x) => x.toUpperCase()).filter(Boolean);
  const l = leagues.map((x) => x.toUpperCase()).filter(Boolean);
  if (l.includes("MLB") || s.includes("MLB") || s.includes("BASEBALL")) {
    return {
      sports: ["MLB", ...s.filter((x) => x !== "MLB" && x !== "BASEBALL")],
      leagues: ["MLB", ...l.filter((x) => x !== "MLB" && x !== "BASEBALL")],
    };
  }
  const atp = l.includes("ATP") || s.includes("ATP");
  const wta = l.includes("WTA") || s.includes("WTA");
  if (atp && !wta) {
    return {
      sports: ["ATP", ...s.filter((x) => x !== "ATP" && x !== "TENNIS")],
      leagues: ["ATP", ...l.filter((x) => x !== "ATP" && x !== "TENNIS")],
    };
  }
  if (wta && !atp) {
    return {
      sports: ["WTA", ...s.filter((x) => x !== "WTA" && x !== "TENNIS")],
      leagues: ["WTA", ...l.filter((x) => x !== "WTA" && x !== "TENNIS")],
    };
  }
  const ncaab = l.includes("NCAAB") || s.includes("NCAAB");
  const nba = l.includes("NBA") || s.includes("NBA");
  if (ncaab && !nba) {
    return {
      sports: ["NCAAB", ...s.filter((x) => x !== "NCAAB" && x !== "BASKETBALL")],
      leagues: ["NCAAB", ...l.filter((x) => x !== "NCAAB" && x !== "BASKETBALL")],
    };
  }
  if (nba && !ncaab) {
    return {
      sports: ["NBA", ...s.filter((x) => x !== "NBA" && x !== "BASKETBALL")],
      leagues: ["NBA", ...l.filter((x) => x !== "NBA" && x !== "BASKETBALL")],
    };
  }
  return { sports: s, leagues: l };
}

export function isWarehouseDeskDraft(draft: WorkflowDraft): boolean {
  const leagues = draft.universe.leagues.map((s) => s.toUpperCase());
  const sports = draft.universe.sports.map((s) => s.toUpperCase());
  const mlb = leagues.includes("MLB") || sports.includes("MLB") || sports.includes("BASEBALL");
  const nba = leagues.includes("NBA") || sports.includes("NBA");
  const ncaab = leagues.includes("NCAAB") || sports.includes("NCAAB");
  const atp = leagues.includes("ATP") || sports.includes("ATP");
  const wta = leagues.includes("WTA") || sports.includes("WTA");
  return mlb || nba || ncaab || atp || wta;
}

export function validateDraftSyntax(draft: WorkflowDraft): SyntacticError[] {
  const errors = new Set<SyntacticError>();
  const from = draft.universe.dateFrom?.slice(0, 10) || "";
  const to = draft.universe.dateTo?.slice(0, 10) || "";
  if (from && to && from > to) errors.add("malformed_date_range");
  if (!draft.entryConditions.length) errors.add("missing_entry");
  for (const entry of draft.entryConditions) {
    if (!ENTRY_FAMILY[entry.family]) errors.add("invalid_entry");
    if (entry.priceCents == null) errors.add("missing_threshold");
    if (
      entry.maxEntryCents != null &&
      (entry.maxEntryCents < 5 ||
        entry.maxEntryCents > 95 ||
        (entry.priceCents != null && entry.maxEntryCents < entry.priceCents))
    ) {
      errors.add("invalid_max_entry");
    }
    if (entry.period && !VALID_PERIODS.has(entry.period.toUpperCase())) errors.add("invalid_period");
    if ((entry.clockFrom || entry.clockTo) && (clockSecs(entry.clockFrom || "") == null || clockSecs(entry.clockTo || "") == null)) {
      errors.add("invalid_clock");
    }
    for (const window of entry.periodWindows || []) {
      if (window.period && !VALID_PERIODS.has(window.period.toUpperCase())) errors.add("invalid_period");
      if (
        (window.clockFrom || window.clockTo) &&
        (clockSecs(window.clockFrom || "") == null || clockSecs(window.clockTo || "") == null)
      ) {
        errors.add("invalid_clock");
      }
    }
  }
  const exits = draft.exitConditions;
  const hasWin = exits.some((e) => e.outcome === "win" || e.family === "hold_expiration_win" || e.family === "yes");
  const hasLoss = exits.some((e) => e.outcome === "loss" || e.family === "hold_expiration_loss" || e.family === "no");
  const hasHold = exits.some((e) => e.family === "both" || e.kind === "terminal");
  if (!hasWin && !hasHold) errors.add("missing_win_exit");
  if (!hasLoss && !hasHold) errors.add("missing_loss_exit");
  return [...errors];
}

function mapClock(from?: string, to?: string): { remaining_from_s: number; remaining_to_s: number } | null {
  if (!from && !to) return null;
  const lo = clockSecs(from || "");
  const hi = clockSecs(to || "");
  if (lo == null || hi == null) return null;
  return { remaining_from_s: lo, remaining_to_s: hi };
}

function mapPeriodWindow(window: { period?: string; clockFrom?: string; clockTo?: string; clock?: PeriodWindowJson["clock"] }): PeriodWindowJson {
  const clock =
    window.clock && "remaining_from_s" in window.clock
      ? window.clock
      : mapClock(window.clockFrom, window.clockTo);
  return {
    period: window.period ? window.period.toUpperCase() : null,
    clock,
  };
}

export function teFiltersActive(filters: TeFilters | undefined): boolean {
  if (!filters) return false;
  if (filters.scoreSide && filters.scoreSide !== "any") return true;
  if (filters.absDiff && filters.absDiff !== "any") return true;
  if ((filters.exactDiffs ?? []).length) return true;
  if (filters.customRange?.min != null || filters.customRange?.max != null) return true;
  if (filters.half === "top" || filters.half === "bottom") return true;
  if (filters.yesBatting != null) return true;
  if ((filters.outs ?? []).length) return true;
  if (filters.count && filters.count !== "any") return true;
  if (filters.runners && filters.runners !== "any") return true;
  if ((filters.tennisPointScores ?? []).length) return true;
  if ((filters.tennisServe ?? []).length) return true;
  if ((filters.tennisEventStates ?? []).length) return true;
  if (filters.tennisSetLead) return true;
  if (filters.tennisGameLead) return true;
  if (filters.tennisPointLead) return true;
  return false;
}

function mapEntry(entry: EntryCondition, index: number) {
  const mapped = ENTRY_FAMILY[entry.family];
  const price = centsToE4(entry.priceCents) ?? 0;
  const rawWindows = (entry.periodWindows || []).filter((w) => w.period || w.clockFrom || w.clockTo);
  let period = entry.period ? entry.period.toUpperCase() : null;
  let clock = mapClock(entry.clockFrom, entry.clockTo);
  let period_windows: PeriodWindowJson[] | undefined;
  if (rawWindows.length > 1) {
    period = null;
    clock = null;
    period_windows = rawWindows.map(mapPeriodWindow);
  } else if (rawWindows.length === 1) {
    const only = mapPeriodWindow(rawWindows[0]);
    period = only.period;
    clock = only.clock;
  }
  const nth =
    mapped?.ordinal === "NTH_TOUCH" && typeof entry.touchNValue === "number" ? entry.touchNValue : null;
  const payload: ResearchQuestionJson["entry_conditions"][number] = {
    id: entry.id || `e${index + 1}`,
    ordinal: mapped?.ordinal ?? "FIRST_TOUCH",
    price_e4: price,
    period,
    clock,
    nth,
    event_definition: "TRADABLE_CLOSE_CROSS",
    price_field: "yes_bid_close",
  };
  if (period_windows?.length) payload.period_windows = period_windows;
  if (mapped && mapped.operation !== mapped.ordinal) payload.operation = mapped.operation;
  if (entry.direction) payload.direction = entry.direction;
  if (entry.maxEntryCents != null) {
    const ceiling = centsToE4(entry.maxEntryCents);
    if (ceiling != null) payload.max_entry_e4 = ceiling;
  }
  return payload;
}

function mapExit(exit: ExitCondition, usedWin: boolean) {
  const fam = token(exit.family);
  const op = PATH_FAMILY[fam];
  if (!op) return null;
  const price = centsToE4(exit.priceCents);
  if (price == null) return null;
  const outcome: "win" | "loss" =
    exit.outcome === "win" ? "win" : exit.outcome === "loss" ? "loss" : usedWin ? "loss" : "win";
  return {
    id: exit.id || (outcome === "win" ? "win" : "loss"),
    op,
    price_e4: price,
    sequential: Boolean(exit.sequential),
    outcome,
  };
}

export function researchQuestionFromDraft(draft: WorkflowDraft): {
  question: ResearchQuestionJson;
  errors: SyntacticError[];
} {
  const errors = validateDraftSyntax(draft);
  const { sports, leagues } = canonicalNbaUniverse(draft.universe.sports, draft.universe.leagues);
  const seasons = draft.universe.seasons.map(season).filter(Boolean);
  const markets = draft.universe.markets.map(token).filter(Boolean);
  const market_data = draft.universe.marketData.map((m) => MARKET_DATA[token(m)] ?? token(m)).filter(Boolean);
  const date_from = draft.universe.dateFrom?.slice(0, 10) || null;
  const date_to = draft.universe.dateTo?.slice(0, 10) || null;
  const entries = draft.entryConditions.map(mapEntry);
  const paths: ResearchQuestionJson["path_conditions"] = [];
  let win_hold = false;
  let loss_hold = false;
  let terminal: "YES" | "NO" | "BOTH" = "BOTH";
  const dims: string[] = [];
  for (const exit of draft.exitConditions) {
    const fam = token(exit.family);
    if (fam === "yes") {
      terminal = "YES";
      win_hold = true;
      continue;
    }
    if (fam === "no") {
      terminal = "NO";
      loss_hold = true;
      continue;
    }
    if (fam === "both" || fam.startsWith("hold_expiration") || exit.kind === "terminal") {
      dims.push("HOLD_TO_SETTLEMENT");
      if (fam.endsWith("win") || exit.outcome === "win") win_hold = true;
      else if (fam.endsWith("loss") || exit.outcome === "loss") loss_hold = true;
      else {
        win_hold = true;
        loss_hold = true;
      }
      continue;
    }
    const mapped = mapExit(exit, paths.some((p) => p.outcome === "win"));
    if (mapped) paths.push(mapped);
  }
  const needsPbp =
    teFiltersActive(draft.teFilters) ||
    draft.entryConditions.some(
      (e) =>
        Boolean(e.period || e.clockFrom || e.clockTo) ||
        Boolean((e.periodWindows || []).some((w) => w.period || w.clockFrom || w.clockTo)),
    );
  if (!dims.length) dims.push("HOLD_TO_SETTLEMENT");
  const question: ResearchQuestionJson = {
    universe: {
      sports,
      leagues: leagues.length ? leagues : sports,
      seasons,
      markets: markets.length ? markets : ["kalshi"],
      market_data: market_data.length ? market_data : ["candles"],
      game_data: needsPbp ? ["pbp"] : [],
      date_from,
      date_to,
    },
    entry_conditions: entries,
    path_conditions: paths,
    terminal,
    requested_dimensions: [...new Set(dims)],
    accept_limitations: false,
  };
  if (win_hold) question.win_hold = true;
  if (loss_hold) question.loss_hold = true;
  const lastTrade = question.universe.market_data.some((m) => token(m).includes("last_trade"));
  if (lastTrade) {
    question.entry_conditions = question.entry_conditions.map((entry) => ({
      ...entry,
      price_field: "last_close_e4",
    }));
  }
  return { question, errors };
}
