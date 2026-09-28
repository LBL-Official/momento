import type { LifecycleStage } from "../researchLifecycle";

/** Quiet derived lifecycle — typography only, no boxed badges. */
export default function ResearchLifecycle({ stages }: { stages: LifecycleStage[] }) {
  return (
    <div className="lifecycle" aria-label="Research lifecycle">
      <div className="lifecycle-stages">
        {stages.map((s, i) => (
          <div key={s.id} className={`lifecycle-stage ${s.active ? "on" : ""}`}>
            {i > 0 ? <span className="lifecycle-rule">·</span> : null}
            <span className="lifecycle-name">{s.label}</span>
            <span className={`status-badge tone-${s.active ? "active" : "neutral"}`}>
              {s.state}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
