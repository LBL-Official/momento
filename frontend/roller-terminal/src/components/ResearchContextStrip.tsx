import type { ResearchContext, Spec } from "../researchTypes";
import type { InterpretResult } from "../researchTypes";
import type { Freshness, ResultSnapshot, ValidationSnapshot } from "../researchFreshness";
import {
  deriveExecutionStatus,
  deriveObjectId,
  deriveSpecStatus,
  deriveSpecSummary,
} from "../researchLifecycle";
import StatusBadge, { toneForStatus } from "./StatusBadge";

type Props = {
  spec: Spec;
  interpretation: InterpretResult | null;
  validationSnapshot: ValidationSnapshot | null;
  resultSnapshot: ResultSnapshot | null;
  validationFreshness: Freshness;
  executionFreshness: Freshness;
  researchContext: ResearchContext | null;
  runBusy: boolean;
  onClearContext: () => void;
  onViewObject: () => void;
};

export default function ResearchContextStrip({
  spec,
  interpretation,
  validationSnapshot,
  resultSnapshot,
  validationFreshness,
  executionFreshness,
  researchContext,
  runBusy,
  onClearContext,
  onViewObject,
}: Props) {
  const objectId = deriveObjectId(
    validationFreshness,
    validationSnapshot,
    executionFreshness,
    resultSnapshot,
  );
  const specStatus = deriveSpecStatus(validationFreshness, validationSnapshot, interpretation);
  const execStatus = deriveExecutionStatus(executionFreshness, resultSnapshot, runBusy);
  const chips = deriveSpecSummary(spec);

  const priorValidationId =
    validationFreshness === "STALE"
      ? validationSnapshot?.payload.research_object_id
      : null;
  const priorResultId =
    executionFreshness === "STALE" ? resultSnapshot?.payload.research_object_id : null;

  return (
    <div className="context-strip">
      <div className="context-row">
        <div className="context-block">
          <div className="context-k">CURRENT OBJECT</div>
          <div className={`context-v mono ${objectId === "UNVALIDATED" ? "muted" : ""}`}>
            {objectId === "UNVALIDATED" ? "OBJECT: UNVALIDATED" : objectId}
          </div>
          {priorValidationId ? (
            <div className="muted small">prior validation: {priorValidationId}</div>
          ) : null}
          {priorResultId ? (
            <div className="muted small">prior result: {priorResultId}</div>
          ) : null}
        </div>
        <div className="context-block">
          <div className="context-k">SPEC</div>
          <StatusBadge label={specStatus} tone={toneForStatus(specStatus)} />
          {validationFreshness === "STALE" ? (
            <div className="muted small">REVALIDATE REQUIRED</div>
          ) : null}
        </div>
        <div className="context-block">
          <div className="context-k">EXECUTION</div>
          <StatusBadge label={String(execStatus)} tone={toneForStatus(String(execStatus))} />
          {executionFreshness === "STALE" ? (
            <div className="muted small">PRIOR RESULT PRESERVED</div>
          ) : null}
        </div>
        <div className="context-block grow">
          <div className="context-k">OBJECT SUMMARY</div>
          <div className="chip-row tight">
            {chips.length === 0 ? (
              <span className="muted small">No derived fields yet</span>
            ) : (
              chips.map((c) => (
                <span key={c} className="summary-chip">
                  {c}
                </span>
              ))
            )}
          </div>
        </div>
      </div>

      {researchContext ? (
        <div className="observation-context">
          <div className="context-k">OBSERVATION CONTEXT</div>
          <div className="context-row">
            <div>
              <div className="mono">{researchContext.internal_game_id}</div>
              <div className="muted small">{researchContext.as_of}</div>
              {researchContext.observation_id ? (
                <div className="muted small">O_t · {researchContext.observation_id}</div>
              ) : (
                <div className="muted small">O_t</div>
              )}
              <div className="muted small">
                {[researchContext.sport, researchContext.season].filter(Boolean).join(" · ")}
              </div>
              <div className="muted small">EXPLORER CONTEXT ≠ research_spec binding</div>
            </div>
            <div className="row" style={{ marginBottom: 0 }}>
              <button type="button" className="btn-secondary" onClick={onViewObject}>
                VIEW OBJECT
              </button>
              <button type="button" className="btn-secondary" onClick={onClearContext}>
                CLEAR CONTEXT
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
