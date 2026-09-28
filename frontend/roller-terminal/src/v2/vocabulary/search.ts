/** Grammar-first discovery search. SEARCH ≠ COMPILER. No opaque fuzzy matching. */

import { isCompilerAccepted } from "./compilerAccepted";
import { buildCompilerPhraseIndex } from "./compilerAccepted";
import { buildVocabularyCorpus } from "./corpus";
import { DATA_FIELDS } from "./dataDictionary";
import { parsePhenomenon } from "./grammar";
import { normalizeSearchText, phraseBoundaryMatch, tokensOf } from "./normalize";
import { breakdownFor, CANONICAL_CONCEPTS, CONCEPT_BY_ID } from "./ontology";
import type {
  CanonicalConcept,
  DataField,
  GroupedSearch,
  ParsedPhenomenon,
  RecognizedConcept,
  SearchGroup,
  SearchHit,
  VocabFile,
} from "./types";

export type DiscoveryIndex = {
  concepts: CanonicalConcept[];
  byId: Record<string, CanonicalConcept>;
  phrases: ReturnType<typeof buildVocabularyCorpus>;
  fields: DataField[];
  compiler: ReturnType<typeof buildCompilerPhraseIndex>;
};

export function buildDiscoveryIndex(vocab: VocabFile | null = null): DiscoveryIndex {
  const phrases = buildVocabularyCorpus(vocab);
  return {
    concepts: CANONICAL_CONCEPTS,
    byId: CONCEPT_BY_ID,
    phrases,
    fields: DATA_FIELDS,
    compiler: buildCompilerPhraseIndex(vocab),
  };
}

function conceptFromClause(index: DiscoveryIndex, expressionId: string, familyId: string): CanonicalConcept | undefined {
  return index.byId[expressionId] ?? index.byId[familyId];
}

function scoreConcept(index: DiscoveryIndex, concept: CanonicalConcept, needle: string, tokens: string[]): SearchHit | null {
  const idN = normalizeSearchText(concept.id);
  const nameN = normalizeSearchText(concept.displayName);
  let score = 0;
  let kind: SearchHit["kind"] = "prefix_token";
  let matchedPhrase: string | undefined;

  if (idN === needle || nameN === needle) {
    score = 100;
    kind = "exact_concept";
    matchedPhrase = concept.id;
  }

  const aliases = index.phrases.filter((p) => p.canonicalId === concept.id);
  for (const a of aliases) {
    const an = normalizeSearchText(a.phrase);
    if (an === needle) {
      if (score < 80) {
        score = 80;
        kind = "exact_alias";
        matchedPhrase = a.phrase;
      }
    } else if (phraseBoundaryMatch(an, needle) || phraseBoundaryMatch(needle, an)) {
      if (score < 50) {
        score = 50;
        kind = "exact_alias";
        matchedPhrase = a.phrase;
      }
    }
  }

  if (score < 40 && (idN.startsWith(needle) || nameN.startsWith(needle) || idN.includes(needle))) {
    score = 40;
    kind = "prefix_token";
  }

  if (score < 24) {
    const hay = tokensOf(`${idN} ${nameN} ${normalizeSearchText(concept.definition)}`);
    const hit = tokens.filter((t) => t.length > 1 && hay.includes(t)).length;
    if (hit > 0) {
      score = 10 + hit * 4;
      kind = "prefix_token";
    }
  }

  if (score < 16) {
    for (const rel of concept.relatedConcepts) {
      if (normalizeSearchText(rel) === needle || tokens.includes(normalizeSearchText(rel))) {
        score = 16;
        kind = "related";
        matchedPhrase = rel;
        break;
      }
    }
  }

  if (score <= 0) return null;
  if (concept.constructibility === "REGISTERED" || concept.constructibility === "NOT_CONSTRUCTIBLE") {
    if (kind !== "exact_concept" && kind !== "exact_alias") kind = kind === "related" ? "related" : "registered";
  }
  return { id: concept.id, kind, score, matchedPhrase, concept };
}

function scoreField(field: DataField, needle: string, tokens: string[]): SearchHit | null {
  const names = [field.displayName, field.canonicalField, ...field.aliases].map(normalizeSearchText);
  let score = 0;
  let matchedPhrase: string | undefined;
  for (const n of names) {
    if (n === needle) {
      score = 72;
      matchedPhrase = n;
      break;
    }
    if (n.includes(needle) || needle.includes(n)) {
      score = Math.max(score, 36);
      matchedPhrase = n;
    }
  }
  for (const v of field.knownValues) {
    const vn = normalizeSearchText(v.value);
    if (vn === needle || tokens.includes(vn)) {
      score = Math.max(score, 68);
      matchedPhrase = v.value;
    }
  }
  if (score <= 0) return null;
  return { id: `field:${field.id}`, kind: "field_value", score, matchedPhrase, field };
}

