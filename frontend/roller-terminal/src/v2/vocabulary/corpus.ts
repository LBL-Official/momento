/**
 * Search corpus: documented aliases + grammar-generated notation.
 * Every phrase maps to a canonical family or implemented instance.
 * Generated phrases are NOT compiler-accepted unless they match vocab_v0.
 */

import { DOCUMENTED_SYNONYMS, isCompilerAccepted } from "./compilerAccepted";
import { GRID_CENTS, morphologicalForms, normalizeSearchText } from "./normalize";
import { CANONICAL_CONCEPTS } from "./ontology";
import type { PhraseSource, VocabularyCategory, VocabularyPhrase, VocabFile } from "./types";
import { buildCompilerPhraseIndex } from "./compilerAccepted";

type Seed = {
  phrase: string;
  canonicalId: string;
  category: VocabularyCategory;
  source: PhraseSource;
};

const CURATED: Seed[] = [
  // Population
  { phrase: "first80", canonicalId: "FIRST80", category: "population", source: "canonical" },
  { phrase: "first 80 population", canonicalId: "FIRST80", category: "population", source: "alias" },
  { phrase: "80 cent population", canonicalId: "FIRST80", category: "population", source: "alias" },
  { phrase: "games where price first reaches 80", canonicalId: "FIRST80", category: "population", source: "alias" },
  { phrase: "first occurrence at 80 cents", canonicalId: "FIRST80", category: "population", source: "alias" },
  { phrase: "initial 80 cent touch", canonicalId: "FIRST80", category: "population", source: "alias" },
  { phrase: "first qualifying 80 touch", canonicalId: "FIRST80", category: "population", source: "alias" },
  { phrase: "locked first80", canonicalId: "FIRST80", category: "population", source: "alias" },
  { phrase: "warehouse first80", canonicalId: "FIRST80", category: "population", source: "alias" },
  { phrase: "first tradable 80", canonicalId: "FIRST80", category: "population", source: "alias" },
  { phrase: "first 80 cent print", canonicalId: "FIRST80", category: "population", source: "alias" },
  { phrase: "initial threshold touch", canonicalId: "FIRST_PRICE_TOUCH", category: "population", source: "alias" },
  { phrase: "first price touch", canonicalId: "FIRST_PRICE_TOUCH", category: "population", source: "documented" },
  { phrase: "ncaab first80 p5", canonicalId: "NCAAB_FIRST80_P5", category: "population", source: "canonical" },
  { phrase: "p5 first 80", canonicalId: "NCAAB_FIRST80_P5", category: "population", source: "alias" },
  { phrase: "college first 80", canonicalId: "NCAAB_FIRST80_P5", category: "population", source: "alias" },

  // Price / threshold language (epistemic distinctions preserved)
  { phrase: "market price", canonicalId: "YES_BID_CLOSE", category: "price_threshold", source: "alias" },
  { phrase: "contract price", canonicalId: "YES_BID_CLOSE", category: "price_threshold", source: "alias" },
  { phrase: "yes price", canonicalId: "YES_BID_CLOSE", category: "price_threshold", source: "alias" },
  { phrase: "yes bid", canonicalId: "YES_BID_CLOSE", category: "price_threshold", source: "alias" },
  { phrase: "implied probability", canonicalId: "PRICE_E4", category: "price_threshold", source: "alias" },
  { phrase: "threshold", canonicalId: "PRICE_E4", category: "price_threshold", source: "alias" },
  { phrase: "barrier", canonicalId: "T40", category: "price_threshold", source: "alias" },
  { phrase: "forty cent barrier", canonicalId: "T40", category: "price_threshold", source: "alias" },
  { phrase: "80 cent threshold", canonicalId: "FIRST80", category: "price_threshold", source: "alias" },
  { phrase: "print", canonicalId: "YES_BID_CLOSE", category: "price_threshold", source: "alias" },
  { phrase: "quote", canonicalId: "YES_BID_CLOSE", category: "price_threshold", source: "alias" },
  { phrase: "level", canonicalId: "PRICE_E4", category: "price_threshold", source: "alias" },
  { phrase: "e4 integer", canonicalId: "PRICE_E4", category: "price_threshold", source: "notation" },
  { phrase: "trade print", canonicalId: "CANDLE_1M", category: "price_threshold", source: "alias" },
  { phrase: "candle observation", canonicalId: "CANDLE_1M", category: "price_threshold", source: "alias" },
  { phrase: "fair value", canonicalId: "FUNDAMENTAL_F_T", category: "price_threshold", source: "alias" },

  // Path
  { phrase: "price path", canonicalId: "OBSERVABLE_PATH_ONLY", category: "path", source: "alias" },
  { phrase: "trajectory", canonicalId: "OBSERVABLE_PATH_ONLY", category: "path", source: "alias" },
  { phrase: "after entry", canonicalId: "WHAT_HAPPENED_NEXT", category: "path", source: "alias" },
  { phrase: "subsequent movement", canonicalId: "WHAT_HAPPENED_NEXT", category: "path", source: "alias" },
  { phrase: "later movement", canonicalId: "WHAT_HAPPENED_NEXT", category: "path", source: "alias" },
  { phrase: "path response", canonicalId: "WHAT_HAPPENED_NEXT", category: "path", source: "alias" },
  { phrase: "drawdown", canonicalId: "MAX_ADVERSE_PATH", category: "path", source: "alias" },
  { phrase: "decline", canonicalId: "MAX_ADVERSE_PATH", category: "path", source: "alias" },
  { phrase: "path survival", canonicalId: "SURVIVE", category: "path", source: "documented" },
  { phrase: "barrier survival", canonicalId: "BARRIER_SURVIVAL", category: "path", source: "alias" },
  { phrase: "ever reaches", canonicalId: "EVER_TOUCH", category: "path", source: "alias" },
  { phrase: "never reaches", canonicalId: "NEVER_TOUCH", category: "path", source: "alias" },
  { phrase: "returns to the entry level", canonicalId: "RECOVER_TO", category: "path", source: "alias" },
  { phrase: "mean reverts upward", canonicalId: "REVERSAL", category: "path", source: "alias" },
  { phrase: "mean reverts downward", canonicalId: "REVERSAL", category: "path", source: "alias" },
  { phrase: "forward path", canonicalId: "WHAT_HAPPENED_NEXT", category: "path", source: "documented" },

  // Terminal
  { phrase: "terminal", canonicalId: "SETTLEMENT", category: "terminal", source: "alias" },
  { phrase: "final outcome", canonicalId: "SETTLEMENT", category: "terminal", source: "alias" },
  { phrase: "end result", canonicalId: "SETTLEMENT", category: "terminal", source: "alias" },
  { phrase: "final state", canonicalId: "SETTLEMENT", category: "terminal", source: "alias" },
  { phrase: "contract result", canonicalId: "SETTLEMENT", category: "terminal", source: "alias" },
  { phrase: "resolution", canonicalId: "SETTLEMENT", category: "terminal", source: "alias" },
  { phrase: "settlement", canonicalId: "SETTLEMENT", category: "terminal", source: "alias" },
  { phrase: "settles yes", canonicalId: "TERMINAL_YES", category: "terminal", source: "alias" },
  { phrase: "settles no", canonicalId: "TERMINAL_NO", category: "terminal", source: "alias" },
  { phrase: "resolved yes", canonicalId: "TERMINAL_YES", category: "terminal", source: "alias" },
  { phrase: "resolved no", canonicalId: "TERMINAL_NO", category: "terminal", source: "alias" },
  { phrase: "contract settles yes", canonicalId: "TERMINAL_YES", category: "terminal", source: "alias" },
  { phrase: "final result", canonicalId: "SETTLEMENT", category: "terminal", source: "alias" },

  // Time
  { phrase: "early game", canonicalId: "PERIOD_Q1", category: "time", source: "alias" },
  { phrase: "mid game", canonicalId: "ASKED_SIX", category: "time", source: "alias" },
  { phrase: "game clock", canonicalId: "CLOCK_REMAINING", category: "time", source: "alias" },
  { phrase: "overtime", canonicalId: "OT", category: "time", source: "alias" },
  { phrase: "quarter 3", canonicalId: "PERIOD_Q3", category: "time", source: "notation" },
  { phrase: "late first half", canonicalId: "NCAAB_H1_2", category: "time", source: "documented" },
  { phrase: "early second half", canonicalId: "NCAAB_H2_1", category: "time", source: "documented" },
  { phrase: "asked six", canonicalId: "ASKED_SIX", category: "time", source: "documented" },
  { phrase: "immediately", canonicalId: "TIME_HORIZON", category: "time", source: "alias" },
  { phrase: "eventually", canonicalId: "TIME_HORIZON", category: "time", source: "alias" },
  { phrase: "minutes later", canonicalId: "TIME_HORIZON", category: "time", source: "alias" },
  { phrase: "within five minutes", canonicalId: "CLOCK_REMAINING", category: "time", source: "documented" },

  // Sports
  { phrase: "basketball", canonicalId: "NBA", category: "sport", source: "alias" },
  { phrase: "pro basketball", canonicalId: "NBA", category: "sport", source: "alias" },
  { phrase: "women's basketball", canonicalId: "WNBA", category: "sport", source: "alias" },
  { phrase: "college basketball", canonicalId: "NCAAB", category: "sport", source: "alias" },
  { phrase: "power five", canonicalId: "P5", category: "sport", source: "alias" },
  { phrase: "major conference", canonicalId: "P5", category: "sport", source: "alias" },
  { phrase: "baseball", canonicalId: "MLB", category: "sport", source: "alias" },
  { phrase: "bball1", canonicalId: "BBALL1", category: "sport", source: "canonical" },

  // Measurements
  { phrase: "proportion", canonicalId: "EMPIRICAL_PROPORTION", category: "measurement", source: "alias" },
  { phrase: "rate", canonicalId: "EMPIRICAL_PROPORTION", category: "measurement", source: "alias" },
  { phrase: "frequency", canonicalId: "EMPIRICAL_PROPORTION", category: "measurement", source: "alias" },
  { phrase: "percentage", canonicalId: "EMPIRICAL_PROPORTION", category: "measurement", source: "alias" },
  { phrase: "path proportion", canonicalId: "t40_rate", category: "measurement", source: "alias" },
  { phrase: "terminal proportion", canonicalId: "kalshi_yes_rate", category: "measurement", source: "alias" },
  { phrase: "sample size", canonicalId: "FINITE_SAMPLE", category: "measurement", source: "alias" },
  { phrase: "population size", canonicalId: "FINITE_SAMPLE", category: "measurement", source: "alias" },
  { phrase: "count", canonicalId: "FINITE_SAMPLE", category: "measurement", source: "alias" },
  { phrase: "volatility", canonicalId: "MAX_ADVERSE_PATH", category: "measurement", source: "alias" },
  { phrase: "dispersion", canonicalId: "MAX_ADVERSE_PATH", category: "measurement", source: "alias" },
  { phrase: "market response", canonicalId: "RESIDUAL", category: "measurement", source: "alias" },
  { phrase: "t40 rate", canonicalId: "t40_rate", category: "measurement", source: "notation" },
  { phrase: "kalshi yes rate", canonicalId: "kalshi_yes_rate", category: "measurement", source: "alias" },

  // Mathematics
  { phrase: "population", canonicalId: "FIRST80", category: "mathematics", source: "alias" },
  { phrase: "sample", canonicalId: "FINITE_SAMPLE", category: "mathematics", source: "alias" },
  { phrase: "universe", canonicalId: "BBALL1", category: "mathematics", source: "alias" },
  { phrase: "subset", canonicalId: "CONDITIONAL", category: "mathematics", source: "alias" },
  { phrase: "condition", canonicalId: "CONDITIONAL", category: "mathematics", source: "alias" },
  { phrase: "filter", canonicalId: "CONDITIONAL", category: "mathematics", source: "alias" },
  { phrase: "slice", canonicalId: "CONDITIONAL", category: "mathematics", source: "alias" },
  { phrase: "partition", canonicalId: "STATE_SPACE", category: "mathematics", source: "alias" },
  { phrase: "state space", canonicalId: "STATE_SPACE", category: "mathematics", source: "alias" },
  { phrase: "joint", canonicalId: "JOINT", category: "mathematics", source: "alias" },
  { phrase: "marginal", canonicalId: "MARGINAL", category: "mathematics", source: "alias" },
  { phrase: "conditional", canonicalId: "CONDITIONAL", category: "mathematics", source: "alias" },
  { phrase: "intersection", canonicalId: "JOINT", category: "mathematics", source: "alias" },
  { phrase: "denominator", canonicalId: "FINITE_SAMPLE", category: "mathematics", source: "alias" },
  { phrase: "numerator", canonicalId: "EMPIRICAL_PROPORTION", category: "mathematics", source: "alias" },
  { phrase: "empirical distribution", canonicalId: "EMPIRICAL_PROPORTION", category: "mathematics", source: "alias" },
  { phrase: "finite sample", canonicalId: "FINITE_SAMPLE", category: "mathematics", source: "alias" },
  { phrase: "observation", canonicalId: "OBSERVATION_TIME", category: "mathematics", source: "documented" },

  // Point-in-time
  { phrase: "as of", canonicalId: "POINT_IN_TIME", category: "point_in_time", source: "alias" },
  { phrase: "what was known", canonicalId: "POINT_IN_TIME", category: "point_in_time", source: "alias" },
  { phrase: "what was known at the time", canonicalId: "POINT_IN_TIME", category: "point_in_time", source: "alias" },
  { phrase: "information available at the time", canonicalId: "POINT_IN_TIME", category: "point_in_time", source: "alias" },
  { phrase: "historical information set", canonicalId: "AVAILABLE_INFORMATION", category: "point_in_time", source: "alias" },
  { phrase: "historical information available then", canonicalId: "POINT_IN_TIME", category: "point_in_time", source: "alias" },
  { phrase: "point in time", canonicalId: "POINT_IN_TIME", category: "point_in_time", source: "alias" },
  { phrase: "before this timestamp", canonicalId: "POINT_IN_TIME", category: "point_in_time", source: "alias" },
  { phrase: "available then", canonicalId: "POINT_IN_TIME", category: "point_in_time", source: "alias" },
  { phrase: "known then", canonicalId: "POINT_IN_TIME", category: "point_in_time", source: "alias" },
  { phrase: "lookahead bias", canonicalId: "LOOKAHEAD_BIAS", category: "point_in_time", source: "alias" },
  { phrase: "future information", canonicalId: "LOOKAHEAD_BIAS", category: "point_in_time", source: "alias" },
  { phrase: "historical snapshot", canonicalId: "POINT_IN_TIME", category: "point_in_time", source: "alias" },
  { phrase: "I(t)", canonicalId: "POINT_IN_TIME", category: "point_in_time", source: "canonical" },
  { phrase: "half open information", canonicalId: "POINT_IN_TIME", category: "point_in_time", source: "alias" },

  // Evidence
  { phrase: "evidence", canonicalId: "PROVENANCE", category: "evidence", source: "alias" },
  { phrase: "source", canonicalId: "ARTIFACT", category: "evidence", source: "alias" },
  { phrase: "data source", canonicalId: "ARTIFACT", category: "evidence", source: "alias" },
  { phrase: "artifact", canonicalId: "ARTIFACT", category: "evidence", source: "canonical" },
  { phrase: "provenance", canonicalId: "PROVENANCE", category: "evidence", source: "canonical" },
  { phrase: "lineage", canonicalId: "PROVENANCE", category: "evidence", source: "alias" },
  { phrase: "fingerprint", canonicalId: "PROVENANCE", category: "evidence", source: "alias" },
  { phrase: "dataset", canonicalId: "ARTIFACT", category: "evidence", source: "alias" },
  { phrase: "validation", canonicalId: "VALIDATION", category: "evidence", source: "canonical" },
  { phrase: "audit", canonicalId: "PROVENANCE", category: "evidence", source: "alias" },
  { phrase: "definition version", canonicalId: "DEFINITION_VERSION", category: "evidence", source: "canonical" },
  { phrase: "warehouse freeze", canonicalId: "DEFINITION_VERSION", category: "evidence", source: "alias" },
  { phrase: "canonical data", canonicalId: "ARTIFACT", category: "evidence", source: "alias" },
  { phrase: "derived data", canonicalId: "ARTIFACT", category: "evidence", source: "alias" },

  // Other
  { phrase: "then", canonicalId: "SEQUENCE", category: "other", source: "alias" },
  { phrase: "after", canonicalId: "SEQUENCE", category: "other", source: "alias" },
  { phrase: "before", canonicalId: "SEQUENCE", category: "other", source: "alias" },
  { phrase: "following", canonicalId: "SEQUENCE", category: "other", source: "alias" },
  { phrase: "subsequent to", canonicalId: "SEQUENCE", category: "other", source: "alias" },
  { phrase: "cross", canonicalId: "CROSS", category: "other", source: "alias" },
  { phrase: "break", canonicalId: "CROSS", category: "other", source: "alias" },
  { phrase: "breach", canonicalId: "CROSS", category: "other", source: "alias" },
  { phrase: "above", canonicalId: "PRICE_STATE", category: "other", source: "alias" },
  { phrase: "below", canonicalId: "PRICE_STATE", category: "other", source: "alias" },
];

