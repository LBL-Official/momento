/**
 * Finite payoff math for ROLLER results.
 * CANDLE PATH ≠ FILL. MEASUREMENT ≠ EDGE.
 *
 * 80→40 Model A (FIRST80_8040_CALIBRATED_BOOK / fee model doc):
 *   +20 survive / −40 close-40 stop / 0 leak
 *   EV_gross (R) = 1 − 3q
 *   EV_cents = 20 − 60q
 * Apply only when the query is enter-80 / reach-40. Never invent this for other prices.
 */

import type { AnswerResult } from "./ResultsAnswer";
import type { WorkflowDraft } from "../workflow/types";
import { pathRate } from "./measurementLookup";
import { readResultsContract } from "./resultsContract";

export const RESEARCH_BANKROLL_CENTS = 5000;

export type TradeRow = {
  ticker?: unknown;
  internal_game_id?: unknown;
  entry_ts?: unknown;
  entry_close?: unknown;
  exit_ts?: unknown;
  exit_close?: unknown;
  hyp_pnl_cents?: unknown;
  path_true?: unknown;
  terminal_yes?: unknown;
  entry_ordinal?: unknown;
  entry_price_e4?: unknown;
  win_exit?: unknown;
  loss_exit?: unknown;
};

export function isModelA8040(draft?: WorkflowDraft | null, result?: AnswerResult | null): boolean {
  if (result && readResultsContract(result).lastTrade) return false;
  const entries = draft?.entryConditions ?? [];
  const exits = draft?.exitConditions ?? [];
  const enter80 = entries.length === 1 && entries[0].priceCents === 80 && entries[0].priceFrom == null;
  const reach40 = exits.some((e) => e.kind === "path" && e.family === "reach" && e.priceCents === 40);
  if (enter80 && reach40) return true;
  const compile = (result as { compile?: { question?: { entry_conditions?: Array<{ price_e4?: number }>; path_conditions?: Array<{ op?: string; price_e4?: number }> } } } | null)
    ?.compile?.question;
  if (!compile) return false;
  const e = compile.entry_conditions ?? [];
  const p = compile.path_conditions ?? [];
  return e.length === 1 && e[0].price_e4 === 8000 && p.some((x) => x.op === "REACH" && x.price_e4 === 4000);
}

/** πᵢ = hyp_pnl_cents or (exit_close − entry_close) // 100. Missing exit is not 0. */
export function pathReturnCents(row: TradeRow): number | null {
  if (typeof row.hyp_pnl_cents === "number" && Number.isFinite(row.hyp_pnl_cents)) {
    return Math.trunc(row.hyp_pnl_cents);
  }
  const entry =
    typeof row.entry_close === "number"
      ? row.entry_close
      : typeof row.entry_price_e4 === "number"
        ? row.entry_price_e4
        : null;
  const exit = typeof row.exit_close === "number" ? row.exit_close : null;
  if (entry == null || exit == null) return null;
  return Math.trunc((exit - entry) / 100);
}

export function tradeRows(result: AnswerResult | null | undefined): TradeRow[] {
  const pop = result?.population;
  const trades = pop?.trades ?? pop?.rows ?? [];
  return Array.isArray(trades) ? (trades as TradeRow[]) : [];
}

export function maxDrawdownCents(pnls: number[]): number | null {
  if (!pnls.length) return null;
  let peak = 0;
  let equity = 0;
  let maxDd = 0;
  for (const pnl of pnls) {
    equity += pnl;
    if (equity > peak) peak = equity;
    const dd = peak - equity;
    if (dd > maxDd) maxDd = dd;
  }
  return maxDd;
}

/** Asymptotic ruin. RoR = 1 if no edge, else ((q/p)*(L/W))^(bankroll/L). */
export function riskOfRuin(
  pWin: number,
  avgWin: number,
  avgLoss: number,
  bankrollCents = RESEARCH_BANKROLL_CENTS,
): number | null {
  if (avgLoss <= 0 || bankrollCents <= 0) return null;
  if (pWin <= 0) return 1;
  if (pWin >= 1) return 0;
  if (avgWin <= 0) return 1;
  const q = 1 - pWin;
  const ratio = (q / pWin) * (avgLoss / avgWin);
  if (ratio >= 1) return 1;
  return Math.min(1, Math.max(0, ratio ** (bankrollCents / avgLoss)));
}

export function modelAEvCents(q: number): number {
  return 20 - 60 * q;
}

export type FiniteMathReport = {
  pathTrue: number | null;
  pathFalse: number | null;
  pathAvail: number | null;
  pathRate: number | null;
  modelA: boolean;
  modelAEvCents: number | null;
  observedEvCents: number | null;
  observedN: number;
  maxDrawdownCents: number | null;
  maxDrawdownSource: string | null;
  riskOfRuin: number | null;
  riskOfRuinSource: string | null;
  bankrollCents: number;
};

