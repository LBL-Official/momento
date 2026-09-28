import type { Freshness, ValidationSnapshot } from "../../researchFreshness";

type Props = {
  validationFreshness: Freshness;
  executionFreshness: Freshness;
  validationSnapshot: ValidationSnapshot | null;
  canRun: boolean;
  onRevalidate?: () => void;
  onReviewDetails?: () => void;
};

export default function ResearchStatus({
  validationFreshness,
  executionFreshness,
  validationSnapshot,
  canRun,
  onRevalidate,
  onReviewDetails,
}: Props) {
  let title = "Not ready";
  let tone: "ok" | "warn" | "neutral" = "neutral";
  let detail = "Define a research question, then validate.";

  if (canRun && validationFreshness === "CURRENT") {
    title = "Ready to run";
    tone = "ok";
    detail = "Population binding valid · measurements supported";
  } else if (validationFreshness === "STALE" || executionFreshness === "STALE") {
    title = "Review required";
    tone = "warn";
    detail = "The research object changed after validation or the result is prior.";
  } else if (
    validationSnapshot &&
    (validationSnapshot.payload.status === "INVALID" ||
      validationSnapshot.payload.status === "UNRESOLVED")
  ) {
    title = "Requires attention";
    tone = "warn";
    detail = "Some required research fields are unresolved.";
  } else if (validationFreshness === "CURRENT") {
    title = validationSnapshot?.payload.status || "Validated";
    tone = "neutral";
    detail = "Validation current — check runnability.";
  }

  return (
    <div className={`v2-research-status tone-${tone}`} aria-label="Research status">
      <div className="v2-research-status-title">{title}</div>
      <div className="muted">{detail}</div>
      <div className="v2-research-status-actions">
        {validationFreshness === "STALE" && onRevalidate ? (
          <button type="button" className="btn-primary" onClick={onRevalidate}>
            Revalidate
          </button>
        ) : null}
        {onReviewDetails ? (
          <button type="button" className="btn-secondary" onClick={onReviewDetails}>
            Review details
          </button>
        ) : null}
      </div>
    </div>
  );
}
