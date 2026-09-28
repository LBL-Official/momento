import { useMemo, useState } from "react";
import FolderTile from "./FolderTile";
import SuperasiAResults from "./SuperasiAResults";
import SuperasiBResults from "./SuperasiBResults";
import type { SuperasiBaseInspect, SuperasiDebaseInspect, SuperasiDebaseResult, SuperasiLabSource } from "./types/superasi";

type Props = {
  selected: SuperasiLabSource | null;
  inspect: SuperasiDebaseInspect | null;
  phaseAInspect?: SuperasiBaseInspect | null;
  result: SuperasiDebaseResult | null;
  results: SuperasiDebaseResult[];
  viewingId?: string | null;
  loading?: boolean;
  busy?: boolean;
  onOpenA: () => void;
  onOpenB: () => void;
  onSelectOther: (row: SuperasiDebaseResult) => void;
  onRefresh: () => void;
  onDownloadDebase: (row: SuperasiDebaseResult) => void;
  onDownloadAbase: (row: SuperasiDebaseResult) => void;
  onDownloadRoller: (row: SuperasiDebaseResult) => void;
  onGoToIti: (resultId: string) => void;
  onOpenJump?: () => void;
};

export default function LabsPhaseB({
  selected,
  inspect,
  phaseAInspect,
  result,
  results,
  viewingId,
  loading,
  busy,
  onOpenA,
  onOpenB,
  onSelectOther,
  onRefresh,
  onDownloadDebase,
  onDownloadAbase,
  onDownloadRoller,
  onGoToIti,
  onOpenJump,
}: Props) {
  const [pickerOpen, setPickerOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<"created" | "name">("name");
  const inspectMatches = inspect != null && viewingId != null && inspect.result_id === viewingId;
  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    const rows = results.filter((row) => {
      if (!q) return true;
      return `${row.strategy_name} ${row.folder || ""} ${row.DEBASE_GRADE || ""} ${row.BASE_GRADE || ""}`
        .toLowerCase()
        .includes(q);
    });
    return [...rows].sort((a, b) => {
      if (sort === "name") return a.strategy_name.localeCompare(b.strategy_name);
      return String(b.created_at || "").localeCompare(String(a.created_at || ""));
    });
  }, [query, results, sort]);

  return (
    <div className="sa-page">
      {!selected && !viewingId && !inspectMatches ? (
        <>
          <h1 className="v2-page-title">SuperASI Final Results</h1>
          <p className="v2-lede">
            Select a Roller CSV in research sequence 01. This page lays out that strategy’s SuperASI B
            result. It is not a library of every Phase B folder.
          </p>
        </>
      ) : null}

      {selected && !inspectMatches && !result && !viewingId && !loading ? (
        <>
          <h1 className="v2-page-title">{selected.strategy_name}</h1>
          <p className="v2-lede">
            SuperASI B has not run for this Roller CSV. Sequence 03 runs B after A. B already ran is
            required before this page can lay out Final Results.
          </p>
          <p className={selected.population_matches_rows === false ? "sa-error" : "muted small"}>
            {selected.filename} · rows={selected.rows ?? "—"} · header={selected.header_population ?? "—"}
          </p>
          <div className="ws-labs-actions">
            <button type="button" className="btn-primary" onClick={onOpenB}>
              Open SuperASI B — Debase
            </button>
            <button type="button" className="btn-secondary" onClick={onOpenA}>
              Open Results Labs (phase a)
            </button>
          </div>
        </>
      ) : null}

      {selected && !inspectMatches && (loading || result || viewingId) ? (
        <>
          <h1 className="v2-page-title">{selected.strategy_name}</h1>
          <p className="v2-lede">Loading SuperASI B Final Results for the selected strategy.</p>
        </>
      ) : null}

      {!selected && viewingId && !inspectMatches ? (
        <>
          <h1 className="v2-page-title">SuperASI Final Results</h1>
          <p className="v2-lede">Loading SuperASI B Final Results.</p>
        </>
      ) : null}

      {inspectMatches && inspect ? (
        <>
          <p className="v2-kicker">Final Results</p>
          {phaseAInspect ? <SuperasiAResults inspect={phaseAInspect} embedded /> : null}
          <SuperasiBResults inspect={inspect} />
          {result ? (
            <div className="ws-labs-actions">
              <button type="button" className="v2-text-link" onClick={() => onDownloadRoller(result)}>
                Download Roller CSV
              </button>
              <button type="button" className="v2-text-link" onClick={() => onDownloadAbase(result)}>
                Download SuperasiABase CSV
              </button>
              <button type="button" className="v2-text-link" onClick={() => onDownloadDebase(result)}>
                Download SuperasiBDeBase CSV
              </button>
            </div>
          ) : null}
        </>
      ) : null}

      <div className="sa-final-picker">
        <div className="ws-labs-actions">
          <button
            type="button"
            className="btn-primary"
            disabled={busy || !result}
            onClick={() => result && onGoToIti(result.result_id)}
          >
            Run ITI
          </button>
          {onOpenJump ? (
            <button type="button" className="btn-secondary" onClick={() => onOpenJump()}>
              Go to Jump
            </button>
          ) : null}
          <button
            type="button"
            className="btn-secondary"
            disabled={busy}
            onClick={() => setPickerOpen((open) => !open)}
          >
            {pickerOpen ? "Hide other Final Results" : "Inspect other Final Results"}
          </button>
        </div>
        {pickerOpen ? (
          <>
            <p className="v2-kicker">Other strategies</p>
            <p className="muted small">
              Folder tiles are SuperASI B results on disk. Click one to inspect. Stored bytes = downloaded
              bytes.
            </p>
            <div className="ws-labs-toolbar">
              <label>
                Sort
                <select value={sort} onChange={(e) => setSort(e.target.value as "created" | "name")}>
                  <option value="name">Name</option>
                  <option value="created">Newest</option>
                </select>
              </label>
              <input
                type="search"
                placeholder="Filter strategy or grade"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
              <button type="button" className="btn-secondary" onClick={onRefresh}>
                Refresh
              </button>
            </div>
            {visible.length ? (
              <div className="sa-folder-grid" role="list">
                {visible.map((row) => (
                  <FolderTile
                    key={row.result_id}
                    name={row.strategy_name}
                    meta={`BASE ${row.BASE_GRADE || "—"} · DEBASE ${row.DEBASE_GRADE || "—"} · rows=${row.rows ?? "—"}`}
                    selected={row.result_id === viewingId}
                    onClick={() => onSelectOther(row)}
                  />
                ))}
              </div>
            ) : (
              <p className="muted small">No Phase B folders yet. Run SuperASI B — Debase from a Phase A result.</p>
            )}
          </>
        ) : null}
      </div>
    </div>
  );
}
