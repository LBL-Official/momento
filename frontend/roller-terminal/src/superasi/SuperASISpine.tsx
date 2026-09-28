import { SUPERASI_NAV } from "./navigation";
import type { SuperasiRoute } from "./types/superasi";

type Props = {
  route: SuperasiRoute;
  strategyLabel: string;
  sourceCount: number;
  resultCount: number;
  debaseCount: number;
  grade: string | null;
  debaseGrade: string | null;
  busy?: boolean;
  onNavigate: (route: SuperasiRoute) => void;
};

export default function SuperASISpine({
  route,
  strategyLabel,
  sourceCount,
  resultCount,
  debaseCount,
  grade,
  debaseGrade,
  busy,
  onNavigate,
}: Props) {
  const activeIndex = SUPERASI_NAV.findIndex((s) => s.id === route);
  return (
    <aside className="ws-research-sidebar mm-spine" aria-label="SuperASI spine">
      <div className="mm-spine-block">
        <p className="mm-rail-label">Roller CSV</p>
        <button type="button" className="mm-spine-object" onClick={() => onNavigate("sources")}>
          {strategyLabel}
        </button>
        <p className="mm-spine-detail">{grade ? `BASE_GRADE ${grade}` : "Phase A evidence grade"}</p>
        <p className="mm-spine-detail">{debaseGrade ? `DEBASE_GRADE ${debaseGrade}` : "Debase after Phase A"}</p>
      </div>

      <div className="mm-spine-block">
        <p className="mm-rail-label">Libraries</p>
        <p className="mm-spine-metric">
          <span className="mm-spine-metric-k">Roller CSVs =</span>
          <span className="mm-spine-metric-v">{sourceCount}</span>
        </p>
        <p className="mm-spine-metric">
          <span className="mm-spine-metric-k">Phase A =</span>
          <span className="mm-spine-metric-v">{resultCount}</span>
        </p>
        <p className="mm-spine-metric">
          <span className="mm-spine-metric-k">Final =</span>
          <span className="mm-spine-metric-v">{debaseCount}</span>
        </p>
      </div>

      <div className="mm-spine-block mm-spine-sequence-block">
        <p className="mm-rail-label">Research sequence</p>
        <ol className="mm-sequence">
          {SUPERASI_NAV.map((step, i) => {
            const state =
              activeIndex >= 0 && i < activeIndex ? "done" : i === activeIndex ? "on" : "todo";
            return (
              <li key={step.id} className={`mm-seq is-${state}`}>
                <button
                  type="button"
                  className="mm-seq-btn"
                  onClick={() => onNavigate(step.id)}
                  aria-current={state === "on" ? "step" : undefined}
                >
                  <span className="mm-seq-index" aria-hidden>
                    {String(i + 1).padStart(2, "0")}
                  </span>
                  <span className="mm-seq-text">
                    <span className="mm-seq-label">{step.label}</span>
                    <span className="mm-seq-purpose">{step.hint}</span>
                  </span>
                </button>
              </li>
            );
          })}
        </ol>
      </div>

      <div className="mm-spine-block">
        <p className="mm-rail-label">System</p>
        <p className={`mm-spine-system ${busy ? "tone-review" : "tone-ready"}`}>
          <span className={`mm-signal ${busy ? "hold" : "live"}`} aria-hidden />
          {busy ? "Running SuperASI" : "Research only"}
        </p>
        <p className="mm-spine-detail">ROLLER measures. SuperASI grades evidence.</p>
        <p className="mm-spine-detail">MODE A ≠ LETTER GRADE</p>
        <p className="mm-spine-detail">CANDLE PATH ≠ FILL</p>
        <p className="mm-spine-detail">LIVE EXECUTION = FALSE</p>
      </div>
    </aside>
  );
}
