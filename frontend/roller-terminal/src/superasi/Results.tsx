import type { DetailPayload } from "../v2/components/DetailDrawer";
import AdverseTerminalPanel from "./components/AdverseTerminalPanel";
import MeasurementIdentity from "./components/MeasurementIdentity";
import ResearchQuestionHeader from "./components/ResearchQuestionHeader";
import FeeScenarioPanel from "./components/FeeScenarioPanel";
import FillAlgorithmPanel from "./components/FillAlgorithmPanel";
import PathLossPanel from "./components/PathLossPanel";
import TradeTable from "./components/TradeTable";
import { fmtCents, fmtFrac, fmtPct } from "./format";
import type {
  AdverseP,
  Decomp,
  FeeScenario,
  FillAlgorithm,
  PackageGet,
} from "./types/superasi";

type Props = {
  loaded: PackageGet | null;
  decomp: Decomp | null;
  fill: FillAlgorithm;
  fee: FeeScenario;
  adverse: AdverseP;
  busy?: boolean;
  onFill: (id: FillAlgorithm) => void;
  onFee: (id: FeeScenario) => void;
  onAdverse: (id: AdverseP) => void;
  onOpenDetail: (detail: DetailPayload) => void;
};

export default function Results({
  loaded,
  decomp,
  fill,
  fee,
  adverse,
  busy,
  onFill,
  onFee,
  onAdverse,
  onOpenDetail,
}: Props) {
  const four = decomp?.four_cell;
  const mix = decomp?.active_mix;
  const n = loaded?.population_n ?? four?.n;
  return (
    <div className="sa-page">
      <header className="stax-count-head">
        <p className="ws-kicker">What happened</p>
        <h1 className="ws-title">Results</h1>
        {busy ? <p className="muted small">Rewriting decomp.json…</p> : null}
      </header>

      <ResearchQuestionHeader pkg={loaded?.package} decomp={decomp} />
      <MeasurementIdentity pkg={loaded?.package} decomp={decomp} compact />

      <section className="sa-answer" aria-label="Identities">
        <div className="stax-metric-row">
          <div>
            <div className="muted small">N</div>
            <div className="evidence">{n ?? "—"}</div>
          </div>
          <div>
            <div className="muted small">S · HEADLINE WR</div>
            <div className="evidence">
              {fmtFrac(four?.S)} · {fmtPct(four?.S)}
            </div>
            <div className="muted small">not terminal p</div>
          </div>
          <div>
            <div className="muted small">p · TERMINAL</div>
            <div className="evidence">
              {four?.p?.status === "UNAVAILABLE"
                ? "UNAVAILABLE"
                : `${fmtFrac(four?.p)} · ${fmtPct(four?.p)}`}
            </div>
            <div className="muted small">
              {four?.p?.status === "UNAVAILABLE"
                ? "settlement missing; not invented as NO"
                : "not S"}
            </div>
          </div>
          <div>
            <div className="muted small">FOUR-CELL</div>
            <div className="evidence">
              {four?.status === "PATH_ONLY" || four?.cells?.W_and_not_T40 == null
                ? "UNAVAILABLE"
                : four
                  ? `${four.cells.W_and_not_T40} / ${four.cells.W_and_T40} / ${four.cells.L_and_not_T40} / ${four.cells.L_and_T40}`
                  : "—"}
            </div>
            <div className="muted small">
              {four?.status === "PATH_ONLY" || four?.cells?.W_and_not_T40 == null
                ? "S is path survival only"
                : "W¬T40 / WT40 / L¬T40 / LT40"}
            </div>
          </div>
        </div>
        <div className="stax-metric-row">
          <div>
            <div className="muted small">ENTRY / G</div>
            <div className="evidence">
              {decomp?.entry_cents != null ? `${decomp.entry_cents}¢` : "—"} · G{" "}
              {decomp?.gain_cents != null ? `${decomp.gain_cents}¢` : "—"}
            </div>
            <div className="muted small">{decomp?.gain_status || "—"}</div>
          </div>
          <div>
            <div className="muted small">GROSS / PRE-SUPERASI</div>
            <div>
              {decomp?.gross_pre_superasi?.label || "Copied from ROLLER when present. Never relabeled net."}
            </div>
          </div>
          <div>
            <div className="muted small">HEADLINE RESEARCH EV</div>
            <div className="evidence">
              {mix?.EV ? `${fmtFrac(mix.EV)} (${fmtCents(mix.EV)})` : "—"}
            </div>
            <div className="muted small">mix {fill}</div>
          </div>
        </div>
      </section>

      <FillAlgorithmPanel
        active={fill}
        mixes={decomp?.fill_algorithms}
        onChange={onFill}
        onOpenDetail={onOpenDetail}
      />
      <FeeScenarioPanel
        active={fee}
        fees={decomp?.fees}
        net={decomp?.net_estimate}
        onChange={onFee}
        onOpenDetail={onOpenDetail}
      />
      <AdverseTerminalPanel
        active={adverse}
        adverse={decomp?.adverse_terminal}
        onChange={onAdverse}
        onOpenDetail={onOpenDetail}
      />
      <PathLossPanel windows={decomp?.path_windows} onOpenDetail={onOpenDetail} />

      {loaded ? (
        <TradeTable
          trades={loaded.trades}
          windows={loaded.path_windows}
          onOpenDetail={onOpenDetail}
        />
      ) : (
        <p className="muted">No package loaded.</p>
      )}
    </div>
  );
}
