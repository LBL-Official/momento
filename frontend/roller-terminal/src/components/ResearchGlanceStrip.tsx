import { summarizeResearchSpec } from "../researchSummary";
import { asArr, asObj, type Spec } from "../researchTypes";
import type { Freshness } from "../researchFreshness";

type Props = {
  spec: Spec;
  validationFreshness: Freshness;
  validationStatus: string | null;
  executionFreshness: Freshness;
  executionStatus: string | null;
};

function isEssentiallyBlank(spec: Spec): boolean {
  const identity = asObj(spec.identity);
  const name = String(identity.name || "").trim();
  const measures = asArr(spec.measurement_requests);
  const defs = asObj(spec.definition_versions);
  const pop = asObj(spec.population_binding);
  const slices = asArr(pop.default_structural_slices);
  return !name && measures.length === 0 && Object.keys(defs).length === 0 && slices.length === 0;
}

/** Compact derived summary — never invents FIRST80 / bindings. */
export default function ResearchGlanceStrip({
  spec,
  validationFreshness,
  validationStatus,
  executionFreshness,
  executionStatus,
}: Props) {
  if (isEssentiallyBlank(spec)) {
    return (
      <div className="glance-strip" id="research-glance">
        <div className="context-k">RESEARCH OBJECT AT A GLANCE</div>
        <div className="empty-state glance-empty">
          <div className="empty-title">DEFINE A PHENOMENON</div>
          <p className="muted">
            No empirical claim exists until the research object is explicitly defined.
          </p>
        </div>
      </div>
    );
  }

  const s = summarizeResearchSpec(spec);
  const defKeys = Object.keys(asObj(spec.definition_versions));

  let specLabel: string;
  if (validationFreshness === "STALE") specLabel = "STALE";
  else if (validationFreshness === "CURRENT" && validationStatus) specLabel = validationStatus;
  else specLabel = "UNVALIDATED";

  let execLabel: string;
  if (executionFreshness === "NONE") execLabel = "NONE";
  else if (executionFreshness === "STALE") execLabel = "PRIOR";
  else execLabel = executionStatus ?? "COMPLETE";

  const rows: [string, string][] = [
    ["UNIVERSE", s.universe ?? "—"],
    ["LEAGUES", s.leagues.length ? s.leagues.join(", ") : "—"],
    ["SLICE", s.slices.length ? s.slices.join(", ") : "—"],
    ["ANCHOR", s.anchor ?? "—"],
    ["MEASURES", String(s.measurements.length)],
    ["BINDINGS", defKeys.length ? defKeys.join(", ") : "—"],
    ["SPEC", specLabel],
    ["EXECUTION", execLabel],
  ];

  return (
    <div className="glance-strip" id="research-glance">
      <div className="context-k">RESEARCH OBJECT AT A GLANCE</div>
      <dl className="glance-grid">
        {rows.map(([k, v]) => (
          <div key={k} className="glance-cell">
            <dt>{k}</dt>
            <dd className="mono">{v}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
