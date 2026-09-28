/**
 * Finite-sample stats from the observed return vector.
 * Does not require an analysis envelope. CANDLE PATH ≠ FILL.
 */

import type { AnswerResult } from "./ResultsAnswer";
import { pathReturnCents, tradeRows } from "./finiteMath";
import { isLastTradePrint, LAST_TRADE_UNAVAILABLE } from "./lastTradeBasis";

const T975: Array<[number, number]> = [
  [1, 12.706204736432095],
  [2, 4.302652729749462],
  [3, 3.1824463052837076],
  [4, 2.7764451051977987],
  [5, 2.570581835636314],
  [6, 2.446911851144699],
  [7, 2.364624251778338],
  [8, 2.306004135204166],
  [9, 2.262157162798205],
  [10, 2.228138851986277],
  [12, 2.178812829667228],
  [15, 2.131449545559323],
  [20, 2.085963447265865],
  [25, 2.059538552753294],
  [30, 2.0422724563012373],
  [40, 2.021075390306273],
  [60, 2.000297822021512],
  [80, 1.990063421509341],
  [100, 1.9839715184496334],
  [120, 1.979930405265311],
  [1000, 1.9623414611334483],
];

export type ClusterBlock = {
  status: string;
  unit: string;
  n_units: number;
  n_observations: number;
  reason: string;
  mean?: { lower: number; upper: number; median: number };
};

export type DerivedObserved = {
  lastTrade: boolean;
  returns: number[];
  observed: Record<string, unknown> | null;
  observedEv: Record<string, unknown> | null;
  dependence: Record<string, unknown>;
  sequence: Record<string, unknown> | null;
  bootstrap: Record<string, unknown> | null;
  gameCluster: ClusterBlock;
  dateCluster: ClusterBlock;
  meanEntryCents: number | null;
};

function asRec(v: unknown): Record<string, unknown> | null {
  return v && typeof v === "object" ? (v as Record<string, unknown>) : null;
}

