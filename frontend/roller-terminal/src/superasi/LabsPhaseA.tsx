import type { SuperasiBaseInspect, SuperasiBaseResult, SuperasiLabSource } from "./types/superasi";
import SuperasiAResults from "./SuperasiAResults";

type Props = {
  selected: SuperasiLabSource | null;
  inspect: SuperasiBaseInspect | null;
  result: SuperasiBaseResult | null;
  loading?: boolean;
  busy?: boolean;
  onRunDebase: (row: SuperasiBaseResult) => void;
  onDownloadBase: (row: SuperasiBaseResult) => void;
  onDownloadRoller: (row: SuperasiBaseResult) => void;
  onOpenA: () => void;
};

export default function LabsPhaseA({
  selected,
  inspect,
  result,
  loading,
  busy,
  onRunDebase,
  onDownloadBase,
  onDownloadRoller,
  onOpenA,
}: Props) {
  const inspectMatches =
    inspect != null && (!selected || inspect.source_lab_id === selected.lab_id);

  return (
    <div className="sa-page">
      {!selected ? (
        <>
          <h1 className="v2-page-title">SuperASI Results Labs (phase a)</h1>
          <p className="v2-lede">
            Select a Roller CSV in research sequence 01. This page lays out that strategy’s SuperASI A
            result. It is not a library of every Roller CSV.
          </p>
        </>
      ) : null}

      {selected && !inspectMatches && !result && !loading ? (
        <>
          <h1 className="v2-page-title">{selected.strategy_name}</h1>
          <p className="v2-lede">
            SuperASI A has not run for this Roller CSV. Sequence 02 grades it. A already ran is required
            before this page can lay out results.
          </p>
          <p className={selected.population_matches_rows === false ? "sa-error" : "muted small"}>
            {selected.filename} · rows={selected.rows ?? "—"} · header={selected.header_population ?? "—"}
          </p>
          <button type="button" className="btn-primary" onClick={onOpenA}>
            Open SuperASI A — Base
          </button>
        </>
      ) : null}

      {selected && !inspectMatches && (loading || result) ? (
        <>
          <h1 className="v2-page-title">{selected.strategy_name}</h1>
          <p className="v2-lede">Loading SuperASI A results for the selected Roller CSV.</p>
        </>
      ) : null}

      {inspectMatches && inspect ? (
        <>
          <p className="v2-kicker">Results Labs (phase a)</p>
          <SuperasiAResults inspect={inspect} />
          <p className="muted small">A already ran. This runs B.</p>
          {result ? (
            <div className="ws-labs-actions">
              <button type="button" className="btn-primary" disabled={busy} onClick={() => onRunDebase(result)}>
                {busy ? "Running SuperASI B…" : "Run SuperASI B — Debase"}
              </button>
              <button type="button" className="v2-text-link" onClick={() => onDownloadRoller(result)}>
                Download Roller CSV
              </button>
              <button type="button" className="v2-text-link" onClick={() => onDownloadBase(result)}>
                Download SuperasiABase CSV
              </button>
            </div>
          ) : null}
        </>
      ) : null}
    </div>
  );
}
