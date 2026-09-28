/**
 * Render-only Results contract. Backend analysis.results_contract is authority.
 * Do not infer YES BID from TradableBar.bid. Do not reconstruct population EV.
 */

import type { AnswerResult } from "./ResultsAnswer";
import { LAST_TRADE_UNAVAILABLE } from "./lastTradeBasis";
import { ratePartsFromNames } from "./measurementLookup";

export type ContractRates = {
  n: number | null;
  nEntry: number | null;
  pathTrue: number | null;
  pathFalse: number | null;
  winExit: number | null;
  lossExit: number | null;
  classified: number | null;
  unclassified: number | null;
  terminalYes: number | null;
  terminalNo: number | null;
  terminalMissing: number | null;
  settled: number | null;
};

export const CANDLE_NOT_FILL = "CANDLE PATH ≠ FILL";

export type EconomicMode = "LAST_TRADE_PRINT" | "TRADABLE_YES_BID" | "UNKNOWN";

export type StatusBlock = {
  status: string;
  reason?: string;
  estimate_cents?: number | null;
  estimate?: number | null;
  n?: number | null;
  eligible?: boolean;
  formula?: string;
  q?: number | null;
  break_even_total_cost_cents?: number | null;
  expected_allocation_dollars?: number | null;
  terminal_yes?: number | null;
  terminal_no?: number | null;
  terminal_missing?: number | null;
  settled?: number | null;
  feeds_population_ev?: boolean;
};

export type PrintDisplacement = {
  status?: string;
  n: number;
  meanCents: number | null;
  winHold: number;
  feedsEconomics: false;
  reason?: string;
};

export type ExposureView = {
  status: string;
  declaredUnit: string;
  maxEntriesPerUnit: number | null;
  reason?: string;
  nUniqueGames: number | null;
  nRows: number | null;
  strategyStatisticsPermitted: boolean;
};

export type ResultsContractView = {
  economicMode: EconomicMode;
  lastTrade: boolean;
  tradable: boolean;
  rates: ContractRates;
  economics: {
    observedPathEv: StatusBlock;
    capitalization: StatusBlock;
    sharpe: StatusBlock;
    sortino: StatusBlock;
    breakEven: StatusBlock;
    bookPriceEv: StatusBlock;
    modelA: StatusBlock;
    fillAdjusted: StatusBlock;
    settlementEv: StatusBlock;
    riskOfRuin: StatusBlock;
    strategyPnl: StatusBlock;
  };
  hold: {
    winHoldValid: boolean;
    exitCloseNullValid: boolean;
    unclassifiedIsNotLoss: boolean;
    pathFalseIsNotLoss: boolean;
    note: string;
  };
  printDisplacement: PrintDisplacement | null;
  exposure: ExposureView;
  disclaimers: string[];
  source: "envelope" | "fallback";
};

function asRec(v: unknown): Record<string, unknown> | null {
  return v && typeof v === "object" ? (v as Record<string, unknown>) : null;
}

