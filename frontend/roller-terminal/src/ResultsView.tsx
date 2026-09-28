import { useEffect, useMemo, useRef, useState } from "react";
import ResearchSpecDiffView from "./components/ResearchSpecDiff";
import ResultsCharts from "./components/ResultsCharts";
import ResultsReportBrief from "./components/ResultsReportBrief";
import AnalyticsPanel from "./v2/components/AnalyticsPanel";
import ExportMenu from "./v2/components/ExportMenu";
import { diffResearchSpecs } from "./researchDiff";
import type { Freshness, ResultSnapshot } from "./researchFreshness";
import {
  analyzeResearchCapabilities,
  type CapabilityStatus,
  type ResearchCapabilitiesPayload,
  type ResearchCapabilityPreview,
} from "./researchCapabilityPreview";
import { summaryOneLine } from "./researchSummary";
import type { Spec } from "./researchTypes";

type Measurement = {
  name?: string;
  status?: string;
  value?: number | null;
  definition_version?: string | null;
  caveat?: string | null;
  detail?: Record<string, unknown>;
  source?: { artifact?: string; field?: string } | null;
};

type Binding = {
  requested_definition_version?: string | null;
  actual_definition_version?: string | null;
  status?: string;
  reason?: string;
};

export type ResearchResult = {
  research_object_id?: string | null;
  execution_status?: string;
  elapsed_ms?: number;
  summary?: {
    population_n?: number | null;
    population_description?: string | null;
  };
  bindings?: Record<string, Binding>;
  population?: {
    status?: string;
    count?: number;
    rows?: Record<string, unknown>[];
    trades?: Record<string, unknown>[];
    rows_truncated?: boolean;
  };
  path_conditions?: { status?: string; results?: Record<string, unknown>[] };
  terminal_conditions?: { status?: string; results?: Record<string, unknown>[] };
  measurements?: Measurement[];
  empirical_partition?: {
    status?: string;
    reason?: string | null;
    axes?: { id: string; field: string; true_label: string; false_label: string }[];
    cells?: {
      key: string;
      path_true?: boolean;
      terminal_true?: boolean;
      n: number;
    }[];
    n_population?: number;
    n_joint_available?: number;
    n_missing?: number;
    path_margin?: { true: number; false: number; available: number };
    joint_measured?: boolean;
  } | null;
  provenance?: {
    definition_versions?: Record<string, unknown>;
    dataset_versions?: Record<string, unknown>;
    source_artifacts?: string[];
    entry_slice_binding?: Record<string, unknown>;
    measurement_routing?: string;
  };
  caveats?: string[];
  validation?: {
    status?: string;
    errors?: string[];
    unresolved?: { field: string; reason: string }[];
  };
};

function fmtValue(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "number") return Number.isFinite(v) ? v.toFixed(6).replace(/\.?0+$/, "") : "—";
  return String(v);
}

function fmtMeasurementValue(m: Measurement): string {
  if (m.value === null || m.value === undefined) {
    if (m.status === "NOT_CONSTRUCTIBLE") return "NOT CONSTRUCTIBLE";
    return "—";
  }
  return fmtValue(m.value);
}

function formatSource(source: Measurement["source"]) {
  if (!source) return "—";
  const artifact = source.artifact ?? "";
  const short = artifact.includes("/") ? artifact.split("/").slice(-1)[0] : artifact;
  return (
    <span className="source-cell mono">
      <span className="source-artifact">{short || "—"}</span>
      {source.field ? <span className="source-field">field: {source.field}</span> : null}
    </span>
  );
}

/** Preview status vs executor status — compatible pairs are not disagreements. */
function previewAgreesWithActual(preview: CapabilityStatus, actual: string): boolean {
  if (preview === "IMPLEMENTED") {
    return actual === "COMPLETE" || actual === "IMPLEMENTED" || actual === "PARTIAL";
  }
  if (preview === "REGISTERED" || preview === "NOT_CONSTRUCTIBLE") {
    return (
      actual === "NOT_CONSTRUCTIBLE" ||
      actual === "REGISTERED_NOT_EXECUTABLE" ||
      actual === "REGISTERED"
    );
  }
  if (preview === "UNSUPPORTED") return actual === "UNSUPPORTED";
  if (preview === "ABSENT" || preview === "ABSENT_IF_UNAVAILABLE") {
    return actual === "ABSENT" || actual === "ABSENT_IF_UNAVAILABLE";
  }
  return preview === actual;
}

