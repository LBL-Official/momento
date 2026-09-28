/**
 * MLB last-trade golden contract vs a live draft/result.
 * Measurement identity is dates + FT75 + exact lead +1 + REACH 40 LOSS.
 * Client-generated condition ids and season alias 2025-2026 vs 2025-26
 * change hashes without changing N.
 */

import type { WorkflowDraft, WorkflowUniverse } from "./workflow/types";

export const GOLDEN_MLB = {
  dateFrom: "2026-04-01",
  dateTo: "2026-09-08",
  entryCents: 75,
  entryE4: 7500,
  reachLossE4: 4000,
  scoreSide: "leading",
  exactDiffs: [1],
  n: 554,
  questionHash: "aaef0cbd185379f060a17077957ad50ee9cd2b4b25c339f1f3c1b25695060449",
  universeHash: "9484949819ca08afff3deb8adb171cb392812ba23412179de5b81f1023af78be",
} as const;

/** Warehouse MLB 2025-26 games.game_date min/max. Compiler keeps this span. */
export const MLB_WAREHOUSE_FROM = "2025-03-18";
export const MLB_WAREHOUSE_TO = "2026-09-04";

export function isMlbLastTradeUniverse(universe: WorkflowUniverse): boolean {
  const leagues = [...universe.leagues, ...universe.sports];
  const mlb = leagues.some((x) => x === "MLB" || x === "baseball");
  return mlb && universe.marketData.includes("last_trade");
}

function sameExactDiffs(got: number[] | undefined): boolean {
  const a = [...(got ?? [])].sort((x, y) => x - y);
  const b = [...GOLDEN_MLB.exactDiffs];
  return a.length === b.length && a.every((v, i) => v === b[i]);
}

export function goldenDiffsFromDraft(draft: WorkflowDraft): string[] {
  if (!isMlbLastTradeUniverse(draft.universe)) return [];
  const diffs: string[] = [];
  const u = draft.universe;
  if (u.dateFrom !== GOLDEN_MLB.dateFrom || u.dateTo !== GOLDEN_MLB.dateTo) {
    diffs.push(
      `dates ${u.dateFrom || "unbound"} → ${u.dateTo || "unbound"} (golden ${GOLDEN_MLB.dateFrom} → ${GOLDEN_MLB.dateTo})`,
    );
  }
  const entry = draft.entryConditions[0];
  if (!entry || entry.family !== "first_touch" || entry.priceCents !== GOLDEN_MLB.entryCents) {
    diffs.push(
      `entry ${entry?.family ?? "none"} ${entry?.priceCents ?? "—"}¢ (golden First Touch ${GOLDEN_MLB.entryCents}¢)`,
    );
  }
  const windows = entry?.periodWindows ?? [];
  if (entry?.period || windows.length) {
    const labels = windows.length
      ? windows.map((w) => w.period).filter(Boolean).join(",")
      : entry?.period;
    diffs.push(`period windows ${labels} (golden has none — T4–B7 is not the dated FT75 object)`);
  }
  const te = draft.teFilters;
  if (te?.scoreSide !== GOLDEN_MLB.scoreSide) {
    diffs.push(`TE side ${te?.scoreSide ?? "any"} (golden leading)`);
  }
  if (!sameExactDiffs(te?.exactDiffs)) {
    diffs.push(`exact lead ${(te?.exactDiffs ?? []).join(",") || "none"} (golden exact +1 only)`);
  }
  if (te?.customRange?.min != null || te?.customRange?.max != null) {
    diffs.push(
      `TE range ${te?.customRange?.min ?? "…"}–${te?.customRange?.max ?? "…"} (golden has no range; range ∪ exact is an OR-union)`,
    );
  }
  if (te?.absDiff && te.absDiff !== "any") {
    diffs.push(`TE |Δ| ${te.absDiff} (golden has none)`);
  }
  const reachLoss = draft.exitConditions.find(
    (e) => e.kind === "path" && e.family === "reach" && e.outcome === "loss",
  );
  if (reachLoss?.priceCents !== 40) {
    diffs.push(`LOSS reach ${reachLoss?.priceCents ?? "none"}¢ (golden 40¢)`);
  }
  const holdWin = draft.exitConditions.some(
    (e) => e.family === "hold_expiration_win" || (e.kind === "terminal" && e.outcome === "win"),
  );
  if (!holdWin) diffs.push("hold-to-expiration WIN missing (golden requires it)");
  return diffs;
}