const ORDINALS: Array<{ word: string; n: number }> = [
  { word: "first", n: 1 },
  { word: "initial", n: 1 },
  { word: "second", n: 2 },
  { word: "third", n: 3 },
  { word: "fourth", n: 4 },
  { word: "fifth", n: 5 },
  { word: "sixth", n: 6 },
  { word: "seventh", n: 7 },
  { word: "eighth", n: 8 },
  { word: "ninth", n: 9 },
  { word: "tenth", n: 10 },
];

function ordinalCanonical(ordinal: number, cents: number): string {
  if (ordinal === 1 && cents === 80) return "FIRST80";
  if (ordinal === 1 && cents === 83) return "FIRST83";
  if (ordinal === 1) return "ORDINAL_TOUCH";
  return "ORDINAL_TOUCH";
}

function generateGrammarSeeds(): Seed[] {
  const out: Seed[] = [];
  const events = ["touch", "hit", "reach", "print"];
  for (const { word, n } of ORDINALS) {
    for (const cents of GRID_CENTS) {
      const id = ordinalCanonical(n, cents);
      const templates =
        n <= 3
          ? [
              `${word} ${cents}`,
              `${word} ${cents}¢`,
              `${word} ${cents} cents`,
              `${word} touch ${cents}`,
              `${word} hit ${cents}`,
              `${word} reaches ${cents}`,
              `${word} time at ${cents}`,
              `${word} occurrence of ${cents}`,
              `${word} touch of ${cents}`,
            ]
          : [`${word} ${cents}`, `${word} touch ${cents}`, `${word} ${cents} cents`];
      if (n === 1) {
        templates.push(`initial touch of ${cents}`, `first ${cents} cent print`);
      }
      if (n === 2) {
        templates.push(`returns to ${cents} for the second time`, `second visit to ${cents}`);
      }
      for (const t of templates) {
        out.push({ phrase: t, canonicalId: id, category: "population", source: "notation" });
      }
      for (const ev of n <= 2 ? events : []) {
        out.push({
          phrase: `${word} ${ev} ${cents}c`,
          canonicalId: id,
          category: "population",
          source: "notation",
        });
      }
    }
  }

  for (const cents of GRID_CENTS) {
    const dropId = cents === 40 ? "T40" : "DROP_TO";
    const everId = cents === 40 ? "T40" : "EVER_TOUCH";
    const neverId = cents === 40 ? "SURVIVE" : "NEVER_TOUCH";
    out.push(
      { phrase: `drops to ${cents}`, canonicalId: dropId, category: "path", source: "notation" },
      { phrase: `falls to ${cents}`, canonicalId: dropId, category: "path", source: "notation" },
      { phrase: `declines to ${cents}`, canonicalId: dropId, category: "path", source: "notation" },
      { phrase: `drops to ${cents} cents`, canonicalId: dropId, category: "path", source: "notation" },
      { phrase: `bounces to ${cents}`, canonicalId: "BOUNCE_TO", category: "path", source: "notation" },
      { phrase: `rebounds to ${cents}`, canonicalId: "BOUNCE_TO", category: "path", source: "notation" },
      { phrase: `rallies back to ${cents}`, canonicalId: "BOUNCE_TO", category: "path", source: "notation" },
      { phrase: `recovers to ${cents}`, canonicalId: "RECOVER_TO", category: "path", source: "notation" },
      { phrase: `claws back to ${cents}`, canonicalId: "RECOVER_TO", category: "path", source: "notation" },
      { phrase: `gets back to ${cents}`, canonicalId: "RECOVER_TO", category: "path", source: "notation" },
      { phrase: `ever reaches ${cents}`, canonicalId: everId, category: "path", source: "notation" },
      { phrase: `ever hits ${cents}`, canonicalId: everId, category: "path", source: "notation" },
      { phrase: `ever touches ${cents}`, canonicalId: everId, category: "path", source: "notation" },
      { phrase: `never reaches ${cents}`, canonicalId: neverId, category: "path", source: "notation" },
      { phrase: `never touches ${cents}`, canonicalId: neverId, category: "path", source: "notation" },
      { phrase: `survives above ${cents}`, canonicalId: neverId, category: "path", source: "notation" },
      { phrase: `crosses above ${cents}`, canonicalId: "CROSS", category: "price_threshold", source: "notation" },
      { phrase: `breaks above ${cents}`, canonicalId: "CROSS", category: "price_threshold", source: "notation" },
      { phrase: `crosses below ${cents}`, canonicalId: "CROSS", category: "price_threshold", source: "notation" },
      { phrase: `falls through ${cents}`, canonicalId: "CROSS", category: "price_threshold", source: "notation" },
      { phrase: `above ${cents}`, canonicalId: "PRICE_STATE", category: "price_threshold", source: "notation" },
      { phrase: `below ${cents}`, canonicalId: "PRICE_STATE", category: "price_threshold", source: "notation" },
      { phrase: `over ${cents}`, canonicalId: "PRICE_STATE", category: "price_threshold", source: "notation" },
      { phrase: `under ${cents}`, canonicalId: "PRICE_STATE", category: "price_threshold", source: "notation" },
      { phrase: `at least ${cents}`, canonicalId: "PRICE_STATE", category: "price_threshold", source: "notation" },
    );
  }

  out.push(
    { phrase: "reverts up", canonicalId: "REVERSAL", category: "path", source: "alias" },
    { phrase: "moves back up", canonicalId: "REVERSAL", category: "path", source: "alias" },
    { phrase: "rebounds", canonicalId: "REVERSAL", category: "path", source: "alias" },
    { phrase: "reverts down", canonicalId: "REVERSAL", category: "path", source: "alias" },
    { phrase: "falls back", canonicalId: "REVERSAL", category: "path", source: "alias" },
    { phrase: "retraces lower", canonicalId: "REVERSAL", category: "path", source: "alias" },
    { phrase: "touches 80 then falls to 40", canonicalId: "SEQUENCE", category: "path", source: "alias" },
    { phrase: "hits 80 then falls to 40", canonicalId: "SEQUENCE", category: "path", source: "alias" },
    { phrase: "first reaches 80 then recovers", canonicalId: "SEQUENCE", category: "path", source: "alias" },
    { phrase: "falls to 40 before recovering to 80", canonicalId: "SEQUENCE", category: "path", source: "alias" },
  );

  return out;
}

