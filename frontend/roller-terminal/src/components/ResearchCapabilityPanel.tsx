import type {
  ResearchCapabilityPreview,
  ResearchCapabilitiesPayload,
} from "../researchCapabilityPreview";

type Props = {
  preview: ResearchCapabilityPreview | null;
  capabilities: ResearchCapabilitiesPayload | null;
  loading: boolean;
  error: string | null;
};

function mark(status: string): string {
  if (status === "IMPLEMENTED") return "✓";
  if (status === "REGISTERED" || status === "NOT_CONSTRUCTIBLE") return "○";
  if (status === "UNSUPPORTED" || status === "UNKNOWN") return "?";
  return "—";
}

export default function ResearchCapabilityPanel({
  preview,
  capabilities,
  loading,
  error,
}: Props) {
  return (
    <section className="capability-panel">
      <h2>Execution Capability Preview</h2>
      <div className="muted small epistemic-label">
        REGISTRY PREVIEW · NOT VALIDATION · NOT EXECUTION
      </div>
      <div className="muted small">
        CAPABILITY ≠ CONSTRUCTIBILITY ≠ EXECUTION
      </div>

      {loading ? (
        <div className="notice">LOADING REGISTERED CAPABILITIES…</div>
      ) : null}

      {error ? (
        <div className="notice">
          CAPABILITY PREVIEW UNAVAILABLE
          <div className="muted small">
            The authoritative validation and execution routes remain available.
          </div>
          <div className="muted small">{error}</div>
        </div>
      ) : null}

      {!loading && !error && !capabilities ? (
        <div className="muted">No capability registry loaded.</div>
      ) : null}

      {!loading && !error && preview ? (
        <>
          <h3>Population</h3>
          <div className="capability-block">
            {preview.population.family ? (
              <>
                <div className="mono">{preview.population.family}</div>
                <div className="mono muted small">
                  {preview.population.requestedDefinitionVersion ?? "—"}
                </div>
                <div className={`cap-status cap-${preview.population.status}`}>
                  {preview.population.status}
                </div>
                {preview.population.reason ? (
                  <div className="muted small">{preview.population.reason}</div>
                ) : null}
              </>
            ) : (
              <div className="muted">NO EXPLICIT REGISTERED POPULATION BINDING</div>
            )}
          </div>

          <h3>Measurements</h3>
          {preview.measurements.length === 0 ? (
            <div className="muted">No measurement_requests on current spec</div>
          ) : (
            <ul className="capability-list">
              {preview.measurements.map((m) => (
                <li key={`${m.name}-${m.status}`}>
                  <span className="cap-mark">{mark(m.status)}</span>
                  <span className="mono">{m.name}</span>
                  <div className={`cap-status cap-${m.status}`}>
                    {m.status}
                    {m.kind ? ` · ${m.kind.replace(/_/g, " ")}` : ""}
                  </div>
                  {m.definitionVersion ? (
                    <div className="muted small mono">{m.definitionVersion}</div>
                  ) : null}
                  {m.reason ? <div className="muted small">{m.reason}</div> : null}
                </li>
              ))}
            </ul>
          )}

          <div className="muted small" style={{ marginTop: "0.55rem" }}>
            Preview never mutates research_spec · Executor remains authoritative
          </div>
        </>
      ) : null}
    </section>
  );
}
