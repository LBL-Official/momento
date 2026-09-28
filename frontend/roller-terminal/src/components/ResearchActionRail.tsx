/** Sticky research-object action rail — single source of action availability. */

type Props = {
  ideaText: string;
  hasProposedSpec: boolean;
  canRun: boolean;
  interpretBusy: boolean;
  validateBusy: boolean;
  runBusy: boolean;
  validationFreshness: string;
  onInterpret: () => void;
  onApply: () => void;
  onValidate: () => void;
  onRun: () => void;
  onExport: () => void;
};

export default function ResearchActionRail({
  ideaText,
  hasProposedSpec,
  canRun,
  interpretBusy,
  validateBusy,
  runBusy,
  validationFreshness,
  onInterpret,
  onApply,
  onValidate,
  onRun,
  onExport,
}: Props) {
  const busy = interpretBusy || validateBusy || runBusy;
  return (
    <div className="action-rail" role="toolbar" aria-label="Research object actions">
      <div className="action-rail-label">ACTIONS</div>
      <div className="action-rail-buttons">
        <button
          type="button"
          className="btn-primary"
          onClick={onInterpret}
          disabled={interpretBusy || !ideaText.trim()}
          title="Cmd/Ctrl+Enter in interpretation textarea"
        >
          {interpretBusy ? "INTERPRETING…" : "INTERPRET"}
        </button>
        <button
          type="button"
          className="btn-primary"
          onClick={onApply}
          disabled={!hasProposedSpec || busy}
          title="Replace App-owned spec with structuredClone(proposed_spec)"
        >
          APPLY
        </button>
        <button
          type="button"
          className="btn-primary"
          onClick={onValidate}
          disabled={validateBusy || runBusy}
        >
          {validateBusy ? "VALIDATING…" : "VALIDATE"}
        </button>
        <button
          type="button"
          className="btn-primary"
          onClick={onRun}
          disabled={busy || !canRun}
          title={
            canRun
              ? "Execute App-owned current spec"
              : validationFreshness === "STALE"
                ? "SPEC CHANGED — REVALIDATE REQUIRED"
                : "CURRENT SPEC HAS NOT BEEN VALIDATED"
          }
        >
          {runBusy ? "RUNNING…" : "RUN RESEARCH"}
        </button>
        <button type="button" className="btn-secondary" onClick={onExport} title="Export CURRENT spec only">
          EXPORT JSON
        </button>
      </div>
    </div>
  );
}
