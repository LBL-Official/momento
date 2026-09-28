/**
 * Last-trade Results contract. Consumes observation_basis / analysis envelope.
 * TradableBar.bid on LAST_TRADE_PRINT is last_close_e4 — never yes_bid_close.
 */

import type { AnswerResult } from "./ResultsAnswer";
import { tradeRows } from "./finiteMath";
import { LAST_TRADE_UNAVAILABLE, isLastTradePrint } from "./lastTradeBasis";
import { readResultsContract, type ContractRates } from "./resultsContract";

export { LAST_TRADE_UNAVAILABLE, isLastTradePrint };
export type LastTradeRates = ContractRates;

function pct(n: number, d: number): number {
  return d > 0 ? n / d : 0;
}

export function lastTradeRates(result: AnswerResult): LastTradeRates {
  return readResultsContract(result).rates;
}

export function fmtRate(num: number | null, den: number | null, digits = 1): string {
  if (num == null || den == null || den <= 0) return "—";
  return `${((num / den) * 100).toFixed(digits)}% · ${num} / ${den}`;
}

export function lastTradePrintDisplacement(result: AnswerResult): {
  n: number;
  meanCents: number | null;
  winHold: number;
  feedsEconomics: false;
} {
  const rows = tradeRows(result);
  const xs: number[] = [];
  let winHold = 0;
  for (const row of rows) {
    if (row.win_exit === true && row.exit_close == null) winHold += 1;
    if (row.loss_exit !== true) continue;
    const entry =
      typeof row.entry_close === "number"
        ? row.entry_close
        : typeof row.entry_price_e4 === "number"
          ? row.entry_price_e4
          : null;
    const exit = typeof row.exit_close === "number" ? row.exit_close : null;
    if (entry == null || exit == null) continue;
    xs.push((exit - entry) / 100);
  }
  return {
    n: xs.length,
    meanCents: xs.length ? xs.reduce((s, x) => s + x, 0) / xs.length : null,
    winHold,
    feedsEconomics: false,
  };
}

export function lastTradeEconomicsUnavailable(result: AnswerResult): boolean {
  return isLastTradePrint(result);
}

export function coveragePct(settled: number | null, n: number | null): string {
  if (settled == null || n == null || n <= 0) return "—";
  return `${((settled / n) * 100).toFixed(2)}% · ${settled} / ${n}`;
}

export { pct };
