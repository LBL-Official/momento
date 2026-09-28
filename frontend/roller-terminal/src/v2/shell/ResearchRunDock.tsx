import type { Freshness } from "../../researchFreshness";

type Props = {
  identityName: string;
  validationFreshness: Freshness;
  canRun: boolean;
  runBusy: boolean;
  validateBusy?: boolean;
  onValidate: () => void;
  onRun: () => void;
  onValidateAndRun: () => void;
  onRevertToValidated?: () => void;
  onReloadTemplate?: () => void;
};

/** Viewport-pinned research actions — always reachable while scrolling Lab. */
export default function ResearchRunDock({
  identityName,
  validationFreshness,
  canRun,
  runBusy,
  validateBusy,
  onValidate,
  onRun,
  onValidateAndRun,
  onRevertToValidated,
  onReloadTemplate,
}: Props) {
  const busy = Boolean(runBusy || validateBusy);
  const stale = validationFreshness === "STALE";

  return (
    <div className="ws-run-dock" role="toolbar" aria-label="Validate and run">
      <div className="ws-run-dock-meta">
        <span className="evidence">{identityName}</span>
        <span className="muted small">
          {stale
            ? "STALE — revert or revalidate"
            : canRun
              ? "Ready · ⌘↵ Validate & Run"
              : "Validate first · then Run"}
        </span>
      </div>
      <div className="ws-run-dock-actions">
        {stale ? (
          <>
            {onRevertToValidated ? (
              <button type="button" className="btn-secondary" onClick={onRevertToValidated}>
                Revert
              </button>
            ) : null}
            {onReloadTemplate ? (
              <button type="button" className="btn-secondary" onClick={onReloadTemplate}>
                Reload template
              </button>
            ) : null}
          </>
        ) : null}
        <button type="button" className="btn-secondary" onClick={onValidate} disabled={busy}>
          {stale ? "Revalidate" : "Validate"}
        </button>
        {canRun ? (
          <button type="button" className="btn-primary" onClick={onRun} disabled={busy}>
            {runBusy ? "Running…" : "Run"}
          </button>
        ) : (
          <button
            type="button"
            className="btn-primary"
            onClick={onValidateAndRun}
            disabled={busy || stale}
            title={stale ? "Revert or revalidate first" : "Validate, then run if RUNNABLE"}
          >
            {busy ? "Working…" : "Validate & Run"}
          </button>
        )}
      </div>
    </div>
  );
}
