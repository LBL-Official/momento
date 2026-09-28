import AdverseTerminalPanel from "./components/AdverseTerminalPanel";
import MeasurementIdentity from "./components/MeasurementIdentity";
import ResearchQuestionHeader from "./components/ResearchQuestionHeader";
import FeeScenarioPanel from "./components/FeeScenarioPanel";
import FillAlgorithmPanel from "./components/FillAlgorithmPanel";
import type { DetailPayload } from "../v2/components/DetailDrawer";
import type {
  AdverseP,
  Decomp,
  FeeScenario,
  FillAlgorithm,
  PackageIdentity,
} from "./types/superasi";

const LAYERS = [
  "0 source / outcome",
  "1 four-cell or path-only S",
  "2 exit-loss (80/40-style mixes)",
  "3 estimated maker / taker fees",
  "4 adverse p (needs settlement)",
  "5 path geometry",
  "6 liquidity (FAST_GAP = TAKER)",
  "7 combined research EV",
];

type Props = {
  pkg?: PackageIdentity | null;
  decomp?: Decomp | null;
  fill: FillAlgorithm;
  fee: FeeScenario;
  adverse: AdverseP;
  busy?: boolean;
  onFill: (id: FillAlgorithm) => void;
  onFee: (id: FeeScenario) => void;
  onAdverse: (id: AdverseP) => void;
  onOpenDetail: (detail: DetailPayload) => void;
  onOpenResults: () => void;
};

export default function Decompose({
  pkg,
  decomp,
  fill,
  fee,
  adverse,
  busy,
  onFill,
  onFee,
  onAdverse,
  onOpenDetail,
  onOpenResults,
}: Props) {
  return (
    <div className="sa-page">
      <header className="stax-count-head">
        <p className="ws-kicker">Deterministic · no RNG · no clustering</p>
        <h1 className="ws-title">Decompose</h1>
        <p className="muted small">
          Settings never mutate package.json or the observation file. decomp.json is the derived
          write. Changing a mix or fee must not change S. DECOMPOSITION ≠ SIGNAL.
        </p>
      </header>

      {pkg ? (
        <section className="sa-active">
          <ResearchQuestionHeader pkg={pkg} decomp={decomp} />
          <div className="stax-metric-row">
            <div>
              <div className="muted small">PACKAGE</div>
              <div className="evidence">{pkg.package_id}</div>
            </div>
            <div>
              <div className="muted small">N</div>
              <div className="evidence">{pkg.population_n ?? "—"}</div>
            </div>
            <div>
              <div className="muted small">SOURCE</div>
              <div className="evidence">{pkg.source || "—"}</div>
            </div>
            <div>
              <div className="muted small">LIVE EXECUTION</div>
              <div className="evidence">{String(pkg.live_execution)}</div>
            </div>
          </div>
          <MeasurementIdentity pkg={pkg} decomp={decomp} compact />
          {busy ? <p className="muted small">Rewriting decomp.json…</p> : null}
        </section>
      ) : (
        <p className="stax-empty muted">Import or seed a measurement first.</p>
      )}

      <section className="sa-layers-block">
        <p className="ws-kicker">Decomposition layers</p>
        <ol className="stax-ledger sa-layers">
          {LAYERS.map((label, i) => (
            <li key={label} className="stax-ledger-row">
              <span className="stax-ledger-index">{String(i).padStart(2, "0")}</span>
              <span className="stax-ledger-name">{label}</span>
            </li>
          ))}
        </ol>
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

      <section className="ws-level">
        <button type="button" className="btn-primary" onClick={onOpenResults} disabled={!pkg || busy}>
          Open Results
        </button>
      </section>
    </div>
  );
}
