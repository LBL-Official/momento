import type { Freshness } from "../researchFreshness";

/** RESEARCH CHECKPOINT — derived freshness + optional capability counts. */
export default function ResearchCheckpoint({
  validationFreshness,
  executionFreshness,
  validationStatus,
  executionStatus,
  capabilitySummary,
  capabilitiesLoading,
  capabilitiesError,
}: {
  validationFreshness: Freshness;
  executionFreshness: Freshness;
  validationStatus: string | null;
  executionStatus: string | null;
  capabilitySummary?: string | null;
  capabilitiesLoading?: boolean;
  capabilitiesError?: string | null;
}) {
  const valLabel =
    validationFreshness === "UNVALIDATED"
      ? "UNVALIDATED"
      : validationFreshness === "STALE"
        ? "STALE"
        : validationStatus ?? "CURRENT";

  const execLabel =
    executionFreshness === "NONE"
      ? "NOT RUN"
      : executionFreshness === "STALE"
        ? "PRIOR"
        : executionStatus ?? "COMPLETE";

  let capLabel: string | null = null;
  if (capabilitiesLoading) capLabel = "LOADING";
  else if (capabilitiesError) capLabel = "UNAVAILABLE";
  else if (capabilitySummary) capLabel = capabilitySummary;

  return (
    <div className="checkpoint-strip">
      <div className="context-k">RESEARCH CHECKPOINT</div>
      <div className="checkpoint-row">
        <span>
          SPEC <strong>CURRENT</strong>
        </span>
        <span className="caveat-sep">·</span>
        <span>
          VALIDATION <strong>{valLabel}</strong>
        </span>
        {capLabel ? (
          <>
            <span className="caveat-sep">·</span>
            <span>
              CAPABILITY <strong>{capLabel}</strong>
            </span>
          </>
        ) : null}
        <span className="caveat-sep">·</span>
        <span>
          EXECUTION <strong>{execLabel}</strong>
        </span>
      </div>
    </div>
  );
}
