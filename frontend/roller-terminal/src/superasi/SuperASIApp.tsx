import { useCallback, useEffect, useRef, useState } from "react";
import DetailDrawer, { type DetailPayload } from "../v2/components/DetailDrawer";
import {
  downloadBaseCsv,
  downloadDebaseAbaseCsv,
  downloadDebaseCsv,
  downloadDebaseRollerCsv,
  advanceLabToFinal,
  downloadRollerCopy,
  getBaseResult,
  getDebaseResult,
  listBaseResults,
  listBaseSources,
  listDebaseResults,
  runSuperasiBase,
  runSuperasiDebase,
} from "./api/superasiApi";
import BaseRun from "./BaseRun";
import DebaseRun from "./DebaseRun";
import { errorMessage } from "./format";
import ITI from "./ITI";
import LabsPhaseA from "./LabsPhaseA";
import LabsPhaseB from "./LabsPhaseB";
import { matchPhaseAResult, matchPhaseBResult } from "./selection";
import Sources from "./Sources";
import SuperASISpine from "./SuperASISpine";
import type {
  SuperasiBaseInspect,
  SuperasiBaseResult,
  SuperasiDebaseInspect,
  SuperasiDebaseResult,
  SuperasiLabSource,
  SuperasiRoute,
} from "./types/superasi";

type Props = {
  initialPackageId?: string | null;
  importNote?: string | null;
  initialLabId?: string | null;
  onBackToRoller: () => void;
  onOpenJump: () => void;
  onOpenVital?: () => void;
};

