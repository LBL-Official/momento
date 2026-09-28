/** Phase 5.7 — compact research_spec summary. Pure helpers only. */

import { asArr, asObj, type Spec } from "./researchTypes";

export type ResearchSpecSummary = {
  universe: string | null;
  leagues: string[];
  slices: string[];
  anchor: string | null;
  measurements: string[];
  definitionVersions: string[];
  informationRegime: string | null;
  lines: string[];
};

/**
 * Derive a compact human summary from actual spec keys only.
 * Never infers FIRST80 from FIRST_PRICE_TOUCH + price_e4.
 */
export function summarizeResearchSpec(spec: Spec | null | undefined): ResearchSpecSummary {
  if (!spec) {
    return {
      universe: null,
      leagues: [],
      slices: [],
      anchor: null,
      measurements: [],
      definitionVersions: [],
      informationRegime: null,
      lines: [],
    };
  }

  const universe = typeof spec.universe === "string" ? spec.universe : null;
  const pop = asObj(spec.population_binding);
  const leagues = asArr(pop.leagues).filter((x) => typeof x === "string") as string[];
  const slices = asArr(pop.default_structural_slices).filter(
    (x) => typeof x === "string",
  ) as string[];

  const anchorObj = asObj(spec.anchor);
  let anchor: string | null = null;
  if (typeof anchorObj.event === "string" && anchorObj.event) {
    anchor =
      anchorObj.price_e4 != null && anchorObj.price_e4 !== ""
        ? `${anchorObj.event} @ ${String(anchorObj.price_e4)}`
        : anchorObj.event;
  }

  const measurements = (asArr(spec.measurement_requests) as Record<string, unknown>[])
    .map((m) => (typeof m.name === "string" ? m.name : null))
    .filter((x): x is string => Boolean(x));

  const defs = asObj(spec.definition_versions);
  const definitionVersions = Object.keys(defs).map((k) => {
    const v = defs[k];
    return typeof v === "string" ? `${k} · ${v}` : k;
  });

  const informationRegime =
    typeof spec.information_regime === "string" ? spec.information_regime : null;

  const lines: string[] = [];
  if (universe) lines.push(universe);
  if (leagues.length) lines.push(leagues.join(", "));
  if (slices.length) lines.push(slices.join(", "));
  if (anchor) lines.push(anchor);
  if (definitionVersions.length) lines.push(definitionVersions.join(" · "));
  if (measurements.length) lines.push(`${measurements.length} measurements`);
  else lines.push("0 measurements");

  return {
    universe,
    leagues,
    slices,
    anchor,
    measurements,
    definitionVersions,
    informationRegime,
    lines,
  };
}

export function summaryOneLine(spec: Spec | null | undefined): string {
  return summarizeResearchSpec(spec).lines.join(" · ");
}