export function searchDiscovery(index: DiscoveryIndex, query: string): GroupedSearch {
  const parsed = parsePhenomenon(query);
  const needle = parsed.normalized;
  const tokens = tokensOf(needle);

  if (!needle) {
    const implemented = index.concepts.filter((c) => c.constructibility === "IMPLEMENTED").slice(0, 24);
    const hits: SearchHit[] = implemented.map((concept, i) => ({
      id: concept.id,
      kind: "exact_concept" as const,
      score: 90 - i,
      concept,
    }));
    return {
      query,
      normalized: "",
      recognized: [],
      unknown: false,
      groups: [{ id: "exact", label: "Implemented concepts", hits }],
      hits,
    };
  }

  const conceptHits = new Map<string, SearchHit>();
  for (const concept of index.concepts) {
    const hit = scoreConcept(index, concept, needle, tokens);
    if (hit) conceptHits.set(hit.id, hit);
  }

  const recognized: RecognizedConcept[] = [];
  for (const clause of parsed.clauses) {
    const concept = conceptFromClause(index, clause.expressionId, clause.familyId);
    recognized.push({
      id: clause.expressionId,
      displayName: clause.displayName,
      matchedPhrase: clause.matchedPhrase,
      constructibility: clause.constructibility,
      compilerAccepted: isCompilerAccepted(clause.matchedPhrase, concept?.id ?? clause.expressionId, index.compiler),
    });
    const base = concept ?? index.byId[clause.familyId];
    if (base) {
      const prev = conceptHits.get(base.id);
      const score = 110 + (clause.constructibility === "IMPLEMENTED" ? 20 : 0);
      if (!prev || prev.score < score) {
        conceptHits.set(base.id, {
          id: base.id,
          kind: "exact_concept",
          score,
          matchedPhrase: clause.matchedPhrase,
          concept: base,
        });
      }
    }
    if (index.byId[clause.expressionId] && clause.expressionId !== clause.familyId) {
      const inst = index.byId[clause.expressionId];
      conceptHits.set(inst.id, {
        id: inst.id,
        kind: "exact_concept",
        score: 130,
        matchedPhrase: clause.matchedPhrase,
        concept: inst,
      });
    }
    for (const bind of clause.bindsToImplemented) {
      const rel = index.byId[bind];
      if (rel && !conceptHits.has(rel.id)) {
        conceptHits.set(rel.id, {
          id: rel.id,
          kind: "related",
          score: 22,
          matchedPhrase: clause.expressionId,
          concept: rel,
        });
      }
    }
  }

  const fieldHits: SearchHit[] = [];
  for (const field of index.fields) {
    const hit = scoreField(field, needle, tokens);
    if (hit) fieldHits.push(hit);
  }

  const all = [...conceptHits.values()].sort((a, b) => b.score - a.score);
  const measurements = all.filter((h) => h.concept?.conceptType === "measurement");
  const registered = all.filter(
    (h) =>
      h.concept &&
      (h.concept.constructibility === "REGISTERED" || h.concept.constructibility === "NOT_CONSTRUCTIBLE") &&
      h.kind !== "exact_concept",
  );
  const aliases = all.filter((h) => h.kind === "exact_alias");
  const exact = all.filter((h) => h.kind === "exact_concept" || h.score >= 80);
  const related = all.filter((h) => h.kind === "related" || (h.score >= 16 && h.score < 80 && h.kind !== "field_value"));

  const breakdownHits: SearchHit[] = [];
  for (const h of exact) {
    const bd = h.concept ? breakdownFor(h.concept.id) : undefined;
    if (bd) {
      breakdownHits.push({
        ...h,
        id: `breakdown:${h.id}`,
        kind: "related",
        score: h.score - 1,
      });
    }
  }

  const groups: SearchGroup[] = (
    [
      { id: "exact", label: "Exact concepts", hits: dedupeHits(exact) },
      { id: "related", label: "Related concepts", hits: dedupeHits(related).slice(0, 12) },
      { id: "fields", label: "Fields", hits: fieldHits.sort((a, b) => b.score - a.score).slice(0, 10) },
      { id: "measurements", label: "Measurements", hits: dedupeHits(measurements).slice(0, 10) },
      { id: "breakdowns", label: "Available breakdowns", hits: breakdownHits.slice(0, 6) },
      { id: "aliases", label: "Aliases", hits: dedupeHits(aliases).slice(0, 10) },
      { id: "registered", label: "Registered / not constructible", hits: dedupeHits(registered).slice(0, 10) },
    ] satisfies SearchGroup[]
  ).filter((g) => g.hits.length > 0);

  const hits = dedupeHits([...exact, ...fieldHits, ...related]).slice(0, 40);
  return {
    query,
    normalized: needle,
    recognized,
    unknown: recognized.length === 0 && hits.length === 0,
    groups,
    hits,
  };
}

function dedupeHits(hits: SearchHit[]): SearchHit[] {
  const seen = new Set<string>();
  const out: SearchHit[] = [];
  for (const h of hits) {
    if (seen.has(h.id)) continue;
    seen.add(h.id);
    out.push(h);
  }
  return out;
}

export function parseQuery(query: string): ParsedPhenomenon {
  return parsePhenomenon(query);
}
