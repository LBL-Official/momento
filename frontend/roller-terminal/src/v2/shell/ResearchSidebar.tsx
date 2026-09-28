import type { LibraryEntry } from "../researchLibrary";
import { SECONDARY_NAV, type AppRoute } from "../navigation";
import type { Freshness, ValidationSnapshot } from "../../researchFreshness";
import type { HumanStatus } from "../researchStatus";
import type { StaxRoute } from "../../stax/types";

type ResearchMode = "quickstart" | "stax";

type Props = {
  collapsed: boolean;
  route: AppRoute;
  identityName: string;
  status: HumanStatus;
  validationFreshness: Freshness;
  executionFreshness: Freshness;
  validationSnapshot: ValidationSnapshot | null;
  canRun: boolean;
  runBusy: boolean;
  populationN: number | null;
  resultsFresh?: boolean;
  recent: LibraryEntry[];
  currentSpecFingerprint: string;
  onValidate: () => void;
  onRun: () => void;
  onValidateAndRun?: () => void;
  onSave: () => void;
  onRevertToValidated?: () => void;
  onReloadTemplate?: () => void;
  onOpenRecent: (entry: LibraryEntry) => void;
  onNavigate: (route: AppRoute) => void;
  researchMode?: ResearchMode;
  onResearchMode?: (mode: ResearchMode) => void;
  staxRoute?: StaxRoute;
  onStaxNavigate?: (route: StaxRoute) => void;
  staxName?: string;
  staxStrategyCount?: number;
};

/** The research sequence is the spine of the terminal: each step states what
 *  it is for, not just where it goes. Routes are unchanged. */
const QUICKSTART_SEQUENCE: { id: AppRoute; label: string; purpose: string }[] = [
  { id: "start", label: "Quick Start", purpose: "Define universe" },
  { id: "entry", label: "Entry", purpose: "Define event" },
  { id: "exit", label: "Exit", purpose: "Define path" },
  { id: "confirm", label: "Confirm", purpose: "Lock specification" },
  { id: "results", label: "Results", purpose: "Measure" },
];

const STAX_SEQUENCE: { id: StaxRoute; label: string; purpose: string }[] = [
  { id: "overview", label: "Overview", purpose: "Stack state" },
  { id: "strategies", label: "Strategies", purpose: "Independent objects" },
  { id: "results", label: "Results", purpose: "Per-strategy measurement" },
  { id: "history", label: "History", purpose: "Immutable versions" },
  { id: "automation", label: "Automation", purpose: "Re-execution" },
];

const SIGNAL: Record<HumanStatus["kind"], string> = {
  ready: "live",
  review: "hold",
  attention: "blocked",
  idle: "idle",
};

