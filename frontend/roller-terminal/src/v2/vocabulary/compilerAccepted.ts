/**
 * Phrases the deterministic vocabulary compiler actually accepts.
 * Copied from docs/research/roller_dashboard/research_vocabulary_v0.json
 * plus canonical ids / snake_case forms the compiler adds.
 *
 * SEARCH DISCOVERABILITY ≠ COMPILER ACCEPTANCE.
 */

import { normalizeSearchText } from "./normalize";
import type { VocabFile } from "./types";

const DOCUMENTED_SYNONYMS: Record<string, string[]> = {
  FIRST_PRICE_TOUCH: [
    "first touch",
    "first reached",
    "first hit",
    "first printed",
    "first 80",
    "first eighty",
    "FIRST80",
    "first price touch",
  ],
  SURVIVE: ["survived", "never stopped", "did not hit stop", "no stop", "path survival"],
  STOP_T40: ["stop", "stop loss", "hit 40", "touched 40", "T40"],
  TERMINAL_YES: ["won", "expired yes", "settled yes", "kalshi yes", "W"],
  TERMINAL_NO: ["lost", "expired no", "settled no"],
  ASKED_SIX: ["asked six", "asked-six", "mid-game default slices"],
  PERIOD_Q1: ["Q1", "first quarter", "1st quarter"],
  PERIOD_Q2: ["Q2", "second quarter", "2nd quarter"],
  PERIOD_Q3: ["Q3", "third quarter", "3rd quarter"],
  PERIOD_Q4: ["Q4", "fourth quarter", "4th quarter"],
  NCAAB_H1_2: ["H1_2", "late first half"],
  NCAAB_H2_1: ["H2_1", "early second half"],
  PRICE_E4: ["cents", "¢", "price"],
  CLOCK_REMAINING: [
    "clock remaining",
    "time remaining",
    "under five minutes",
    "less than 5 minutes",
  ],
  SCORE_MARGIN: ["score margin", "margin", "lead", "trail"],
  CANDLE_1M: ["one minute candle", "1m candle", "candle path"],
  OBSERVABLE_PATH_ONLY: ["observable path", "candle path only", "not fills"],
  OBSERVATION_TIME: ["observation", "at time t", "O_t"],
  FUNDAMENTAL_F_T: ["F_t", "fundamental", "fundamental probability"],
  BASIS: ["basis", "market fundamental basis", "market-fundamental basis"],
  RESIDUAL: ["residual", "response residual"],
  DELTA_MARKET: ["delta", "Δ", "market delta"],
  GAMMA_DISCRETE: ["gamma", "Γ", "discrete gamma"],
  THETA_OBSERVED: ["theta", "Θ", "observed theta"],
  PRICE_MOVE: ["price move", "moved", "dropped", "rallied"],
  BIG_MOVE: ["big move", "large move", "sharply", "unusually large", "more than normal"],
  LATE_GAME: ["late game", "late", "closing minutes"],
  FAVORITE: ["favorite", "fav"],
  WHAT_HAPPENED_NEXT: ["what happened next", "then what", "forward path", "after that"],
  EDGE: ["edge", "alpha", "inefficiency", "mispricing"],
};

function addPhrase(into: Map<string, Set<string>>, conceptId: string, phrase: string): void {
  const norm = normalizeSearchText(phrase);
  if (!norm) return;
  const set = into.get(norm) ?? new Set<string>();
  set.add(conceptId);
  into.set(norm, set);
}

export function buildCompilerPhraseIndex(vocab: VocabFile | null): Map<string, Set<string>> {
  const into = new Map<string, Set<string>>();
  const rows = vocab?.concepts?.length
    ? vocab.concepts
    : Object.entries(DOCUMENTED_SYNONYMS).map(([concept, synonyms]) => ({
        concept,
        synonyms,
      }));

  for (const row of rows) {
    const cid = row.concept;
    if (!cid) continue;
    addPhrase(into, cid, cid);
    addPhrase(into, cid, cid.replace(/_/g, " "));
    for (const syn of row.synonyms ?? []) {
      addPhrase(into, cid, syn);
    }
  }
  return into;
}

export function isCompilerAccepted(
  phrase: string,
  canonicalId: string,
  compilerIndex: Map<string, Set<string>>,
): boolean {
  const norm = normalizeSearchText(phrase);
  const ids = compilerIndex.get(norm);
  return Boolean(ids?.has(canonicalId));
}

export { DOCUMENTED_SYNONYMS };