export function computeFiniteMath(
  result: AnswerResult | null | undefined,
  draft?: WorkflowDraft | null,
): FiniteMathReport {
  const path = pathRate(result);
  const contract = readResultsContract(result);
  const lastPrint = contract.lastTrade;
  const modelA =
    !lastPrint &&
    (contract.economics.modelA.eligible === true || isModelA8040(draft, result));
  const namedEv = result?.measurements?.find((m) => m.name === "model_a_8040_ev_cents");
  const namedObs = result?.measurements?.find((m) => m.name === "observed_hyp_ev_cents");
  const namedDd = result?.measurements?.find((m) => m.name === "max_drawdown_cents");
  const namedRor = result?.measurements?.find((m) => m.name === "risk_of_ruin");

  if (lastPrint) {
    return {
      pathTrue: path.trueN,
      pathFalse: path.trueN != null && path.avail != null ? path.avail - path.trueN : null,
      pathAvail: path.avail,
      pathRate: path.rate,
      modelA: false,
      modelAEvCents: null,
      observedEvCents: null,
      observedN: 0,
      maxDrawdownCents: null,
      maxDrawdownSource: null,
      riskOfRuin: null,
      riskOfRuinSource: null,
      bankrollCents: RESEARCH_BANKROLL_CENTS,
    };
  }

  const rows = tradeRows(result);
  const dated = rows
    .map((r) => {
      const pnl = pathReturnCents(r);
      return pnl == null ? null : { ts: String(r.entry_ts ?? ""), pnl };
    })
    .filter((x): x is { ts: string; pnl: number } => x != null)
    .sort((a, b) => a.ts.localeCompare(b.ts));
  const observed = dated.map((x) => x.pnl);

  let observedEv = typeof namedObs?.value === "number" ? namedObs.value : null;
  if (observedEv == null && observed.length) {
    observedEv = observed.reduce((s, n) => s + n, 0) / observed.length;
  }

  let dd = typeof namedDd?.value === "number" ? namedDd.value : null;
  let ddSource = typeof namedDd?.detail?.source === "string" ? namedDd.detail.source : null;
  let ror = typeof namedRor?.value === "number" ? namedRor.value : null;
  let rorSource = typeof namedRor?.detail?.source === "string" ? namedRor.detail.source : null;

  let modelAEv = typeof namedEv?.value === "number" ? namedEv.value : null;
  if (modelAEv == null && modelA && path.rate != null) {
    modelAEv = modelAEvCents(path.rate);
  }

  if (modelA && path.rate != null && path.avail && path.trueN != null) {
    if (ror == null) {
      ror = riskOfRuin((path.avail - path.trueN) / path.avail, 20, 40);
      rorSource = "model_a_8040";
    }
    if (dd == null) {
      if (observed.length) {
        dd = maxDrawdownCents(observed);
        ddSource = "observed_hyp_pnl";
      } else if (rows.length) {
        const synth: number[] = [];
        for (const r of [...rows].sort((a, b) =>
          String(a.entry_ts ?? "").localeCompare(String(b.entry_ts ?? "")),
        )) {
          if (r.path_true === true) synth.push(-40);
          else if (r.path_true === false) synth.push(20);
        }
        dd = maxDrawdownCents(synth);
        ddSource = "model_a_synthesized_sequence";
      }
    }
  } else if (observed.length) {
    if (dd == null) {
      dd = maxDrawdownCents(observed);
      ddSource = "observed_hyp_pnl";
    }
    if (ror == null) {
      const wins = observed.filter((p) => p > 0);
      const losses = observed.filter((p) => p < 0).map((p) => -p);
      const pWin = wins.length / observed.length;
      const avgWin = wins.length ? wins.reduce((s, n) => s + n, 0) / wins.length : 0;
      const avgLoss = losses.length ? losses.reduce((s, n) => s + n, 0) / losses.length : 0;
      ror = riskOfRuin(pWin, avgWin, avgLoss);
      rorSource = "observed_hyp_pnl";
    }
  }

  return {
    pathTrue: path.trueN,
    pathFalse: path.trueN != null && path.avail != null ? path.avail - path.trueN : null,
    pathAvail: path.avail,
    pathRate: path.rate,
    modelA,
    modelAEvCents: modelAEv,
    observedEvCents: observedEv,
    observedN: observed.length,
    maxDrawdownCents: dd,
    maxDrawdownSource: ddSource,
    riskOfRuin: ror,
    riskOfRuinSource: rorSource,
    bankrollCents: RESEARCH_BANKROLL_CENTS,
  };
}
