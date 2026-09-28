import { useEffect, useMemo, useRef, useState } from "react";
import { commitIti, getBaseResult, getDebaseResult, getItiRun, latestIti, runIti, type ItiRun, type ItiSlot } from "./api/superasiApi";
import SuperasiAResults from "./SuperasiAResults";
import SuperasiBResults from "./SuperasiBResults";
import type { SuperasiBaseInspect, SuperasiDebaseInspect, SuperasiDebaseResult } from "./types/superasi";

const ATTACHABLE = new Set(["PENDING", "RUNNING", "COMPLETE"]);

type Props = {
  upstream: SuperasiDebaseResult[];
  initialDebaseResultId?: string | null;
  autoStart?: boolean;
  error: string | null;
  onError: (message: string | null) => void;
  onOpenJump?: () => void;
};

export default function ITI({ upstream, initialDebaseResultId, autoStart, error, onError, onOpenJump }: Props) {
  const [selectedId, setSelectedId] = useState<string>(initialDebaseResultId || upstream[0]?.result_id || "");
  const [run, setRun] = useState<ItiRun | null>(null);
  const [picked, setPicked] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [inspectA, setInspectA] = useState<SuperasiBaseInspect | null>(null);
  const [inspectB, setInspectB] = useState<SuperasiDebaseInspect | null>(null);
  const [expandLoading, setExpandLoading] = useState(false);
  const autoStartedFor = useRef<string | null>(null);

  useEffect(() => {
    if (initialDebaseResultId) setSelectedId(initialDebaseResultId);
  }, [initialDebaseResultId]);

  useEffect(() => {
    if (!selectedId && upstream[0]?.result_id) setSelectedId(upstream[0].result_id);
  }, [selectedId, upstream]);

  useEffect(() => {
    if (!selectedId) return;
    let cancelled = false;
    void latestIti(selectedId)
      .then(async (found) => {
        if (cancelled) return;
        if (found && ATTACHABLE.has(found.status)) {
          setRun(found);
          setPicked(found.committed_slot_id || found.recommended_slot_id || "");
          return;
        }
        const shouldStart =
          Boolean(autoStart) &&
          Boolean(initialDebaseResultId) &&
          selectedId === initialDebaseResultId &&
          autoStartedFor.current !== selectedId;
        if (shouldStart) {
          autoStartedFor.current = selectedId;
          const body = await runIti(selectedId);
          if (cancelled) return;
          setRun(body);
          setPicked(body.recommended_slot_id || "");
          return;
        }
        setRun(found);
        setPicked(found?.committed_slot_id || found?.recommended_slot_id || "");
      })
      .catch((err) => {
        if (!cancelled) onError(err instanceof Error ? err.message : String(err));
      });
    return () => {
      cancelled = true;
    };
  }, [autoStart, initialDebaseResultId, onError, selectedId]);

  useEffect(() => {
    if (!run?.run_id) return;
    if (run.status === "COMPLETE" || run.status === "FAILED" || run.status === "CANCELLED") return;
    const tick = window.setInterval(() => {
      void getItiRun(run.run_id)
        .then((next) => {
          setRun(next);
          if (!picked && next.recommended_slot_id) setPicked(next.recommended_slot_id);
        })
        .catch((err) => onError(err instanceof Error ? err.message : String(err)));
    }, 1500);
    return () => window.clearInterval(tick);
  }, [onError, picked, run]);

  const selected = useMemo(
    () => upstream.find((row) => row.result_id === selectedId) || null,
    [selectedId, upstream],
  );
  const pickedSlot = run?.slots.find((s) => s.slot_id === picked);
  const canSave = Boolean(pickedSlot?.status === "COMPLETE");

  const onRun = () => {
    if (!selectedId) return;
    setBusy(true);
    setNote(null);
    onError(null);
    void runIti(selectedId)
      .then((body) => {
        setRun(body);
        setPicked(body.recommended_slot_id || "");
      })
      .catch((err) => onError(err instanceof Error ? err.message : String(err)))
      .finally(() => setBusy(false));
  };

  const onSave = () => {
    if (!run?.run_id || !picked) return;
    setBusy(true);
    onError(null);
    void commitIti(run.run_id, picked)
      .then((body) => {
        const folder =
          body.iti_folder ||
          (body.source_folder && body.strategy_name ? `${body.source_folder}/${body.strategy_name}` : "");
        setNote(
          folder
            ? `Saved ${body.strategy_name || picked} at ${folder}. Open in Jump to browse the pointer.`
            : `Saved ${body.strategy_name || picked} under the source Phase B folder.`,
        );
        return getItiRun(run.run_id);
      })
      .then((next) => setRun(next))
      .catch((err) => onError(err instanceof Error ? err.message : String(err)))
      .finally(() => setBusy(false));
  };

  const onExpand = (slot: ItiSlot) => {
    if (slot.status !== "COMPLETE") return;
    if (expandedId === slot.slot_id) {
      setExpandedId(null);
      setInspectA(null);
      setInspectB(null);
      return;
    }
    setExpandedId(slot.slot_id);
    setInspectA(null);
    setInspectB(null);
    if (!slot.phase_a_result_id || !slot.phase_b_result_id) {
      onError("Slot SuperASI A/B ids are missing. Inspect stays closed.");
      return;
    }
    setExpandLoading(true);
    onError(null);
    void Promise.all([getBaseResult(slot.phase_a_result_id), getDebaseResult(slot.phase_b_result_id)])
      .then(([a, b]) => {
        setInspectA(a);
        setInspectB(b);
      })
      .catch((err) => onError(err instanceof Error ? err.message : String(err)))
      .finally(() => setExpandLoading(false));
  };

  return (
    <div className="sa-page ju-iti-layout">
      <div className="ju-iti-main">
        <header className="stax-count-head">
          <p className="ws-kicker">SuperASI · after Final Results</p>
          <h1 className="v2-page-title">Ian Taleb Index</h1>
          <p className="v2-lede">
            25 entry/exit price variants (±5% of current cents, up to 3 steps). Same ROLLER ops. Ranked
            by SuperASI DEBASE then BASE. You pick which one to keep.
          </p>
        </header>

        <section className="ws-honesty" aria-label="ITI honesty">
          <p className="muted small">RESEARCH ONLY · CANDLE PATH ≠ FILL · LIVE EXECUTION = FALSE</p>
          <p className="muted small">2% confirmation = OPERATION_REQUIRED · Pyramiding = OPERATION_REQUIRED</p>
          <p className="muted small">Recommended grade is not a fill and is not auto-committed.</p>
        </section>

        {error ? <p className="sa-error">{error}</p> : null}
        {note ? <p className="muted">{note}</p> : null}

        <div className="ws-labs-toolbar">
          <label>
            SuperASI Final Result
            <select value={selectedId} onChange={(e) => setSelectedId(e.target.value)}>
              {upstream.length === 0 ? <option value="">None</option> : null}
              {upstream.map((row) => (
                <option key={row.result_id} value={row.result_id}>
                  {row.strategy_name} · BASE {row.BASE_GRADE || "—"} · DEBASE {row.DEBASE_GRADE || "—"}
                </option>
              ))}
            </select>
          </label>
          <button type="button" className="btn-primary" onClick={onRun} disabled={!selectedId || busy}>
            {busy && !run ? "Starting…" : "Run ITI"}
          </button>
          <button type="button" className="btn-primary" onClick={onSave} disabled={!canSave || busy}>
            Save {picked || "selection"}
          </button>
          {onOpenJump ? (
            <button type="button" className="btn-secondary" onClick={() => onOpenJump()}>
              Open in Jump
            </button>
          ) : null}
        </div>

        {selected ? (
          <p className="muted small">
            Source {selected.folder || selected.result_id}. Parent Roller / SuperASI A / SuperASI B files
            are not rewritten.
          </p>
        ) : (
          <p className="muted">Select a SuperASI Final Result to build the catalog.</p>
        )}

        {run ? (
          <p className="muted small">
            {run.status} · {run.progress_done || 0}/{run.slot_n || 25}
            {run.recommended_slot_id ? ` · recommended ${run.recommended_slot_id}` : ""}
            {run.status !== "COMPLETE"
              ? " · completed slots can be saved now; the other variants keep measuring"
              : ""}
          </p>
        ) : (
          <p className="muted small">Save stays disabled until a completed slot is selected.</p>
        )}

        {run ? (
          <ul className="ju-iti-slots" aria-label="ITI slots">
            {run.slots.map((slot) => {
              const complete = slot.status === "COMPLETE";
              const open = expandedId === slot.slot_id;
              return (
                <li key={slot.slot_id} className={open ? "on" : undefined}>
                  <div className="ju-iti-slot-row">
                    <input
                      type="radio"
                      name="iti-slot"
                      checked={picked === slot.slot_id}
                      disabled={!complete}
                      onChange={() => setPicked(slot.slot_id)}
                      aria-label={`Select ${slot.slot_id}`}
                    />
                    {complete ? (
                      <button type="button" className="ju-iti-slot-open" onClick={() => onExpand(slot)}>
                        <strong>
                          {slot.slot_id}
                          {run.recommended_slot_id === slot.slot_id ? " · rec" : ""}
                        </strong>
                        <span>
                          {slot.entry_cents ?? "—"} / {slot.win_cents ?? "—"} / {slot.loss_cents ?? "—"} ¢ · N=
                          {slot.population ?? "—"}
                        </span>
                        <span>
                          BASE {slot.BASE_GRADE || "—"} · DEBASE {slot.DEBASE_GRADE || "—"}
                        </span>
                        <span>{open ? "Hide SuperASI A + B" : "Open SuperASI A + B"}</span>
                      </button>
                    ) : (
                      <div className="ju-iti-slot-meta">
                        <strong>
                          {slot.slot_id}
                          {run.recommended_slot_id === slot.slot_id ? " · rec" : ""}
                        </strong>
                        <span>
                          {slot.entry_cents ?? "—"} / {slot.win_cents ?? "—"} / {slot.loss_cents ?? "—"} ¢ · N=
                          {slot.population ?? "—"}
                        </span>
                        <span>
                          BASE {slot.BASE_GRADE || "—"} · DEBASE {slot.DEBASE_GRADE || "—"}
                        </span>
                        <span>
                          {slot.status}
                          {slot.skip_reason ? ` · ${slot.skip_reason}` : ""}
                        </span>
                      </div>
                    )}
                  </div>
                  {open ? (
                    <div className="ju-iti-slot-inspect">
                      {expandLoading ? <p className="muted small">Loading SuperASI A and SuperASI B…</p> : null}
                      {inspectA ? <SuperasiAResults inspect={inspectA} /> : null}
                      {inspectB ? <SuperasiBResults inspect={inspectB} /> : null}
                    </div>
                  ) : null}
                </li>
              );
            })}
          </ul>
        ) : null}
      </div>
      <aside className="ju-iti-aside">
        <p className="v2-kicker">Catalog</p>
        <p className="muted small">Full expansion is coming soon.</p>
      </aside>
    </div>
  );
}