type ResultLike = {
  summary?: { population_n?: number | null };
  hashes?: Record<string, string>;
  observation_basis?: string | null;
  provenance?: Record<string, unknown> | null;
  compile?: {
    question?: {
      universe?: {
        date_from?: string | null;
        date_to?: string | null;
        leagues?: string[];
        sports?: string[];
        market_data?: string[];
      };
      entry_conditions?: Array<{
        price_e4?: number;
        ordinal?: string;
        period?: string | null;
        period_windows?: Array<{ period?: string }>;
      }>;
      path_conditions?: Array<{ op?: string; price_e4?: number; outcome?: string }>;
    };
  };
  identity?: {
    te_scope?: {
      requested?: {
        score_side?: string;
        exact_diffs?: number[];
        custom_range?: { min?: number; max?: number };
        abs_diff?: string;
      } | null;
    };
    terminal_yes?: number;
    terminal_no?: number;
    terminal_missing?: number;
  } | null;
};

export function isMlbLastTradeResult(result: ResultLike): boolean {
  const basis = String(result.observation_basis || result.provenance?.price_basis || "");
  const md = String(result.provenance?.market_data || "");
  const leagues = [
    ...((result.compile?.question?.universe?.leagues ?? []) as string[]),
    ...((result.compile?.question?.universe?.sports ?? []) as string[]),
  ];
  const mlb = leagues.some((x) => x === "MLB" || x === "baseball");
  return mlb && (basis.includes("LAST_TRADE") || md.includes("last_trade"));
}

export function goldenDiffsFromResult(result: ResultLike): string[] {
  if (!isMlbLastTradeResult(result)) return [];
  const diffs: string[] = [];
  const uni = result.compile?.question?.universe ?? {};
  if (uni.date_from !== GOLDEN_MLB.dateFrom || uni.date_to !== GOLDEN_MLB.dateTo) {
    diffs.push(
      `dates ${uni.date_from || "unbound"} → ${uni.date_to || "unbound"} (golden ${GOLDEN_MLB.dateFrom} → ${GOLDEN_MLB.dateTo})`,
    );
  }
  const entry = result.compile?.question?.entry_conditions?.[0];
  if (!entry || entry.ordinal !== "FIRST_TOUCH" || entry.price_e4 !== GOLDEN_MLB.entryE4) {
    diffs.push(
      `entry ${entry?.ordinal ?? "none"} ${entry?.price_e4 ?? "—"} (golden FIRST_TOUCH 7500)`,
    );
  }
  const windows = entry?.period_windows ?? [];
  if (entry?.period || windows.length) {
    diffs.push(
      `period windows ${(windows.map((w) => w.period).filter(Boolean).join(",") || entry?.period) ?? "set"} (golden has none)`,
    );
  }
  const te = result.identity?.te_scope?.requested;
  if (te?.score_side !== GOLDEN_MLB.scoreSide) {
    diffs.push(`TE side ${te?.score_side ?? "any"} (golden leading)`);
  }
  if (!sameExactDiffs(te?.exact_diffs)) {
    diffs.push(`exact lead ${(te?.exact_diffs ?? []).join(",") || "none"} (golden exact +1 only)`);
  }
  if (te?.custom_range?.min != null || te?.custom_range?.max != null) {
    diffs.push(`TE range ${te?.custom_range?.min ?? "…"}–${te?.custom_range?.max ?? "…"} (golden has no range)`);
  }
  const reach = (result.compile?.question?.path_conditions ?? []).find(
    (p) => p.op === "REACH" && p.outcome === "loss",
  );
  if (reach?.price_e4 !== GOLDEN_MLB.reachLossE4) {
    diffs.push(`LOSS reach ${reach?.price_e4 ?? "none"} (golden 4000)`);
  }
  const n = result.summary?.population_n;
  if (n != null && n !== GOLDEN_MLB.n) {
    diffs.push(`N = ${n} (golden ${GOLDEN_MLB.n})`);
  }
  return diffs;
}

export function hashesMatchGolden(result: ResultLike): boolean {
  return result.hashes?.question_hash === GOLDEN_MLB.questionHash;
}

export function terminalMissingPhrase(provenance: Record<string, unknown> | null | undefined): string {
  const settle =
    provenance?.settlement && typeof provenance.settlement === "object"
      ? (provenance.settlement as Record<string, unknown>)
      : {};
  const overlay = settle.overlay_applied === true;
  const src = String(provenance?.terminal_source ?? settle.terminal_source ?? "");
  if (overlay || src.includes("official") || src.includes("first80") || src.includes("expiration_result")) {
    return "unmatched official W";
  }
  if (src.includes("kalshi_markets")) return "missing kalshi_markets.result";
  return "missing terminal settlement";
}
