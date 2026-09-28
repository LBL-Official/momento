import { useMemo, useState } from "react";
import {
  diffResearchSpecs,
  shortFingerprint,
  type ResearchSpecDiff,
} from "../researchDiff";
import type { Freshness, ResultSnapshot, ValidationSnapshot } from "../researchFreshness";
import type { Spec } from "../researchTypes";
import StatusBadge, { toneForStatus } from "./StatusBadge";
import ResearchSpecDiffView from "./ResearchSpecDiff";

type Props = {
  currentSpec: Spec;
  currentSpecFingerprint: string;
  validationSnapshot: ValidationSnapshot | null;
  resultSnapshot: ResultSnapshot | null;
  validationFreshness: Freshness;
  executionFreshness: Freshness;
  onOpenValidatedJson?: () => void;
};

export default function ResearchAuditStrip({
  currentSpec,
  currentSpecFingerprint,
  validationSnapshot,
  resultSnapshot,
  validationFreshness,
  executionFreshness,
  onOpenValidatedJson,
}: Props) {
  const [showValDiff, setShowValDiff] = useState(false);
  const [showExecDiff, setShowExecDiff] = useState(false);

  const vsValidated = useMemo(
    () => diffResearchSpecs(currentSpec, validationSnapshot?.spec ?? null),
    [currentSpec, validationSnapshot],
  );
  const vsExecuted = useMemo(
    () => diffResearchSpecs(currentSpec, resultSnapshot?.spec ?? null),
    [currentSpec, resultSnapshot],
  );

  const allEqual =
    validationFreshness === "CURRENT" &&
    (executionFreshness === "CURRENT" || executionFreshness === "NONE") &&
    (!resultSnapshot || executionFreshness === "CURRENT");

  const converged =
    validationFreshness === "CURRENT" &&
    executionFreshness === "CURRENT" &&
    validationSnapshot?.specFingerprint === resultSnapshot?.specFingerprint;

  return (
    <div className="audit-strip">
      <div className="context-k">RESEARCH AUDIT</div>
      {converged || (allEqual && executionFreshness === "NONE") ? (
        <div className="muted small audit-equal">
          {converged
            ? "CURRENT = VALIDATED = EXECUTED"
            : validationFreshness === "CURRENT"
              ? "CURRENT = VALIDATED · EXECUTION NOT RUN"
              : null}
        </div>
      ) : null}

      <div className="audit-grid">
        <AuditCell
          label="CURRENT"
          fingerprint={currentSpecFingerprint}
          badge="CURRENT"
          detail={null}
        />
        <AuditCell
          label="VALIDATED"
          fingerprint={validationSnapshot?.specFingerprint}
          badge={
            !validationSnapshot
              ? "ABSENT"
              : validationFreshness === "CURRENT"
                ? String(validationSnapshot.payload.status)
                : `STALE · ${vsValidated.changed_count}Δ`
          }
          detail={
            validationSnapshot?.payload.research_object_id
              ? `id ${validationSnapshot.payload.research_object_id}`
              : null
          }
          onDiff={
            validationFreshness === "STALE" && vsValidated.changed_count > 0
              ? () => setShowValDiff((v) => !v)
              : undefined
          }
          diffOpen={showValDiff}
          onViewSpec={validationSnapshot?.spec ? onOpenValidatedJson : undefined}
        />
        <AuditCell
          label="EXECUTED"
          fingerprint={resultSnapshot?.specFingerprint}
          badge={
            !resultSnapshot
              ? "NOT RUN"
              : executionFreshness === "CURRENT"
                ? String(resultSnapshot.payload.execution_status)
                : "PRIOR RESULT"
          }
          detail={
            resultSnapshot?.payload.research_object_id
              ? `id ${resultSnapshot.payload.research_object_id}`
              : null
          }
          onDiff={
            executionFreshness === "STALE" && vsExecuted.changed_count > 0
              ? () => setShowExecDiff((v) => !v)
              : undefined
          }
          diffOpen={showExecDiff}
        />
      </div>

      {showValDiff ? (
        <ResearchSpecDiffView
          title="SPEC CHANGED SINCE VALIDATION"
          diff={vsValidated}
        />
      ) : null}
      {showExecDiff ? (
        <ResearchSpecDiffView
          title="CURRENT SPEC vs EXECUTED SPEC"
          diff={vsExecuted}
        />
      ) : null}
    </div>
  );
}

function AuditCell({
  label,
  fingerprint,
  badge,
  detail,
  onDiff,
  diffOpen,
  onViewSpec,
}: {
  label: string;
  fingerprint?: string | null;
  badge: string;
  detail: string | null;
  onDiff?: () => void;
  diffOpen?: boolean;
  onViewSpec?: () => void;
}) {
  return (
    <div className="audit-cell">
      <div className="context-k">{label}</div>
      <div className="mono small">fp: {shortFingerprint(fingerprint)}</div>
      <StatusBadge label={badge} tone={toneForStatus(badge.split("·")[0].trim())} />
      {detail ? <div className="muted small mono">{detail}</div> : null}
      <div className="row" style={{ marginBottom: 0, marginTop: "0.35rem" }}>
        {onDiff ? (
          <button type="button" className="btn-secondary" onClick={onDiff}>
            {diffOpen ? "HIDE Δ" : "VIEW Δ"}
          </button>
        ) : null}
        {onViewSpec ? (
          <button type="button" className="btn-secondary" onClick={onViewSpec}>
            VIEW VALIDATED SPEC
          </button>
        ) : null}
      </div>
    </div>
  );
}

/** Compact header audit chips. */
export function ResearchAuditChips({
  validationFreshness,
  executionFreshness,
  validationDiff,
  capabilitySummary,
  onFocusAudit,
}: {
  validationFreshness: Freshness;
  executionFreshness: Freshness;
  validationDiff: ResearchSpecDiff | null;
  capabilitySummary?: string | null;
  onFocusAudit?: () => void;
}) {
  const valLabel =
    validationFreshness === "UNVALIDATED"
      ? "UNVALIDATED"
      : validationFreshness === "STALE"
        ? `STALE · ${validationDiff?.changed_count ?? 0}Δ`
        : "CURRENT";
  const resLabel =
    executionFreshness === "NONE"
      ? "NONE"
      : executionFreshness === "STALE"
        ? "PRIOR"
        : "CURRENT";

  return (
    <button type="button" className="audit-chips" onClick={onFocusAudit}>
      <span>
        SPEC <strong>CURRENT</strong>
      </span>
      <span className="caveat-sep">·</span>
      <span>
        VALIDATION <strong>{valLabel}</strong>
      </span>
      {capabilitySummary ? (
        <>
          <span className="caveat-sep">·</span>
          <span>
            CAPABILITY <strong>{capabilitySummary}</strong>
          </span>
        </>
      ) : null}
      <span className="caveat-sep">·</span>
      <span>
        RESULT <strong>{resLabel}</strong>
      </span>
    </button>
  );
}