export default function SuperASIApp({
  importNote,
  initialLabId,
  onBackToRoller,
  onOpenJump,
  onOpenVital,
}: Props) {
  const [route, setRoute] = useState<SuperasiRoute>("sources");
  const [itiDebaseId, setItiDebaseId] = useState<string | null>(null);
  const [lastDebaseId, setLastDebaseId] = useState<string | null>(null);
  const [browseDebaseId, setBrowseDebaseId] = useState<string | null>(null);
  const [labs, setLabs] = useState<SuperasiLabSource[]>([]);
  const [folders, setFolders] = useState<string[]>([]);
  const [results, setResults] = useState<SuperasiBaseResult[]>([]);
  const [debaseResults, setDebaseResults] = useState<SuperasiDebaseResult[]>([]);
  const [selected, setSelected] = useState<SuperasiLabSource | null>(null);
  const [inspect, setInspect] = useState<SuperasiBaseInspect | null>(null);
  const [debaseInspect, setDebaseInspect] = useState<SuperasiDebaseInspect | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [phaseALoading, setPhaseALoading] = useState(false);
  const [phaseBLoading, setPhaseBLoading] = useState(false);
  const [finalAInspect, setFinalAInspect] = useState<SuperasiBaseInspect | null>(null);
  const [detail, setDetail] = useState<DetailPayload | null>(null);
  const [handoffNote, setHandoffNote] = useState<string | null>(importNote || null);
  const advancedLab = useRef<string | null>(null);
  const stopHandoffUi = useRef(false);

  const refreshSources = useCallback(async () => {
    const body = await listBaseSources();
    setLabs(body.labs);
    setFolders(body.folders);
    return body;
  }, []);

  const refreshResults = useCallback(async () => {
    const body = await listBaseResults();
    setResults(body.results);
  }, []);

  const refreshDebase = useCallback(async () => {
    const body = await listDebaseResults();
    setDebaseResults(body.results);
  }, []);

  useEffect(() => {
    void refreshSources().catch((err) => setError(errorMessage(err)));
    void refreshResults().catch((err) => setError(errorMessage(err)));
    void refreshDebase().catch((err) => setError(errorMessage(err)));
  }, [refreshDebase, refreshResults, refreshSources]);

  useEffect(() => {
    if (!initialLabId || advancedLab.current === initialLabId) return;
    advancedLab.current = initialLabId;
    stopHandoffUi.current = false;
    let cancelled = false;
    setBusy(true);
    setError(null);
    setHandoffNote("Warehouse lab → SuperASI A → SuperASI B. ITI is not started.");
    setRoute("run");
    void refreshSources()
      .then((sources) => {
        if (cancelled) return;
        const lab = sources.labs.find((row) => row.lab_id === initialLabId) || null;
        if (lab) setSelected(lab);
        return advanceLabToFinal(initialLabId, {
          onUpdate: (job) => {
            if (cancelled) return;
            if (job.phase === "B") {
              setHandoffNote("Running SuperASI B. ITI is not started.");
            } else if (job.phase === "A") {
              setHandoffNote("Running SuperASI A, then B. ITI is not started.");
            }
          },
        });
      })
      .then(async (body) => {
        if (cancelled || stopHandoffUi.current || !body) return;
        if (!body.result_id) {
          throw new Error("SuperASI handoff did not return Final Results");
        }
        await Promise.all([refreshSources(), refreshResults(), refreshDebase()]);
        setLastDebaseId(body.result_id);
        setBrowseDebaseId(body.result_id);
        const inspectBody = body.inspect || (await getDebaseResult(body.result_id));
        if (cancelled) return;
        setDebaseInspect(inspectBody);
        setHandoffNote(
          body.reused_debase
            ? `Reused Final Results for ${body.strategy_name || "this lab"}. Run ITI when you want the 25-slot catalog.`
            : `Final Results ready for ${body.strategy_name || "this lab"}. Run ITI when you want the 25-slot catalog.`,
        );
        setRoute("labs_phase_b");
      })
      .catch((err) => {
        if (!cancelled && !stopHandoffUi.current) {
          setError(errorMessage(err));
          setRoute("sources");
        }
      })
      .finally(() => {
        if (!cancelled) setBusy(false);
      });
    return () => {
      cancelled = true;
    };
  }, [initialLabId, refreshDebase, refreshResults, refreshSources]);

  const selectedPhaseA = matchPhaseAResult(results, selected?.lab_id);
  const selectedPhaseB = matchPhaseBResult(debaseResults, selected?.lab_id);
  const inspectMatchesSelected =
    inspect != null && (!selected || inspect.source_lab_id === selected.lab_id);
  const justRanSelectedB =
    debaseInspect != null &&
    lastDebaseId != null &&
    debaseInspect.result_id === lastDebaseId &&
    (!selected || debaseInspect.source_lab_id === selected.lab_id);
  const viewingDebaseId = browseDebaseId || selectedPhaseB?.result_id || (justRanSelectedB ? lastDebaseId : null);
  const viewingDebase = debaseResults.find((row) => row.result_id === viewingDebaseId) || selectedPhaseB;
  const debaseInspectMatchesView =
    debaseInspect != null && viewingDebaseId != null && debaseInspect.result_id === viewingDebaseId;

  useEffect(() => {
    if (route !== "labs_phase_a" || !selected || busy) return;
    if (!selectedPhaseA) return;
    if (
      inspectMatchesSelected &&
      inspect?.result_id === selectedPhaseA.result_id &&
      inspect.desk?.source === "roller_payoff"
    ) {
      return;
    }
    let cancelled = false;
    setPhaseALoading(true);
    void getBaseResult(selectedPhaseA.result_id)
      .then((body) => {
        if (!cancelled) setInspect(body);
      })
      .catch((err) => {
        if (!cancelled) setError(errorMessage(err));
      })
      .finally(() => {
        if (!cancelled) setPhaseALoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [busy, inspect, inspectMatchesSelected, route, selected, selectedPhaseA]);

  useEffect(() => {
    if (route !== "labs_phase_b" || !viewingDebaseId || busy) return;
    if (debaseInspectMatchesView) return;
    let cancelled = false;
    setPhaseBLoading(true);
    void getDebaseResult(viewingDebaseId)
      .then((body) => {
        if (!cancelled) setDebaseInspect(body);
      })
      .catch((err) => {
        if (!cancelled) setError(errorMessage(err));
      })
      .finally(() => {
        if (!cancelled) setPhaseBLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [busy, debaseInspectMatchesView, route, viewingDebaseId]);

  useEffect(() => {
    if (route !== "labs_phase_b" || busy) return;
    const phaseAId =
      (debaseInspectMatchesView && debaseInspect?.phase_a_result_id) || viewingDebase?.phase_a_result_id;
    if (!phaseAId) return;
    if (finalAInspect?.result_id === phaseAId && finalAInspect.desk?.source === "roller_payoff") return;
    let cancelled = false;
    void getBaseResult(phaseAId)
      .then((body) => {
        if (!cancelled) setFinalAInspect(body);
      })
      .catch((err) => {
        if (!cancelled) setError(errorMessage(err));
      });
    return () => {
      cancelled = true;
    };
  }, [busy, debaseInspect, debaseInspectMatchesView, finalAInspect, route, viewingDebase]);

  const onCancelHandoff = () => {
    stopHandoffUi.current = true;
    setBusy(false);
    setHandoffNote(
      "Stopped waiting on Warehouse Move. Run SuperASI A — Base here or from 01 Roller CSVs.",
    );
    setRoute("run");
  };

  const onRun = (lab: SuperasiLabSource) => {
    stopHandoffUi.current = true;
    setBusy(true);
    setError(null);
    setSelected(lab);
    setRoute("run");
    void runSuperasiBase(lab.lab_id)
      .then((body) => {
        setInspect(body);
        return refreshResults();
      })
      .catch((err) => setError(errorMessage(err)))
      .finally(() => setBusy(false));
  };

  const onRunDebase = (row: SuperasiBaseResult) => {
    setBusy(true);
    setError(null);
    setRoute("run_debase");
    void runSuperasiDebase(row.result_id)
      .then((body) => {
        setDebaseInspect(body);
        setLastDebaseId(body.result_id);
        setBrowseDebaseId(null);
        setRoute("labs_phase_b");
        return refreshDebase();
      })
      .catch((err) => setError(errorMessage(err)))
      .finally(() => setBusy(false));
  };

  return (
    <div className="app-root ws-app sa-app">
      <header className="ws-header">
        <button
          type="button"
          className="mm-masthead-brand"
          onClick={() => setRoute("sources")}
          aria-label="SuperASI — go to Roller CSVs"
        >
          <img
            className="mm-mark"
            src="/brand/momento-m-mark.png"
            alt=""
            width={26}
            height={26}
            decoding="async"
          />
          <span className="mm-wordmark">
            <span className="mm-wordmark-product">Superasi</span>
            <span className="mm-wordmark-rule" aria-hidden />
            <span className="mm-wordmark-sub">Research Operating System</span>
          </span>
        </button>

        <div className="mm-masthead-org">Momento Systems</div>

        <div className="mm-status-strip">
          <div className="mm-status-item">
            <span className="mm-status-key">Mode</span>
            <span className="mm-status-value is-strong">RESEARCH ONLY</span>
          </div>
          <div className="mm-status-item">
            <span className="mm-status-key">Execution</span>
            <span className="mm-status-value">NOT A TRADING SYSTEM</span>
          </div>
          <div className="mm-status-item">
            <span className="mm-status-key">Upstream</span>
            <button type="button" className="mm-status-value" onClick={onBackToRoller}>
              ← ROLLER
            </button>
          </div>
          <div className="mm-status-item">
            <span className="mm-status-key">Downstream</span>
            <button type="button" className="mm-status-value" onClick={() => onOpenJump()}>
              JUMP
            </button>
            {onOpenVital ? (
              <button type="button" className="mm-status-value" onClick={() => onOpenVital()}>
                VITAL
              </button>
            ) : null}
          </div>
        </div>
      </header>

      <div className="ws-body">
        <SuperASISpine
          route={route}
          strategyLabel={
            debaseInspect?.strategy_name || selected?.strategy_name || inspect?.strategy_name || "No Phase A folder"
          }
          sourceCount={labs.length}
          resultCount={results.length}
          debaseCount={debaseResults.length}
          grade={debaseInspect?.BASE_GRADE || inspect?.BASE_GRADE || null}
          debaseGrade={debaseInspect?.DEBASE_GRADE || null}
          busy={busy}
          onNavigate={setRoute}
        />
        <div className="ws-main-col">
          <div className="ws-main-scroll sa-body">
            {error ? <p className="sa-error">{error}</p> : null}
            {handoffNote ? <p className="muted small">{handoffNote}</p> : null}
            {route === "labs_phase_a" ? (
              <LabsPhaseA
                selected={selected}
                inspect={inspectMatchesSelected ? inspect : null}
                result={selectedPhaseA}
                loading={phaseALoading}
                busy={busy}
                onOpenA={() => setRoute("run")}
                onRunDebase={onRunDebase}
                onDownloadBase={(row) =>
                  void downloadBaseCsv(row.result_id, row.abase_filename || `SuperasiABase[${row.strategy_name}].csv`)
                }
                onDownloadRoller={(row) =>
                  void downloadRollerCopy(row.result_id, row.roller_filename || `Roller[${row.strategy_name}].csv`)
                }
              />
            ) : null}
            {route === "run_debase" ? (
              <DebaseRun inspect={debaseInspect} busy={busy} onOpenFinal={() => setRoute("labs_phase_b")} />
            ) : null}
            {route === "labs_phase_b" ? (
              <LabsPhaseB
                selected={selected}
                inspect={debaseInspectMatchesView ? debaseInspect : null}
                phaseAInspect={
                  debaseInspectMatchesView &&
                  finalAInspect &&
                  finalAInspect.result_id === debaseInspect?.phase_a_result_id
                    ? finalAInspect
                    : null
                }
                result={viewingDebase || null}
                results={debaseResults}
                viewingId={viewingDebaseId}
                loading={phaseBLoading}
                busy={busy}
                onOpenA={() => setRoute("labs_phase_a")}
                onOpenB={() => setRoute("run_debase")}
                onSelectOther={(row) => {
                  setBrowseDebaseId(row.result_id);
                  const lab = labs.find((item) => item.lab_id === row.source_lab_id);
                  if (lab) setSelected(lab);
                }}
                onRefresh={() => void refreshDebase().catch((err) => setError(errorMessage(err)))}
                onDownloadDebase={(row) =>
                  void downloadDebaseCsv(
                    row.result_id,
                    row.debase_filename || `SuperasiBDeBase[${row.strategy_name}].csv`,
                  )
                }
                onDownloadAbase={(row) =>
                  void downloadDebaseAbaseCsv(
                    row.result_id,
                    row.abase_filename || `SuperasiABase[${row.strategy_name}].csv`,
                  )
                }
                onDownloadRoller={(row) =>
                  void downloadDebaseRollerCsv(
                    row.result_id,
                    row.roller_filename || `Roller[${row.strategy_name}].csv`,
                  )
                }
                onGoToIti={(resultId) => {
                  setItiDebaseId(resultId);
                  setRoute("iti");
                }}
                onOpenJump={onOpenJump}
              />
            ) : null}
            {route === "iti" ? (
              <ITI
                upstream={debaseResults.filter(
                  (row) => !/(?: ITI-\d+|_ITI)$/.test(row.strategy_name || row.result_id || ""),
                )}
                initialDebaseResultId={itiDebaseId}
                autoStart={Boolean(itiDebaseId)}
                error={error}
                onError={setError}
                onOpenJump={onOpenJump}
              />
            ) : null}
            {route === "sources" ? (
              <Sources
                labs={labs}
                folders={folders}
                selectedId={selected?.lab_id || null}
                busy={busy}
                onSelect={(lab) => {
                  setBrowseDebaseId(null);
                  setSelected(lab);
                }}
                onRun={onRun}
                onRefresh={() => void refreshSources().catch((err) => setError(errorMessage(err)))}
              />
            ) : null}
            {route === "run" ? (
              <BaseRun
                inspect={inspect}
                selected={selected}
                busy={busy}
                advancingToFinal={Boolean(initialLabId) && busy && !stopHandoffUi.current}
                onRun={onRun}
                onCancelHandoff={onCancelHandoff}
                onOpenLabs={() => setRoute("labs_phase_a")}
              />
            ) : null}
          </div>
        </div>
      </div>
      <DetailDrawer detail={detail} onClose={() => setDetail(null)} />
    </div>
  );
}