export default function ResearchSidebar({
  collapsed,
  route,
  identityName,
  status,
  validationFreshness,
  canRun,
  runBusy,
  populationN,
  resultsFresh,
  recent,
  onValidate,
  onRun,
  onSave,
  onRevertToValidated,
  onReloadTemplate,
  onOpenRecent,
  onNavigate,
  researchMode = "quickstart",
  onResearchMode,
  staxRoute = "overview",
  onStaxNavigate,
  staxName,
  staxStrategyCount,
}: Props) {
  if (collapsed) {
    return <aside className="ws-research-sidebar collapsed" aria-hidden />;
  }

  const stax = researchMode === "stax";
  const sequence = stax ? STAX_SEQUENCE : QUICKSTART_SEQUENCE;
  const activeId: string = stax ? staxRoute : route;
  const activeIndex = sequence.findIndex((s) => s.id === activeId);

  return (
    <aside className="ws-research-sidebar mm-spine" aria-label="Research spine">
      {/* Product identity lives in the application bar; the spine opens
          straight into research state so the two never duplicate. */}

      {/* ── Research mode ────────────────────────────────────────── */}
      {onResearchMode ? (
        <div className="mm-spine-block">
          <p className="mm-rail-label">Research mode</p>
          <div className="mm-mode-switch" role="group" aria-label="Research mode">
            <button
              type="button"
              className={!stax ? "mm-mode on" : "mm-mode"}
              onClick={() => onResearchMode("quickstart")}
              aria-pressed={!stax}
            >
              <span className="mm-mode-name">Quick Start</span>
              <span className="mm-mode-sub">One object</span>
            </button>
            <button
              type="button"
              className="mm-mode"
              disabled
              aria-pressed={false}
              aria-disabled="true"
              title="Coming soon. STAX is not in use."
            >
              <span className="mm-mode-name">Stax</span>
              <span className="mm-mode-sub">Coming soon · not in use</span>
            </button>
          </div>
          <p className="ws-coming-soon">
            <strong>COMING SOON</strong>
            <span>STAX multi-object is recognized but not in use. Quick Start remains the research mode.</span>
          </p>
        </div>
      ) : null}

      {/* ── Active research object ───────────────────────────────── */}
      <div className="mm-spine-block">
        <p className="mm-rail-label">{stax ? "Stack" : "Research object"}</p>
        <button
          type="button"
          className="mm-spine-object"
          onClick={() => (stax ? onStaxNavigate?.("overview") : onNavigate("start"))}
        >
          {stax ? staxName || "Multi-strategy stack" : identityName}
        </button>
      </div>

      <div className="mm-spine-block">
        <p className="mm-rail-label">Observations</p>
        {stax ? (
          <p className="mm-spine-metric">
            <span className="mm-spine-metric-k">Strategies =</span>
            <span className="mm-spine-metric-v">{staxStrategyCount ?? 0}</span>
          </p>
        ) : (
          <p className={populationN != null ? "mm-spine-metric" : "mm-spine-metric is-empty"}>
            <span className="mm-spine-metric-k">N =</span>
            <span className="mm-spine-metric-v">{populationN != null ? populationN : "—"}</span>
          </p>
        )}
      </div>

      {/* ── Research sequence — the mission progression ──────────── */}
      <div className="mm-spine-block mm-spine-sequence-block">
        <p className="mm-rail-label">Research sequence</p>
        <ol className="mm-sequence">
          {sequence.map((step, i) => {
            const state =
              activeIndex >= 0 && i < activeIndex ? "done" : i === activeIndex ? "on" : "todo";
            return (
              <li key={step.id} className={`mm-seq is-${state}`}>
                <button
                  type="button"
                  className="mm-seq-btn"
                  onClick={() =>
                    stax ? onStaxNavigate?.(step.id as StaxRoute) : onNavigate(step.id as AppRoute)
                  }
                  aria-current={state === "on" ? "step" : undefined}
                >
                  <span className="mm-seq-index" aria-hidden>
                    {String(i + 1).padStart(2, "0")}
                  </span>
                  <span className="mm-seq-text">
                    <span className="mm-seq-label">
                      {step.label}
                      {!stax && step.id === "results" && resultsFresh ? (
                        <span className="ws-nav-mark" aria-hidden />
                      ) : null}
                    </span>
                    <span className="mm-seq-purpose">{step.purpose}</span>
                  </span>
                </button>
              </li>
            );
          })}
        </ol>
      </div>

      {/* ── System state ─────────────────────────────────────────── */}
      <div className="mm-spine-block">
        <p className="mm-rail-label">System</p>
        <p className={`mm-spine-system tone-${status.kind}`} title={status.detail}>
          <span className={`mm-signal ${SIGNAL[status.kind]}`} aria-hidden />
          {status.title}
        </p>

        <p className="mm-spine-detail">{status.detail}</p>

        {validationFreshness === "STALE" ? (
          <div className="ws-sidebar-stale">
            <p className="muted small">
              Spec changed since validation. Preview does not mutate research_spec.
            </p>
            <div className="ws-sidebar-actions">
              <button type="button" className="btn-primary" onClick={onValidate}>
                Revalidate
              </button>
              {onRevertToValidated ? (
                <button type="button" className="btn-secondary" onClick={onRevertToValidated}>
                  Revert to validated
                </button>
              ) : null}
              {onReloadTemplate ? (
                <button type="button" className="btn-secondary" onClick={onReloadTemplate}>
                  Reload template
                </button>
              ) : null}
            </div>
          </div>
        ) : null}

        <details className="ws-sidebar-advanced">
          <summary>Map actions</summary>
          <div className="ws-sidebar-actions">
            <button type="button" className="btn-secondary" onClick={onValidate} disabled={runBusy}>
              Validate
            </button>
            <button
              type="button"
              className="btn-secondary"
              onClick={onRun}
              disabled={runBusy || !canRun}
            >
              {runBusy ? "Running…" : "Run"}
            </button>
            <button type="button" className="btn-secondary" onClick={onSave}>
              Save
            </button>
          </div>
        </details>
      </div>

      {/* ── Reference destinations — deliberately subordinate ─────── */}
      <div className="mm-spine-block">
        <p className="mm-rail-label">Reference</p>
        <ul className="mm-spine-reference">
          {SECONDARY_NAV.map((item) => (
            <li key={item.id}>
              <button
                type="button"
                className={route === item.id && !stax ? "mm-spine-ref on" : "mm-spine-ref"}
                onClick={() => onNavigate(item.id)}
                title={item.hint}
              >
                {item.label}
              </button>
            </li>
          ))}
        </ul>
      </div>

      <section className="mm-spine-block ws-sidebar-section">
        <p className="mm-rail-label">Recent snapshots</p>
        {!recent.length ? (
          <p className="mm-spine-empty">None saved locally</p>
        ) : (
          <ul className="ws-sidebar-list">
            {recent.slice(0, 6).map((e) => (
              <li key={e.id}>
                <button type="button" className="v2-text-link" onClick={() => onOpenRecent(e)}>
                  {e.name}
                </button>
              </li>
            ))}
          </ul>
        )}
        <button
          type="button"
          className="v2-text-link"
          onClick={() => (stax ? onStaxNavigate?.("library" as StaxRoute) : onNavigate("library"))}
        >
          Open library →
        </button>
      </section>
    </aside>
  );
}
