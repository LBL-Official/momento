/** Compatibility facade over the compositional vocabulary module. */

import {
  buildDiscoveryIndex,
  searchDiscovery,
  type CanonicalConcept,
  type VocabFile,
} from "./vocabulary";

export type { VocabFile };

export type VocabEntry = {
  id: string;
  kind: "concept" | "phenomenon" | "template" | "measurement" | "guide" | "field" | "family";
  title: string;
  aliases: string[];
  definition: string;
  constructibility?: string;
  compatiblePopulations?: string[];
  knownMeasurements?: string[];
  templates?: string[];
  raw?: unknown;
  compilerAccepted?: boolean;
};

function toEntry(c: CanonicalConcept): VocabEntry {
  return {
    id: c.id,
    kind:
      c.conceptType === "measurement"
        ? "measurement"
        : c.conceptType === "data field"
          ? "field"
          : c.conceptType === "population"
            ? "phenomenon"
            : "concept",
    title: c.displayName,
    aliases: [],
    definition: c.definition,
    constructibility: c.constructibility,
    compatiblePopulations: c.compatiblePopulations,
    knownMeasurements: c.knownMeasurements,
    templates: c.templates,
    raw: c,
    compilerAccepted: c.compilerConcept,
  };
}

export function buildVocabularyIndex(vocab: VocabFile | null): VocabEntry[] {
  return buildDiscoveryIndex(vocab).concepts.map(toEntry);
}

export function searchVocabulary(entries: VocabEntry[], q: string): VocabEntry[] {
  const index = buildDiscoveryIndex(null);
  const grouped = searchDiscovery(index, q);
  const byId = new Map(entries.map((e) => [e.id, e]));
  const out: VocabEntry[] = [];
  for (const hit of grouped.hits) {
    const fromList = byId.get(hit.concept?.id ?? hit.id);
    if (fromList) out.push(fromList);
    else if (hit.concept) out.push(toEntry(hit.concept));
  }
  return out.slice(0, 60);
}