function proportionBlock(title: string, label: string, m: Measurement | undefined) {
  if (!m) return null;
  const d = m.detail || {};
  const trueN = typeof d.count_true === "number" ? d.count_true : null;
  const avail = typeof d.count_available === "number" ? d.count_available : null;
  return (
    <div className="measurement-block proportion-block">
      <div className="measurement-label proportion-label">{label}</div>
      <div className="meta">
        <span>{title}</span>
        <span className={`status-${m.status}`}>{m.status}</span>
      </div>
      {trueN != null && avail != null ? (
        <div className="measurement-meta proportion-nums evidence">
          {trueN} / {avail}
        </div>
      ) : null}
      <div className="measurement-value proportion-value evidence">{fmtValue(m.value)}</div>
      {m.source ? (
        <div className="measurement-meta muted small">
          {m.source.artifact}
          {m.source.field ? ` · ${m.source.field}` : ""}
        </div>
      ) : null}
    </div>
  );
}

function conditionMass(title: string, payload: unknown) {
  const empty =
    payload == null ||
    (typeof payload === "object" &&
      !Array.isArray(payload) &&
      Object.keys(payload as object).length === 0) ||
    (Array.isArray(payload) && payload.length === 0);
  if (empty) {
    return <div className="conditional-structure empty">NO CONDITIONS DEFINED</div>;
  }
  return (
    <div className="conditional-structure">
      <div className="muted small" style={{ marginBottom: "0.35rem" }}>
        {title}
      </div>
      <pre className="condition-expr spec-json" style={{ margin: 0, maxHeight: "12rem" }}>
        {JSON.stringify(payload, null, 2)}
      </pre>
    </div>
  );
}

