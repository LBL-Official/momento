import type { Freshness } from "../researchFreshness";

type Props = {
  validationFreshness: Freshness;
  executionFreshness: Freshness;
  /** Short mono id / fingerprint for current object when present */
  currentDetail?: string | null;
  validationDetail?: string | null;
  executionDetail?: string | null;
};

/**
 * Sole substantial top-of-chrome status object.
 * Derived from existing freshness helpers — no new state machine.
 */
export default function ResearchStatePanel({
  validationFreshness,
  executionFreshness,
  currentDetail,
  validationDetail,
  executionDetail,
}: Props) {
  const currentLabel =
    validationFreshness === "UNVALIDATED"
      ? "UNVALIDATED"
      : validationFreshness === "CURRENT"
        ? "VALIDATED"
        : validationFreshness === "STALE"
          ? "STALE"
          : String(validationFreshness);

  return (
    <section className="research-state" aria-label="Research state">
      <div className="research-state-label">Research State</div>
      <div className="research-state-grid">
        <div className="research-state-cell">
          <div className="research-state-k">Current</div>
          <div className="research-state-v">{currentLabel}</div>
          {currentDetail ? (
            <div className="research-state-detail mono">{currentDetail}</div>
          ) : null}
        </div>
        <div className="research-state-cell">
          <div className="research-state-k">Validation</div>
          <div className={`research-state-v status-${validationFreshness}`}>
            {validationFreshness}
          </div>
          {validationDetail ? (
            <div className="research-state-detail mono">{validationDetail}</div>
          ) : null}
        </div>
        <div className="research-state-cell">
          <div className="research-state-k">Execution</div>
          <div className={`research-state-v status-${executionFreshness}`}>
            {executionFreshness}
          </div>
          {executionDetail ? (
            <div className="research-state-detail mono">{executionDetail}</div>
          ) : null}
        </div>
      </div>
    </section>
  );
}