function asNum(v: unknown): number | null {
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

function e4(v: unknown): number | null {
  const n = asNum(v);
  if (n == null) return null;
  return Math.trunc(n);
}

function mean(xs: number[]): number | null {
  return xs.length ? xs.reduce((s, x) => s + x, 0) / xs.length : null;
}

function sampleStd(xs: number[]): number | null {
  if (xs.length < 2) return null;
  const m = mean(xs);
  if (m == null) return null;
  return Math.sqrt(xs.reduce((s, x) => s + (x - m) ** 2, 0) / (xs.length - 1));
}

function quantile(xs: number[], p: number): number | null {
  if (!xs.length) return null;
  const s = [...xs].sort((a, b) => a - b);
  if (s.length === 1) return s[0];
  const idx = p * (s.length - 1);
  const lo = Math.floor(idx);
  const hi = Math.ceil(idx);
  if (lo === hi) return s[lo];
  return s[lo] * (1 - (idx - lo)) + s[hi] * (idx - lo);
}

function tCritical975(df: number): number | null {
  if (df < 1) return null;
  if (df >= 10_000) return 1.959963984540054;
  let prevDf = T975[0][0];
  let prevT = T975[0][1];
  if (df <= prevDf) return prevT;
  for (const [nxtDf, nxtT] of T975.slice(1)) {
    if (df <= nxtDf) {
      const w = (df - prevDf) / (nxtDf - prevDf);
      return prevT + w * (nxtT - prevT);
    }
    prevDf = nxtDf;
    prevT = nxtT;
  }
  return 1.959963984540054;
}

function logGamma(z: number): number {
  const p = [
    676.5203681218851, -1259.1392167224028, 771.32342877765313, -176.61502916214059, 12.507343278686905,
    -0.13857109526572012, 9.9843695780195716e-6, 1.5056327351493116e-7,
  ];
  if (z < 0.5) {
    return Math.log(Math.PI / Math.sin(Math.PI * z)) - logGamma(1 - z);
  }
  let x = 0.99999999999980993;
  const y = z - 1;
  for (let i = 0; i < p.length; i++) x += p[i] / (y + i + 1);
  const t = y + p.length - 0.5;
  return 0.5 * Math.log(2 * Math.PI) + (y + 0.5) * Math.log(t) - t + Math.log(x);
}

function logBeta(a: number, b: number): number {
  return logGamma(a) + logGamma(b) - logGamma(a + b);
}

function betacf(a: number, b: number, x: number): number {
  const maxIter = 200;
  const eps = 3e-12;
  const fpmin = 1e-30;
  const qab = a + b;
  const qap = a + 1;
  const qam = a - 1;
  let c = 1;
  let d = 1 - (qab * x) / qap;
  if (Math.abs(d) < fpmin) d = fpmin;
  d = 1 / d;
  let h = d;
  for (let m = 1; m <= maxIter; m++) {
    const m2 = 2 * m;
    let aa = (m * (b - m) * x) / ((qam + m2) * (a + m2));
    d = 1 + aa * d;
    if (Math.abs(d) < fpmin) d = fpmin;
    c = 1 + aa / c;
    if (Math.abs(c) < fpmin) c = fpmin;
    d = 1 / d;
    h *= d * c;
    aa = (-(a + m) * (qab + m) * x) / ((a + m2) * (qap + m2));
    d = 1 + aa * d;
    if (Math.abs(d) < fpmin) d = fpmin;
    c = 1 + aa / c;
    if (Math.abs(c) < fpmin) c = fpmin;
    d = 1 / d;
    const delta = d * c;
    h *= delta;
    if (Math.abs(delta - 1) < eps) return h;
  }
  return h;
}

function regularizedIncompleteBeta(x: number, a: number, b: number): number {
  if (x <= 0) return 0;
  if (x >= 1) return 1;
  if (a <= 0 || b <= 0) return Number.NaN;
  const front = Math.exp(a * Math.log(x) + b * Math.log(1 - x) - logBeta(a, b));
  if (x < (a + 1) / (a + b + 2)) return (front * betacf(a, b, x)) / a;
  return 1 - (front * betacf(b, a, 1 - x)) / b;
}

function studentTTwoSidedP(tStat: number, df: number): number | null {
  if (df < 1 || !Number.isFinite(tStat)) return null;
  const x = df / (df + tStat * tStat);
  const p = regularizedIncompleteBeta(x, df / 2, 0.5);
  if (!Number.isFinite(p)) return null;
  return Math.min(1, Math.max(0, p));
}

export function tInterval(xs: number[]): Record<string, unknown> | null {
  const n = xs.length;
  if (n < 2) return null;
  const m = mean(xs);
  const s = sampleStd(xs);
  const tcrit = tCritical975(n - 1);
  if (m == null || s == null || tcrit == null) return null;
  const se = s / Math.sqrt(n);
  const tStat = se === 0 ? null : m / se;
  const pValue = tStat != null ? studentTTwoSidedP(tStat, n - 1) : null;
  const half = tcrit * se;
  return {
    estimate: m,
    lower: m - half,
    upper: m + half,
    confidence_level: 0.95,
    method: "student_t",
    n,
    std: s,
    standard_error: se,
    t_statistic: tStat,
    p_value: pValue,
    df: n - 1,
    null: "EV = 0",
    zero_inside_ci: m - half <= 0 && 0 <= m + half,
    t_critical: tcrit,
    assumption: "IID-like mean. Sports observations are not assumed independent.",
    source: "derived_from_return_vector",
  };
}

function maxDrawdown(pnls: number[]): number | null {
  if (!pnls.length) return null;
  let peak = 0;
  let equity = 0;
  let maxDd = 0;
  for (const pnl of pnls) {
    equity += pnl;
    if (equity > peak) peak = equity;
    maxDd = Math.max(maxDd, peak - equity);
  }
  return maxDd;
}

function clusterReadiness(nUnits: number, nObs: number, unit: string): ClusterBlock {
  if (nUnits < 2) {
    return {
      status: "UNAVAILABLE",
      unit,
      n_units: nUnits,
      n_observations: nObs,
      reason: `UNAVAILABLE · N < minimum (2 ${unit}s)`,
    };
  }
  if (nUnits === nObs) {
    return {
      status: "COINCIDENT",
      unit,
      n_units: nUnits,
      n_observations: nObs,
      reason: `1 observation per ${unit} · coincides with observation-level CI`,
    };
  }
  return {
    status: "DERIVED",
    unit,
    n_units: nUnits,
    n_observations: nObs,
    reason: `${nObs} observations from ${nUnits} ${unit}s · not ${nObs} independent experiments`,
  };
}

function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a += 0x6d2b79f5;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function percentile(xs: number[], p: number): number | null {
  if (!xs.length) return null;
  const s = [...xs].sort((a, b) => a - b);
  const idx = p * (s.length - 1);
  const lo = Math.floor(idx);
  const hi = Math.min(lo + 1, s.length - 1);
  const w = idx - lo;
  return s[lo] * (1 - w) + s[hi] * w;
}

function observationBootstrap(xs: number[]): Record<string, unknown> | null {
  if (xs.length < 2) return null;
  const iterations = 10_000;
  const rng = mulberry32(20260909);
  const n = xs.length;
  const means: number[] = [];
  const sharpes: number[] = [];
  const endings: number[] = [];
  const dds: number[] = [];
  for (let i = 0; i < iterations; i++) {
    const sample: number[] = [];
    for (let j = 0; j < n; j++) sample.push(xs[Math.floor(rng() * n)]!);
    const m = mean(sample);
    const s = sampleStd(sample);
    if (m != null) means.push(m);
    if (m != null && s != null && s !== 0) sharpes.push(m / s);
    endings.push(sample.reduce((a, b) => a + b, 0));
    dds.push(maxDrawdown(sample) ?? 0);
  }
  const share = means.filter((v) => v > 0).length / means.length;
  return {
    status: "DERIVED",
    label: "PERCENTILE BOOTSTRAP · derived from return vector · not a forecast",
    iterations,
    resampling_unit: "observation",
    mean: {
      lower: percentile(means, 0.025),
      upper: percentile(means, 0.975),
      median: percentile(means, 0.5),
    },
    sharpe: {
      lower: percentile(sharpes, 0.025),
      upper: percentile(sharpes, 0.975),
      median: percentile(sharpes, 0.5),
    },
    ending_pnl_cents: {
      lower: percentile(endings, 0.025),
      upper: percentile(endings, 0.975),
      median: percentile(endings, 0.5),
    },
    max_drawdown_cents: {
      lower: percentile(dds, 0.025),
      upper: percentile(dds, 0.975),
      median: percentile(dds, 0.5),
      p95: percentile(dds, 0.95),
    },
    share_means_positive: share,
    source: "derived_from_return_vector",
  };
}

function lastTradeDenied(result: AnswerResult): boolean {
  if (isLastTradePrint(result)) return true;
  const compile = result.compile as { question?: { entry_conditions?: Array<{ basis?: string }> } } | undefined;
  const bases = compile?.question?.entry_conditions?.map((e) => e.basis) ?? [];
  return bases.some((b) => b === "last_trade");
}

export function deriveObservedStats(result: AnswerResult): DerivedObserved {
  const denied = lastTradeDenied(result);
  const rows = tradeRows(result);
  const dated: Array<{ ts: string; pnl: number; game: string | null; date: string | null; entryE4: number | null }> = [];
  for (const row of rows) {
    const pnl = pathReturnCents(row);
    if (pnl == null) continue;
    const ts = String(row.entry_ts ?? "");
    dated.push({
      ts,
      pnl,
      game: row.internal_game_id != null && String(row.internal_game_id) ? String(row.internal_game_id) : null,
      date: ts ? ts.slice(0, 10) : null,
      entryE4: e4(row.entry_close ?? row.entry_price_e4),
    });
  }
  dated.sort((a, b) => a.ts.localeCompare(b.ts));
  const returns = dated.map((x) => x.pnl);
  const games = new Set(dated.map((x) => x.game).filter((g): g is string => Boolean(g)));
  const dates = new Set(dated.map((x) => x.date).filter((d): d is string => Boolean(d)));
  const tickers = new Set(
    rows.map((r) => (r.ticker != null && String(r.ticker) ? String(r.ticker) : null)).filter((t): t is string => Boolean(t)),
  );
  const entries = dated.map((x) => x.entryE4).filter((v): v is number => v != null);
  const meanEntryCents = entries.length ? entries.reduce((s, v) => s + v, 0) / entries.length / 100 : null;
  const gameCluster = clusterReadiness(games.size, returns.length, "game");
  const dateCluster = clusterReadiness(dates.size, returns.length, "date");

  if (denied || returns.length === 0) {
    return {
      lastTrade: denied,
      returns,
      observed: denied
        ? { status: "UNAVAILABLE", reason: `${LAST_TRADE_UNAVAILABLE}. No P&L / EV / Sharpe on this basis.` }
        : { status: "UNAVAILABLE", n: 0, reason: "No valid exit price. Missing exit is not zero return." },
      observedEv: null,
      dependence: {
        n_observations: rows.length || result.summary?.population_n || result.population?.count || 0,
        n_games: games.size || null,
        n_dates: dates.size || null,
        n_tickers: tickers.size || null,
        game_cluster: gameCluster,
        date_cluster: dateCluster,
      },
      sequence: null,
      bootstrap: null,
      gameCluster,
      dateCluster,
      meanEntryCents,
    };
  }

  const m = mean(returns);
  const s = sampleStd(returns);
  const evCi = tInterval(returns);
  const sharpe = m != null && s != null && s !== 0 ? m / s : null;
  const chrono = dated.map((x) => x.pnl);
  const dd = maxDrawdown(chrono);
  const observed: Record<string, unknown> = {
    status: "OBSERVED",
    label: "OBSERVED PATH RETURN · CANDLE PATH · NOT A FILL",
    n: returns.length,
    mean_cents: m,
    median_cents: quantile(returns, 0.5),
    std_cents: s,
    variance_cents: s != null ? s * s : null,
    min_cents: Math.min(...returns),
    max_cents: Math.max(...returns),
    quantiles: {
      p5: quantile(returns, 0.05),
      p25: quantile(returns, 0.25),
      p50: quantile(returns, 0.5),
      p75: quantile(returns, 0.75),
      p95: quantile(returns, 0.95),
    },
    sharpe_trade: sharpe,
    ev_ci: evCi,
    sum_cents: returns.reduce((a, b) => a + b, 0),
    source: "derived_from_return_vector",
  };
  let verdict = "EV interval not available.";
  if (evCi && m != null) {
    const lo = Number(evCi.lower);
    const hi = Number(evCi.upper);
    if (lo > 0) verdict = "POSITIVE EV · CI EXCLUDES ZERO";
    else if (hi < 0) verdict = "NEGATIVE EV · CI EXCLUDES ZERO";
    else if (m > 0) verdict = "POSITIVE POINT ESTIMATE · NOT STATISTICALLY DISTINGUISHABLE FROM ZERO";
    else if (m < 0) verdict = "NEGATIVE POINT ESTIMATE · NOT STATISTICALLY DISTINGUISHABLE FROM ZERO";
    else verdict = "ZERO POINT ESTIMATE · CI INCLUDES ZERO";
  }
  const observedEv: Record<string, unknown> = {
    status: "OBSERVED",
    label: "OBSERVED PATH EV / CONTRACT",
    formula: "E[exit_close − entry_close]",
    estimate_cents: m,
    ci95: evCi,
    method: "student_t",
    n: returns.length,
    significance: evCi
      ? {
          status: "DERIVED",
          verdict,
          estimate: m,
          standard_error: evCi.standard_error,
          t_statistic: evCi.t_statistic,
          p_value: evCi.p_value,
          df: evCi.df,
          null: "EV = 0",
          zero_inside_ci: evCi.zero_inside_ci,
          p_ev_gt_zero: { status: "NOT_COMPUTED", reason: "Not a posterior probability." },
        }
      : { status: "UNAVAILABLE", p_ev_gt_zero: { status: "NOT_COMPUTED" } },
  };
  return {
    lastTrade: false,
    returns,
    observed,
    observedEv,
    dependence: {
      n_observations: rows.length || returns.length || result.summary?.population_n || result.population?.count || 0,
      n_games: games.size || null,
      n_dates: dates.size || null,
      n_tickers: tickers.size || null,
      game_cluster: gameCluster,
      date_cluster: dateCluster,
      note: "N observations is not N independent experiments when games or dates repeat.",
    },
    sequence: {
      drawdown: { max_drawdown_cents: dd },
      cumulative_end_cents: chrono.reduce((a, b) => a + b, 0),
    },
    bootstrap: usableServerBootstrap(asRec(asRec(asRec(result.analysis)?.uncertainty)?.bootstrap))
      ? null
      : observationBootstrap(returns),
    gameCluster,
    dateCluster,
    meanEntryCents,
  };
}

/** True when a block already has a usable observed return vector. */
export function hasObservedVector(rec: Record<string, unknown> | null | undefined): boolean {
  if (!rec) return false;
  if (rec.status === "UNAVAILABLE") return false;
  if (typeof rec.n === "number") return rec.n > 0;
  if (typeof rec.mean_cents === "number" && Number.isFinite(rec.mean_cents)) return true;
  if (typeof rec.estimate_cents === "number" && Number.isFinite(rec.estimate_cents)) return true;
  return false;
}

export function pickObserved(
  analysis: Record<string, unknown> | null,
  derived: DerivedObserved,
): Record<string, unknown> | null {
  const rec = asRec(analysis?.observed_returns);
  if (hasObservedVector(rec)) return rec;
  if (rec?.status === "UNAVAILABLE" && String(rec.reason ?? "").includes("LAST TRADE")) return rec;
  return derived.observed;
}

export function pickObservedEv(
  analysis: Record<string, unknown> | null,
  derived: DerivedObserved,
): Record<string, unknown> | null {
  if (derived.lastTrade) {
    return { status: "UNAVAILABLE", reason: LAST_TRADE_UNAVAILABLE };
  }
  const rec = asRec(analysis?.observed_ev) ?? asRec(analysis?.observed_path_ev);
  if (rec?.status === "UNAVAILABLE") return rec;
  if (hasObservedVector(rec)) return rec;
  return derived.observedEv;
}

export function pickDependence(
  analysis: Record<string, unknown> | null,
  derived: DerivedObserved,
): Record<string, unknown> {
  const rec = asRec(analysis?.dependence);
  const n = typeof rec?.n_observations === "number" ? rec.n_observations : 0;
  if (rec && n > 0) return rec;
  return derived.dependence;
}

export function pickBootstrap(
  analysis: Record<string, unknown> | null,
  derived: DerivedObserved,
): Record<string, unknown> | null {
  if (derived.lastTrade) {
    return { status: "UNAVAILABLE", reason: LAST_TRADE_UNAVAILABLE };
  }
  const rec = asRec(asRec(analysis?.uncertainty)?.bootstrap);
  const mean = asRec(rec?.mean);
  if (rec && rec.status !== "UNAVAILABLE" && mean && typeof mean.lower === "number") return rec;
  return derived.bootstrap;
}

export function pickCluster(
  server: ClusterBlock | null | undefined,
  derived: ClusterBlock,
): ClusterBlock {
  if (!server) return derived;
  if (server.status === "COINCIDENT" || server.status === "DERIVED") return server;
  if (server.n_units > 0) return server;
  if (derived.n_units > 0 || derived.status !== "UNAVAILABLE") return derived;
  return server;
}

export function usableServerBootstrap(boot: Record<string, unknown> | null | undefined): boolean {
  const mean = asRec(boot?.mean);
  return Boolean(boot && boot.status !== "UNAVAILABLE" && mean && typeof mean.lower === "number");
}