function documentedSeeds(): Seed[] {
  const out: Seed[] = [];
  for (const [cid, syns] of Object.entries(DOCUMENTED_SYNONYMS)) {
    const concept = CANONICAL_CONCEPTS.find((x) => x.id === cid);
    const category = concept?.category ?? "other";
    out.push({ phrase: cid, canonicalId: cid, category, source: "canonical" });
    out.push({ phrase: cid.replace(/_/g, " "), canonicalId: cid, category, source: "notation" });
    for (const s of syns) {
      out.push({ phrase: s, canonicalId: cid, category, source: "documented" });
    }
  }
  for (const concept of CANONICAL_CONCEPTS) {
    out.push({
      phrase: concept.id,
      canonicalId: concept.id,
      category: concept.category,
      source: "canonical",
    });
    out.push({
      phrase: concept.displayName,
      canonicalId: concept.id,
      category: concept.category,
      source: "canonical",
    });
  }
  return out;
}

export function buildVocabularyCorpus(vocab: VocabFile | null = null): VocabularyPhrase[] {
  const compiler = buildCompilerPhraseIndex(vocab);
  const bag = new Map<string, VocabularyPhrase>();

  const push = (seed: Seed) => {
    for (const form of morphologicalForms(seed.phrase)) {
      const norm = normalizeSearchText(form);
      if (!norm || norm.length < 2) continue;
      const key = `${norm}::${seed.canonicalId}`;
      if (bag.has(key)) continue;
      bag.set(key, {
        phrase: form,
        canonicalId: seed.canonicalId,
        category: seed.category,
        source: form === seed.phrase ? seed.source : "morphology",
        compilerAccepted: isCompilerAccepted(form, seed.canonicalId, compiler),
      });
    }
  };

  for (const s of [...documentedSeeds(), ...CURATED, ...generateGrammarSeeds()]) {
    push(s);
  }

  if (vocab?.concepts) {
    for (const row of vocab.concepts) {
      const concept = CANONICAL_CONCEPTS.find((x) => x.id === row.concept);
      const category = concept?.category ?? "other";
      for (const syn of row.synonyms ?? []) {
        push({ phrase: syn, canonicalId: row.concept, category, source: "documented" });
      }
    }
  }

  return [...bag.values()].sort((a, b) => a.canonicalId.localeCompare(b.canonicalId) || a.phrase.localeCompare(b.phrase));
}

export function phrasesForConcept(corpus: VocabularyPhrase[], id: string): string[] {
  return corpus.filter((p) => p.canonicalId === id).map((p) => p.phrase);
}
