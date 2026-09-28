/** Developer-facing vocabulary coverage. Not a backend service. */

import { OPERATOR_FAMILIES } from "./ontology";
import type { CoverageReport, VocabularyCategory, VocabularyPhrase } from "./types";
import type { DiscoveryIndex } from "./search";

const EMPTY_CATS: Record<VocabularyCategory, number> = {
  population: 0,
  price_threshold: 0,
  path: 0,
  terminal: 0,
  time: 0,
  sport: 0,
  measurement: 0,
  mathematics: 0,
  point_in_time: 0,
  evidence: 0,
  other: 0,
};

export function vocabularyCoverage(index: DiscoveryIndex, phrases?: VocabularyPhrase[]): CoverageReport {
  const corpus = phrases ?? index.phrases;
  const uniquePhrases = new Set(corpus.map((p) => p.phrase.toLowerCase()));
  const byCategory = { ...EMPTY_CATS };
  for (const p of corpus) {
    byCategory[p.category] += 1;
  }
  const concepts = index.concepts;
  return {
    canonicalConcepts: concepts.length,
    operatorFamilies: OPERATOR_FAMILIES.length,
    searchablePhrases: uniquePhrases.size,
    compilerAcceptedPhrases: corpus.filter((p) => p.compilerAccepted).length,
    searchOnlyPhrases: corpus.filter((p) => !p.compilerAccepted).length,
    fields: index.fields.length,
    byCategory,
    implementedConcepts: concepts.filter((c) => c.constructibility === "IMPLEMENTED").length,
    configurableConcepts: concepts.filter((c) => c.constructibility === "CONFIGURABLE").length,
    registeredConcepts: concepts.filter((c) => c.constructibility === "REGISTERED").length,
    notConstructibleConcepts: concepts.filter((c) => c.constructibility === "NOT_CONSTRUCTIBLE").length,
  };
}

export function formatCoverageReport(report: CoverageReport): string {
  const cats = Object.entries(report.byCategory)
    .map(([k, v]) => `${k}: ${v}`)
    .join("\n");
  return [
    "VOCABULARY COVERAGE",
    "",
    `Canonical concepts: ${report.canonicalConcepts}`,
    `Operator families: ${report.operatorFamilies}`,
    `Searchable phrases: ${report.searchablePhrases}`,
    `Compiler-accepted phrases: ${report.compilerAcceptedPhrases}`,
    `Search-only phrases: ${report.searchOnlyPhrases}`,
    `Fields: ${report.fields}`,
    "",
    `Implemented: ${report.implementedConcepts}`,
    `Configurable: ${report.configurableConcepts}`,
    `Registered: ${report.registeredConcepts}`,
    `Not constructible: ${report.notConstructibleConcepts}`,
    "",
    cats,
  ].join("\n");
}
