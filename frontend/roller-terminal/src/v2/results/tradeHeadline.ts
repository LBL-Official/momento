import type { AnswerResult } from "./ResultsAnswer";
import type { ContractRates } from "./resultsContract";

export type SameNRates = {
  n: number;
  wins: number;
  losses: number;
  other: number;
  pWin: number;
  pLoss: number;
  pOther: number;
  taggedExits: boolean;
};

export type BinaryBreakeven = {
  entryCents: number;
  breakeven: number;
  margin: number;
  evCents: number;
};

export function entryCentsFromResult(result: AnswerResult): number | null {
  const e = result.compile?.question?.entry_conditions?.[0];
  if (e?.price_e4 != null && Number.isFinite(e.price_e4)) {
    return Math.round(e.price_e4 / 100);
  }
  return null;
}

/** Wins and losses share population N. Residual is not LOSS. */
export function sameNRates(rates: ContractRates): SameNRates | null {
  const n = rates.n;
  if (n == null || n <= 0) return null;
  const tagged = rates.winExit != null || rates.lossExit != null;
  const wins = tagged ? (rates.winExit ?? 0) : (rates.pathTrue ?? 0);
  const losses = tagged ? (rates.lossExit ?? 0) : 0;
  const other = Math.max(0, n - wins - losses);
  return {
    n,
    wins,
    losses,
    other,
    pWin: wins / n,
    pLoss: losses / n,
    pOther: other / n,
    taggedExits: tagged,
  };
}

export function binaryBreakeven(
  entryCents: number | null,
  pWin: number | null,
): BinaryBreakeven | null {
  if (entryCents == null || pWin == null || !Number.isFinite(pWin)) return null;
  const be = entryCents / 100;
  return {
    entryCents,
    breakeven: be,
    margin: pWin - be,
    evCents: 100 * pWin - entryCents,
  };
}

export function fmtPct(v: number | null | undefined, digits = 1): string {
  if (v == null || !Number.isFinite(v)) return "—";
  return `${(v * 100).toFixed(digits)}%`;
}

export function fmtPp(v: number | null | undefined, digits = 1): string {
  if (v == null || !Number.isFinite(v)) return "—";
  const sign = v > 0 ? "+" : "";
  return `${sign}${(v * 100).toFixed(digits)} pp`;
}

export function fmtSignedCents(v: number | null | undefined, digits = 1): string {
  if (v == null || !Number.isFinite(v)) return "—";
  const sign = v > 0 ? "+" : v < 0 ? "" : "";
  return `${sign}${v.toFixed(digits)}¢`;
}