function num(v: unknown): number | null {
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

function statusOf(v: unknown, fallback: StatusBlock): StatusBlock {
  const r = asRec(v);
  if (!r) return fallback;
  return {
    status: String(r.status ?? fallback.status),
    reason: typeof r.reason === "string" ? r.reason : fallback.reason,
    estimate_cents: num(r.estimate_cents) ?? num(r.mean_cents),
    estimate: num(r.estimate),
    n: num(r.n),
    eligible: typeof r.eligible === "boolean" ? r.eligible : fallback.eligible,
    formula: typeof r.formula === "string" ? r.formula : fallback.formula,
    q: num(r.q),
    break_even_total_cost_cents: num(r.break_even_total_cost_cents),
    expected_allocation_dollars: num(r.expected_allocation_dollars),
    terminal_yes: num(r.terminal_yes),
    terminal_no: num(r.terminal_no),
    terminal_missing: num(r.terminal_missing),
    settled: num(r.settled),
    feeds_population_ev: r.feeds_population_ev === true ? true : false,
  };
}

function unavailable(reason: string): StatusBlock {
  return { status: "UNAVAILABLE", reason };
}

function emptyExposure(): ExposureView {
  return {
    status: "UNVERIFIED",
    declaredUnit: "GAME",
    maxEntriesPerUnit: 1,
    reason: "No retained rows to verify EXPOSURE_UNIT=GAME · MAX_ENTRIES_PER_GAME=1. Do not assume N is unique games.",
    nUniqueGames: null,
    nRows: null,
    strategyStatisticsPermitted: true,
  };
}

function adaptExposure(raw: unknown): ExposureView {
  const r = asRec(raw);
  if (!r) return emptyExposure();
  return {
    status: String(r.status || "UNVERIFIED"),
    declaredUnit: String(r.exposure_unit || r.declared_unit || "GAME"),
    maxEntriesPerUnit: num(r.max_entries_per_unit) ?? num(r.max_entries_per_game),
    reason: typeof r.reason === "string" ? r.reason : undefined,
    nUniqueGames: num(r.n_unique_games),
    nRows: num(r.n_rows),
    strategyStatisticsPermitted: r.strategy_statistics_permitted !== false,
  };
}

function emptyRates(): ContractRates {
  return {
    n: null,
    nEntry: null,
    pathTrue: null,
    pathFalse: null,
    winExit: null,
    lossExit: null,
    classified: null,
    unclassified: null,
    terminalYes: null,
    terminalNo: null,
    terminalMissing: null,
    settled: null,
  };
}

function ratesFromEnvelope(result: AnswerResult): ContractRates {
  const n = result.summary?.population_n ?? result.population?.count ?? result.identity?.reported_n ?? null;
  const te = result.identity?.te_scope;
  const nEntry = te?.n_entry ?? result.identity?.n_entry_events ?? result.identity?.entry_eligible ?? null;
  const path = ratePartsFromNames(result, ["path_rate"]);
  const win = ratePartsFromNames(result, ["win_exit_rate"]);
  const loss = ratePartsFromNames(result, ["loss_exit_rate"]);
  const pathTrue = path.trueN ?? result.identity?.path_true ?? null;
  const pathAvail = path.avail ?? n;
  const pathFalse =
    result.identity?.path_false ?? (pathTrue != null && pathAvail != null ? pathAvail - pathTrue : null);
  const winExit = win.trueN;
  const lossExit = loss.trueN;
  const classified = win.avail ?? (winExit != null && lossExit != null ? winExit + lossExit : null);
  const unclassified = n != null && classified != null && n - classified >= 0 ? n - classified : null;
  const terminalYes = result.identity?.terminal_yes ?? null;
  const terminalNo = result.identity?.terminal_no ?? null;
  const terminalMissing = result.identity?.terminal_missing ?? null;
  const settled =
    terminalYes != null && terminalNo != null
      ? terminalYes + terminalNo
      : ratePartsFromNames(result, ["kalshi_yes_rate"]).avail;
  return {
    n,
    nEntry,
    pathTrue,
    pathFalse,
    winExit,
    lossExit,
    classified,
    unclassified,
    terminalYes,
    terminalNo,
    terminalMissing,
    settled,
  };
}

function countsToRates(counts: Record<string, unknown> | null, fallback: ContractRates): ContractRates {
  if (!counts) return fallback;
  return {
    n: num(counts.n) ?? fallback.n,
    nEntry: num(counts.n_entry) ?? fallback.nEntry,
    pathTrue: num(counts.path_true) ?? fallback.pathTrue,
    pathFalse: num(counts.path_false) ?? fallback.pathFalse,
    winExit: num(counts.win_exit) ?? fallback.winExit,
    lossExit: num(counts.loss_exit) ?? fallback.lossExit,
    classified: num(counts.classified) ?? fallback.classified,
    unclassified: num(counts.unclassified) ?? fallback.unclassified,
    terminalYes: num(counts.terminal_yes) ?? fallback.terminalYes,
    terminalNo: num(counts.terminal_no) ?? fallback.terminalNo,
    terminalMissing: num(counts.terminal_missing) ?? fallback.terminalMissing,
    settled: num(counts.settled) ?? fallback.settled,
  };
}

function adaptPrint(raw: unknown): PrintDisplacement | null {
  const r = asRec(raw);
  if (!r) return null;
  return {
    status: typeof r.status === "string" ? r.status : undefined,
    n: num(r.n) ?? 0,
    meanCents: num(r.mean_cents),
    winHold: num(r.win_hold_no_exit) ?? 0,
    feedsEconomics: false,
    reason: typeof r.reason === "string" ? r.reason : undefined,
  };
}

function modeFromResult(result: AnswerResult | null | undefined): EconomicMode {
  if (!result) return "UNKNOWN";
  const basis = String(result.observation_basis || result.mlb?.observation_basis || "");
  const prov = result.provenance || {};
  if (basis.includes("LAST_TRADE")) return "LAST_TRADE_PRINT";
  if (String(prov.price_basis || "").includes("LAST_TRADE")) return "LAST_TRADE_PRINT";
  if (String(prov.market_data_type || "").includes("LAST_TRADE")) return "LAST_TRADE_PRINT";
  if (String(prov.market_data || "").includes("last_trade")) return "LAST_TRADE_PRINT";
  const observed = result.analysis?.observed_returns as { reason?: string } | undefined;
  if (String(observed?.reason || "").includes("LAST TRADE")) return "LAST_TRADE_PRINT";
  if (basis.includes("TRADABLE") || basis.includes("YES_BID")) return "TRADABLE_YES_BID";
  return "TRADABLE_YES_BID";
}

function fallbackEconomics(lastTrade: boolean, analysis: Record<string, unknown> | null): ResultsContractView["economics"] {
  if (lastTrade) {
    const block = unavailable(LAST_TRADE_UNAVAILABLE);
    const settle = asRec(analysis?.settlement_payoff) ?? asRec(analysis?.settlement);
    return {
      observedPathEv: block,
      capitalization: block,
      sharpe: block,
      sortino: block,
      breakEven: block,
      bookPriceEv: block,
      modelA: unavailable("Model A is an exact 80/40 subtype and is not defined on LAST_TRADE_PRINT."),
      fillAdjusted: unavailable("LAST TRADE ≠ FILL. Execution data required."),
      settlementEv: {
        status: String(settle?.status || "INCOMPLETE"),
        reason: typeof settle?.reason === "string" ? settle.reason : "TERMINAL DATA INCOMPLETE",
        terminal_yes: num(settle?.terminal_yes),
        terminal_no: num(settle?.terminal_no),
        terminal_missing: num(settle?.terminal_missing),
      },
      riskOfRuin: unavailable("No explicit stochastic bankroll model. LAST TRADE ≠ FILL."),
      strategyPnl: block,
    };
  }
  const observed = asRec(analysis?.observed_ev) ?? asRec(analysis?.observed_path) ?? asRec(analysis?.observed_returns);
  const cap = asRec(analysis?.capitalization) ?? asRec(analysis?.allocation);
  const hurdle = asRec(analysis?.economic_hurdle);
  const book = asRec(analysis?.book_price) ?? asRec(analysis?.hypothetical_payoff);
  const settle = asRec(analysis?.settlement_payoff) ?? asRec(analysis?.settlement);
  const obsStatus = String(observed?.status || (num(observed?.estimate_cents) != null || num(observed?.mean_cents) != null ? "OBSERVED" : "UNAVAILABLE"));
  return {
    observedPathEv: {
      status: obsStatus,
      reason: CANDLE_NOT_FILL,
      estimate_cents: num(observed?.estimate_cents) ?? num(observed?.mean_cents),
      n: num(observed?.n),
    },
    capitalization: {
      status: cap ? String(asRec(cap.observed)?.status || (asRec(cap.observed) ? "OBSERVED" : "UNAVAILABLE")) : "UNAVAILABLE",
      reason: CANDLE_NOT_FILL,
      expected_allocation_dollars: num(asRec(cap?.observed)?.expected_allocation_dollars),
    },
    sharpe: { status: obsStatus === "OBSERVED" ? "OBSERVED" : "UNAVAILABLE", reason: CANDLE_NOT_FILL },
    sortino: { status: obsStatus === "OBSERVED" ? "OBSERVED" : "UNAVAILABLE", reason: CANDLE_NOT_FILL },
    breakEven: {
      status: num(hurdle?.break_even_total_cost_cents) != null ? "OBSERVED" : "UNAVAILABLE",
      break_even_total_cost_cents: num(hurdle?.break_even_total_cost_cents),
      reason: CANDLE_NOT_FILL,
    },
    bookPriceEv: {
      status: String(book?.status || "UNAVAILABLE"),
      estimate_cents: num(book?.ev_cents),
      reason: "Explicit WIN/LOSS payoff chips required.",
    },
    modelA: unavailable("Model A is exact 80¢ entry / 40¢ LOSS on TRADABLE_YES_BID only."),
    fillAdjusted: unavailable(CANDLE_NOT_FILL),
    settlementEv: {
      status: String(settle?.status || "DATA_REQUIRED"),
      estimate_cents: num(settle?.ev_cents),
      reason: typeof settle?.reason === "string" ? settle.reason : "Settlement uses measured YES/NO only.",
      terminal_yes: num(settle?.terminal_yes),
      terminal_no: num(settle?.terminal_no),
      terminal_missing: num(settle?.terminal_missing),
    },
    riskOfRuin: unavailable("RoR is not a live-account forecast."),
    strategyPnl: unavailable("Strategy P&L requires fills. " + CANDLE_NOT_FILL),
  };
}

export function readResultsContract(result: AnswerResult | null | undefined): ResultsContractView {
  const ratesFallback = result ? ratesFromEnvelope(result) : emptyRates();
  const analysis = asRec(result?.analysis);
  const raw = asRec(analysis?.results_contract);
  if (raw) {
    const mode = (raw.economic_mode as EconomicMode) || modeFromResult(result);
    const lastTrade = mode === "LAST_TRADE_PRINT";
    const ratesObj = asRec(raw.rates);
    const counts = asRec(ratesObj?.counts);
    const eco = asRec(raw.economics) || {};
    const hold = asRec(raw.hold);
    return {
      economicMode: mode,
      lastTrade,
      tradable: mode === "TRADABLE_YES_BID",
      rates: countsToRates(counts, ratesFallback),
      economics: {
        observedPathEv: statusOf(eco.observed_path_ev, unavailable(lastTrade ? LAST_TRADE_UNAVAILABLE : CANDLE_NOT_FILL)),
        capitalization: statusOf(eco.capitalization, unavailable(lastTrade ? LAST_TRADE_UNAVAILABLE : CANDLE_NOT_FILL)),
        sharpe: statusOf(eco.sharpe, unavailable(lastTrade ? LAST_TRADE_UNAVAILABLE : CANDLE_NOT_FILL)),
        sortino: statusOf(eco.sortino, unavailable(lastTrade ? LAST_TRADE_UNAVAILABLE : CANDLE_NOT_FILL)),
        breakEven: statusOf(eco.break_even_edge, unavailable(lastTrade ? LAST_TRADE_UNAVAILABLE : CANDLE_NOT_FILL)),
        bookPriceEv: statusOf(eco.book_price_ev, unavailable("No explicit WIN/LOSS payoff chips.")),
        modelA: statusOf(eco.model_a_8040_ev, unavailable("Model A is exact 80/40 on TRADABLE_YES_BID only.")),
        fillAdjusted: statusOf(eco.fill_adjusted_ev, unavailable(lastTrade ? "LAST TRADE ≠ FILL." : CANDLE_NOT_FILL)),
        settlementEv: statusOf(eco.settlement_ev, { status: "INCOMPLETE", reason: "TERMINAL DATA INCOMPLETE" }),
        riskOfRuin: statusOf(eco.risk_of_ruin, unavailable("No explicit stochastic bankroll model.")),
        strategyPnl: statusOf(eco.strategy_pnl, unavailable(lastTrade ? LAST_TRADE_UNAVAILABLE : CANDLE_NOT_FILL)),
      },
      hold: {
        winHoldValid: hold?.win_hold_to_expiration_valid !== false,
        exitCloseNullValid: hold?.exit_close_null_is_valid_for_win_hold !== false,
        unclassifiedIsNotLoss: hold?.unclassified_is_not_loss !== false,
        pathFalseIsNotLoss: hold?.path_false_is_not_loss !== false,
        note: typeof hold?.note === "string" ? hold.note : "HOLD_TO_EXPIRATION · exit_close is None by definition",
      },
      printDisplacement: lastTrade ? adaptPrint(raw.print_displacement) : null,
      exposure: adaptExposure(raw.exposure),
      disclaimers: Array.isArray(raw.disclaimers) ? raw.disclaimers.map(String) : [],
      source: "envelope",
    };
  }
  const mode = modeFromResult(result);
  const lastTrade = mode === "LAST_TRADE_PRINT";
  return {
    economicMode: mode,
    lastTrade,
    tradable: mode === "TRADABLE_YES_BID",
    rates: ratesFallback,
    economics: fallbackEconomics(lastTrade, analysis),
    hold: {
      winHoldValid: true,
      exitCloseNullValid: true,
      unclassifiedIsNotLoss: true,
      pathFalseIsNotLoss: true,
      note: "HOLD_TO_EXPIRATION · exit_close is None by definition · not missing candle data",
    },
    printDisplacement: null,
    exposure: emptyExposure(),
    disclaimers: lastTrade
      ? [
          "LAST TRADE ≠ YES BID",
          "LAST TRADE ≠ FILL",
          "PATH WIN ≠ TERMINAL YES",
          "PATH LOSS ≠ TERMINAL NO",
          "PATH FALSE ≠ LOSS",
          "MEASUREMENT ≠ EDGE",
        ]
      : ["CANDLE PATH ≠ FILL", "PATH FALSE ≠ LOSS", "MEASUREMENT ≠ EDGE"],
    source: "fallback",
  };
}

export function economicsOpen(block: StatusBlock | undefined): boolean {
  if (!block) return false;
  if (block.status === "CARDINALITY_VIOLATION") return false;
  return block.status === "OBSERVED" || block.status === "HYPOTHETICAL" || block.status === "DERIVED";
}