export default function ResultsView({
  resultSnapshot,
  currentSpec,
  currentSpecFingerprint,
  executionFreshness,
  validationFreshness,
  capabilities,
  capabilityPreview,
  onReturnToResearchObject,
}: {
  resultSnapshot: ResultSnapshot | null;
  currentSpec: Spec;
  currentSpecFingerprint: string;
  executionFreshness: Freshness;
  validationFreshness: Freshness;
  capabilities: ResearchCapabilitiesPayload | null;
  capabilityPreview: ResearchCapabilityPreview | null;
  onReturnToResearchObject?: () => void;
}) {
  const [showDiff, setShowDiff] = useState(false);
  const [resultsTab, setResultsTab] = useState<"report" | "analytics" | "export">("report");
  const headingRef = useRef<HTMLHeadingElement | null>(null);
  const result = resultSnapshot?.payload ?? null;
  const executedSpec = resultSnapshot?.spec ?? null;

  const vsExecuted = useMemo(
    () => diffResearchSpecs(currentSpec, executedSpec),
    [currentSpec, executedSpec],
  );

  // Preview against the executed spec when available — never mutates result payload.
  const previewForExecuted = useMemo(() => {
    if (!executedSpec || !capabilities) return capabilityPreview;
    return analyzeResearchCapabilities(executedSpec, capabilities);
  }, [executedSpec, capabilities, capabilityPreview]);

  useEffect(() => {
    if (!result) return;
    requestAnimationFrame(() => {
      headingRef.current?.focus();
      headingRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    });
  }, [result?.research_object_id, resultSnapshot?.specFingerprint]);

  if (!result) {
    return (
      <section className="research-object">
        <div className="empty-state">
          <div className="empty-title">NO EMPIRICAL RESULT</div>
          <p className="muted">
            Validate a research object and execute an authoritative route.
          </p>
          <p className="muted small">
            A valid research object may still contain measurements that are not currently
            constructible.
          </p>
        </div>
        {onReturnToResearchObject ? (
          <button type="button" className="btn-secondary" onClick={onReturnToResearchObject}>
            RETURN TO RESEARCH OBJECT
          </button>
        ) : null}
      </section>
    );
  }

  const isStale = executionFreshness === "STALE";
  const hasSpecSnapshot = Boolean(executedSpec);
  const rows = result.population?.rows ?? [];
  const bindings = result.bindings ?? {};
  const measurements = result.measurements ?? [];
  const caveats = result.caveats ?? [];
  const byName = Object.fromEntries(measurements.map((m) => [m.name, m]));
  const t40 = byName.t40_rate;
  const kalshi = byName.kalshi_yes_rate;
  const provenance = result.provenance ?? {};
  const entryBind = provenance.entry_slice_binding;
  const populationCols = [
    "ticker",
    "game_date",
    "team",
    "status",
    "entry_price_e4",
    "expiration_result_yes",
    "dataset_split",
  ].filter((k) => rows[0] && k in rows[0]);
  const displayCols =
    populationCols.length > 0
      ? populationCols
      : Object.keys(rows[0] || {}).slice(0, 7);

  return (
    <div className="results-layout">
      <div className="row results-toolbar">
        {onReturnToResearchObject ? (
          <button type="button" className="btn-secondary" onClick={onReturnToResearchObject}>
            ← Research object
          </button>
        ) : null}
        {result.elapsed_ms != null ? (
          <span className="muted small evidence">{result.elapsed_ms} ms</span>
        ) : null}
      </div>

      <nav className="v2-mode-nav" aria-label="Results sections">
        <button
          type="button"
          className={resultsTab === "report" ? "v2-mode on" : "v2-mode"}
          onClick={() => setResultsTab("report")}
        >
          Report
        </button>
        <button
          type="button"
          className={resultsTab === "analytics" ? "v2-mode on" : "v2-mode"}
          onClick={() => setResultsTab("analytics")}
        >
          Analytics
        </button>
        <button
          type="button"
          className={resultsTab === "export" ? "v2-mode on" : "v2-mode"}
          onClick={() => setResultsTab("export")}
        >
          Export
        </button>
      </nav>

      {resultsTab === "analytics" ? <AnalyticsPanel result={result} /> : null}
      {resultsTab === "export" ? (
        <ExportMenu spec={executedSpec || currentSpec} result={result} />
      ) : null}

      {resultsTab === "report" ? (
        <>
      {result.execution_status === "ABSENT" ? (
        <section className="research-object error-panel">
          <h2>EXECUTION ABSENT</h2>
          <div className="muted">No authoritative artifact available.</div>
        </section>
      ) : null}

      <ResultsReportBrief
        titleRef={headingRef}
        spec={executedSpec}
        populationN={result.population?.count ?? result.summary?.population_n}
        populationDescription={result.summary?.population_description}
        t40={t40}
        kalshi={kalshi}
        executionStatus={result.execution_status}
        isStale={isStale}
      />

      <ResultsCharts
        populationN={result.population?.count ?? result.summary?.population_n}
        t40={t40}
        kalshi={kalshi}
      />

      {isStale || !hasSpecSnapshot ? (
        <section className={`research-object ${isStale ? "stale-banner stale-workflow" : ""}`}>
          <h2>Execution Continuity</h2>
          {!hasSpecSnapshot ? (
            <div className="notice">RESULT SNAPSHOT CONTEXT ABSENT</div>
          ) : (
            <>
              <div className="empty-title">CURRENT SPEC CHANGED</div>
              <div>RESULT BELOW IS A PRIOR EMPIRICAL RESULT</div>
              <p className="muted small">
                This result is not invalid — it answers a prior question. Navigation does not restore
                the executed spec.
              </p>
              <div className="continuity-compare">
                <div>
                  <div className="context-k">Executed</div>
                  <div className="muted small wrap-id">{summaryOneLine(executedSpec)}</div>
                </div>
                <div>
                  <div className="context-k">Current</div>
                  <div className="muted small wrap-id">{summaryOneLine(currentSpec)}</div>
                </div>
              </div>
              <div className="meta">
                <span className="mono wrap-id">
                  EXECUTED OBJECT ID: {result.research_object_id ?? "null"}
                </span>
                <span>CURRENT SPEC STATUS: {validationFreshness}</span>
              </div>
              <button
                type="button"
                className="btn-secondary"
                onClick={() => setShowDiff((v) => !v)}
              >
                {showDiff ? "HIDE DIFFERENCES" : "VIEW SPEC DIFFERENCES"}
              </button>
              {showDiff ? (
                <ResearchSpecDiffView title="CURRENT vs EXECUTED" diff={vsExecuted} />
              ) : null}
            </>
          )}
        </section>
      ) : (
        <p className="muted small results-fp mono wrap-id">
          {result.research_object_id ?? "—"} · fp {currentSpecFingerprint}
        </p>
      )}

      <details className="research-object results-details">
        <summary>Conditions &amp; measurement detail</summary>
        <div className="results-pair">
          <div>
            <h3>Path</h3>
            {conditionMass("CONDITION", executedSpec?.path_conditions ?? [])}
            {proportionBlock(t40?.name ?? "t40_rate", "PATH PROPORTION", t40)}
          </div>
          <div>
            <h3>Terminal</h3>
            {conditionMass("CONDITION", executedSpec?.terminal_conditions ?? [])}
            {proportionBlock(kalshi?.name ?? "kalshi_yes_rate", "TERMINAL YES PROPORTION", kalshi)}
          </div>
        </div>
        <h3>Measurements</h3>
        {(() => {
          const disagreements =
            previewForExecuted?.measurements.filter((pm) => {
              const actual = byName[pm.name];
              if (!actual?.status) return false;
              return !previewAgreesWithActual(pm.status, String(actual.status));
            }) ?? [];
          if (disagreements.length === 0) return null;
          return (
            <div className="capability-vs-actual">
              <div className="muted small epistemic-label">
                PREVIEW ≠ EXECUTION · EXECUTOR AUTHORITATIVE
              </div>
              <ul className="capability-list">
                {disagreements.map((pm) => {
                  const actual = byName[pm.name];
                  return (
                    <li key={`disagree-${pm.name}`}>
                      <span className="mono">{pm.name}</span>
                      <div className="muted small">
                        preview {pm.status}
                        {pm.reason ? ` · ${pm.reason}` : ""}
                      </div>
                      <div className="cap-status cap-actual">
                        actual {actual?.status} (authoritative)
                      </div>
                    </li>
                  );
                })}
              </ul>
            </div>
          );
        })()}
        {measurements.length === 0 ? (
          <div className="muted">None</div>
        ) : (
          <div className="measurement-cards">
            {measurements.map((m) => (
              <article key={String(m.name)} className="measurement-card">
                <div className="measurement-card-top">
                  <span className="mono">{m.name}</span>
                  <span className={`status-${m.status}`}>{m.status}</span>
                </div>
                <div className="measurement-value evidence">{fmtMeasurementValue(m)}</div>
                <div className="muted small mono">{m.definition_version ?? "—"}</div>
                <div className="muted small">{formatSource(m.source)}</div>
                {m.caveat ? <p className="measurement-caveat muted small">{m.caveat}</p> : null}
              </article>
            ))}
          </div>
        )}
      </details>

      <details className="research-object results-details results-population">
        <summary>
          Population rows · N = {result.population?.count ?? "—"}
          {rows.length > 0
            ? ` · ${Math.min(50, rows.length)} shown${
                result.population?.rows_truncated ? " (truncated)" : ""
              }`
            : ""}
        </summary>
        <div className="meta">
          <span>status: {result.population?.status ?? "ABSENT"}</span>
        </div>
        {Object.keys(bindings).length === 0 ? (
          <div className="muted">No population bindings on result</div>
        ) : (
          <ul className="binding-list">
            {Object.entries(bindings).map(([name, b]) => (
              <li key={name}>
                <strong>{name}</strong>
                <div className="muted small">
                  {b.actual_definition_version ?? b.requested_definition_version ?? "—"} · {b.status}
                </div>
              </li>
            ))}
          </ul>
        )}
        <p className="muted">{result.summary?.population_description}</p>
        {rows.length === 0 ? (
          <div className="muted">No population rows</div>
        ) : (
          <div className="table-wrap results-table-wrap">
            <table className="data results-pop-table">
              <thead>
                <tr>
                  {displayCols.map((k) => (
                    <th key={k}>{k}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.slice(0, 50).map((row, i) => (
                  <tr key={String(row.ticker ?? i)}>
                    {displayCols.map((k) => (
                      <td key={k} title={fmtValue(row[k])}>
                        {fmtValue(row[k])}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </details>

      <details className="research-object results-details">
        <summary>Provenance</summary>
        <h3>Authoritative Bindings</h3>
        <div className="table-wrap results-table-wrap compact-wrap">
          <table className="data">
            <thead>
              <tr>
                <th>name</th>
                <th>requested</th>
                <th>actual</th>
                <th>status</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(bindings).map(([name, b]) => (
                <tr key={name}>
                  <td>{name}</td>
                  <td>{b.requested_definition_version ?? "null"}</td>
                  <td>{b.actual_definition_version ?? "null"}</td>
                  <td>{b.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <h3>Source Artifacts</h3>
        <ul className="binding-list">
          {(provenance.source_artifacts || []).map((a) => (
            <li key={a} className="mono small wrap-id">
              {a}
            </li>
          ))}
        </ul>
        <h3>Field Bindings</h3>
        <ul className="binding-list">
          {entryBind && typeof entryBind === "object" ? (
            <li>
              <span className="mono">
                {String((entryBind as { schema_field?: string }).schema_field)}
              </span>
              {" → "}
              <span className="mono">
                {String((entryBind as { artifact_field?: string }).artifact_field)}
              </span>
            </li>
          ) : null}
          {measurements
            .filter((m) => m.source?.field)
            .map((m) => (
              <li key={String(m.name)}>
                <span className="mono">{m.name}</span>
                {" → "}
                <span className="mono">{m.source?.field}</span>
              </li>
            ))}
        </ul>
      </details>

      <details className="research-object results-details">
        <summary>Caveats</summary>
        <ul className="caveat-list">
          {caveats.map((c) => (
            <li key={c}>{c}</li>
          ))}
        </ul>
      </details>
        </>
      ) : null}
    </div>
  );
}
