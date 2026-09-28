import SuperasiAResults from "./SuperasiAResults";
import type { SuperasiBaseInspect, SuperasiLabSource } from "./types/superasi";

type Props = {
  inspect: SuperasiBaseInspect | null;
  selected?: SuperasiLabSource | null;
  busy?: boolean;
  advancingToFinal?: boolean;
  onOpenLabs: () => void;
  onRun?: (lab: SuperasiLabSource) => void;
  onCancelHandoff?: () => void;
};

export default function BaseRun({
  inspect,
  selected,
  busy,
  advancingToFinal,
  onOpenLabs,
  onRun,
  onCancelHandoff,
}: Props) {
  const inspectMatchesSelected =
    inspect != null && (!selected || inspect.source_lab_id === selected.lab_id);
  if (busy) {
    return (
      <div className="sa-page">
        <h1 className="v2-page-title">{advancingToFinal ? "Advancing to Final Results" : "SuperASI A — Base"}</h1>
        <p className="v2-lede">
          {advancingToFinal
            ? `Warehouse Move already owns SuperASI A, then B, for ${
                selected?.strategy_name || inspect?.strategy_name || "this lab"
              }. The Run SuperASI A — Base button stays off until that finishes. ITI is not started.`
            : `Ingesting ${selected?.strategy_name || inspect?.strategy_name || "the Roller CSV"} and writing SuperasiABase.`}
        </p>
        {advancingToFinal && onCancelHandoff ? (
          <button type="button" className="btn-secondary" onClick={onCancelHandoff}>
            Stop waiting — run SuperASI A myself
          </button>
        ) : null}
      </div>
    );
  }
  if (!inspectMatchesSelected || !inspect) {
    return (
      <div className="sa-page">
        <h1 className="v2-page-title">SuperASI A — Base</h1>
        {selected ? (
          <>
            <p className="v2-lede">
              Selected from Roller CSVs. Run SuperASI A — Base to grade this CSV. The letter grade is evidence of that
              CSV, not the 70% desk model.
            </p>
            <section className="ws-labs-inspect" aria-label="Selected Roller CSV">
              <p className="v2-kicker">Selected</p>
              <h2>{selected.strategy_name}</h2>
              <p className="muted small">
                {selected.folder} · {selected.filename} · {selected.lab_id}
              </p>
              <p className={selected.population_matches_rows === false ? "sa-error" : "muted small"}>
                rows={selected.rows ?? "—"} · header={selected.header_population ?? "—"}
                {selected.population_matches_rows === false ? " · population_matches_rows FAIL" : ""}
              </p>
              <button type="button" className="btn-primary" disabled={!onRun} onClick={() => onRun?.(selected)}>
                Run SuperASI A — Base
              </button>
            </section>
          </>
        ) : (
          <p className="v2-lede">
            Select a Roller CSV in research sequence 01, then return here. SuperASI A does not start until you run it.
          </p>
        )}
      </div>
    );
  }
  return (
    <div className="sa-page">
      <SuperasiAResults inspect={inspect} />
      <div className="ws-labs-toolbar">
        {selected && onRun ? (
          <button type="button" className="btn-primary" onClick={() => onRun(selected)}>
            Run SuperASI A — Base again
          </button>
        ) : null}
        <button type="button" className="btn-secondary" onClick={onOpenLabs}>
          Open SuperASI Results Labs (phase a)
        </button>
      </div>
    </div>
  );
}
