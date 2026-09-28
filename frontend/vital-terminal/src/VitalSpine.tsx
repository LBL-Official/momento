import { VITAL_NAV, type VitalRoute } from "./navigation";
import { toneForLifecycle } from "./format";

type Props = {
  route: VitalRoute;
  botId: string;
  sport: string;
  lifecycle: string;
  health: string;
  onNavigate: (route: VitalRoute) => void;
};

export default function VitalSpine({ route, botId, sport, lifecycle, health, onNavigate }: Props) {
  const activeIndex = VITAL_NAV.findIndex((s) => s.id === route);
  return (
    <aside className="ws-research-sidebar mm-spine" aria-label="Vital spine">
      <div className="mm-spine-block">
        <p className="mm-rail-label">Focus</p>
        <button type="button" className="mm-spine-object" onClick={() => onNavigate("detail")}>
          {botId}
        </button>
        <p className="mm-spine-detail">{sport || "—"}</p>
        <p className={`mm-spine-detail vital-tone ${toneForLifecycle(lifecycle)}`}>{lifecycle}</p>
        <p className="mm-spine-detail">Health {health}</p>
      </div>

      <div className="mm-spine-block mm-spine-sequence-block">
        <p className="mm-rail-label">Desk</p>
        <ol className="mm-sequence">
          {VITAL_NAV.map((step, i) => {
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
        <p className="mm-rail-label">Keys</p>
        <p className="mm-spine-detail">1–5 pages · R read · O observe</p>
        <p className="mm-spine-detail">[ ] previous / next unit</p>
      </div>

      <div className="mm-spine-block">
        <p className="mm-rail-label">Honesty</p>
        <p className="mm-spine-detail">HTTP 200 ≠ RUNNING</p>
        <p className="mm-spine-detail">START ≠ LIVE ARM</p>
        <p className="mm-spine-detail">KILL ≠ STOP</p>
        <p className="mm-spine-detail">MISSING ≠ ZERO</p>
        <p className="mm-spine-detail">TOP-LEVEL ≠ SHARD 3</p>
      </div>
    </aside>
  );
}
