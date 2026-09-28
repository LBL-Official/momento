import { useMemo, useState } from "react";
import type { Spec } from "../../researchTypes";
import { asArr, asObj, blankSpec } from "../../researchTypes";
import type { LabStep } from "../navigation";
import type { CatalogTemplate } from "../templateCatalog";
import ResearchStatus from "../shell/ResearchStatus";
import type { Freshness, ValidationSnapshot } from "../../researchFreshness";
import { lockedTemplateLeagues } from "../populationLock";
import CalendarScopePicker from "../components/CalendarScopePicker";
import { hasCalendarScope } from "../calendarScope";

type BackendTemplate = {
  id: string;
  label: string;
  research_spec: Spec;
};

type Props = {
  spec: Spec;
  setSpec: (spec: Spec | ((s: Spec) => Spec)) => void;
  backendTemplates: BackendTemplate[];
  catalog: CatalogTemplate[];
  validationFreshness: Freshness;
  executionFreshness: Freshness;
  validationSnapshot: ValidationSnapshot | null;
  canRun: boolean;
  runBusy: boolean;
  onValidate: () => void;
  onRun: () => void;
  onValidateAndRun: () => void;
  onSaveNamed: (name: string) => void;
  onOpenAdvanced: () => void;
  showAdvanced: boolean;
  onTemplateLoaded: (templateId: string | null) => void;
  onRevertToValidated: () => void;
  onReloadTemplate: () => void;
};

const STEPS: { id: LabStep; label: string }[] = [
  { id: "population", label: "Population" },
  { id: "conditions", label: "Conditions" },
  { id: "measurements", label: "Measurements" },
  { id: "name", label: "Name" },
  { id: "review", label: "Review" },
];

export default function LabWorkspace({
  spec,
  setSpec,
  backendTemplates,
  catalog,
  validationFreshness,
  executionFreshness,
  validationSnapshot,
  canRun,
  runBusy,
  onValidate,
  onRun,
  onValidateAndRun,
  onSaveNamed,
  onOpenAdvanced,
  showAdvanced,
  onTemplateLoaded,
  onRevertToValidated,
  onReloadTemplate,
}: Props) {
  const [step, setStep] = useState<LabStep>("population");
  const [nameDraft, setNameDraft] = useState(
    () => String(asObj(spec.identity).name || ""),
  );

  const implemented = useMemo(
    () =>
      catalog.filter(
        (c) =>
          c.status === "IMPLEMENTED" &&
          c.backendTemplateId &&
          backendTemplates.some((b) => b.id === c.backendTemplateId),
      ),
    [catalog, backendTemplates],
  );

  const loadBackend = (backendId: string) => {
    const found = backendTemplates.find((t) => t.id === backendId);
    if (!found) return;
    setSpec(structuredClone(found.research_spec));
    onTemplateLoaded(backendId);
    const n = String(asObj(found.research_spec.identity).name || found.label);
    setNameDraft(n);
    setStep("review");
  };

  const lockedLeagues = lockedTemplateLeagues(spec);

  const identity = asObj(spec.identity);
  const pop = asObj(spec.population_binding);
  const leagues = Array.isArray(pop.leagues) ? (pop.leagues as string[]) : [];
  const slices = Array.isArray(pop.default_structural_slices)
    ? (pop.default_structural_slices as string[])
    : [];
  const anchor = asObj(spec.anchor);
  const measurements = Array.isArray(spec.measurement_requests)
    ? (spec.measurement_requests as Record<string, unknown>[])
    : [];

  return (
    <div className="ws-lab">
      <header className="ws-lab-head">
        <p className="v2-kicker">Lab</p>
        <h1 className="v2-page-title">Define a study</h1>
        <p className="v2-lede">
          Population → conditions → measurements → name → validate → run. No JSON required.
        </p>
      </header>

      <nav className="v2-mode-nav" aria-label="Lab steps">
        {STEPS.map((s) => (
          <button
            key={s.id}
            type="button"
            className={step === s.id ? "v2-mode on" : "v2-mode"}
            onClick={() => setStep(s.id)}
          >
            {s.label}
          </button>
        ))}
      </nav>

      {step === "population" ? (
        <section className="ws-lab-step">
          <h2>What are we studying?</h2>
          <div className="ws-choice-list">
            {implemented.map((t) => (
              <button
                key={t.id}
                type="button"
                className="ws-choice"
                onClick={() => t.backendTemplateId && loadBackend(t.backendTemplateId)}
              >
                <div className="ws-choice-title">{t.name}</div>
                <div className="muted">{t.description}</div>
                <span className="v2-badge ok">IMPLEMENTED · RUNNABLE</span>
                {t.id === "FIRST80_Q3" ? (
                  <div className="evidence">Locked expectation n = 290</div>
                ) : null}
                {t.id === "NCAAB_FIRST80_P5" ? (
                  <div className="evidence">Locked expectation n = 721</div>
                ) : null}
              </button>
            ))}
            <button
              type="button"
              className="ws-choice"
              onClick={() => {
                setSpec(blankSpec());
                onTemplateLoaded(null);
                setNameDraft("");
                setStep("conditions");
              }}
            >
              <div className="ws-choice-title">Blank study</div>
              <div className="muted">Start empty — use Advanced editor for full control.</div>
              <span className="v2-badge">CONFIGURABLE</span>
            </button>
          </div>
        </section>
      ) : null}

      {step === "conditions" ? (
        <section className="ws-lab-step">
          <h2>Define the empirical universe</h2>
          <div className="ws-condition-mass">
            <div className="ws-condition-block">
              <div className="v2-kicker">When</div>
              <div className="ws-condition-value">
                {typeof anchor.event === "string" ? anchor.event.replace(/_/g, " ") : "—"}
              </div>
              {typeof anchor.price_e4 === "number" ? (
                <div className="evidence">= {Math.round(anchor.price_e4 / 100)}¢</div>
              ) : null}
            </div>
            <div className="ws-and">AND</div>
            <div className="ws-condition-block">
              <div className="v2-kicker">Game period</div>
              <div className="ws-condition-value evidence">
                {slices.length ? slices.join(" · ") : "Unrestricted"}
              </div>
              <div className="muted">{leagues.join(" · ") || "League unset"}</div>
            </div>
          </div>

          <CalendarScopePicker
            spec={spec}
            setSpec={setSpec}
            locked={Boolean(lockedLeagues)}
          />

          {hasCalendarScope(pop) ? (
            <p className="notice">
              Calendar scope is set — validation will report STRUCTURAL /
              population_binding.calendar_scope until an authoritative route applies it (or you clear
              it).
            </p>
          ) : null}

          <p className="muted">
            Anchor and period come from the loaded template. Season scope is editable above.
          </p>
          <div className="row">
            <button type="button" className="btn-secondary" onClick={() => setStep("population")}>
              ← Population
            </button>
            <button type="button" className="btn-primary" onClick={() => setStep("measurements")}>
              Measurements →
            </button>
          </div>
        </section>
      ) : null}

      {step === "measurements" ? (
        <section className="ws-lab-step">
          <h2>What do you want to observe?</h2>
          <ul className="ws-measure-list">
            {measurements.length ? (
              measurements.map((m, i) => (
                <li key={String(m.name || i)} className="ws-measure-item">
                  <span className="evidence">{String(m.name)}</span>
                  <span className="v2-badge ok">Requested</span>
                </li>
              ))
            ) : (
              <li className="muted">No measurement requests on this study yet.</li>
            )}
          </ul>
          <p className="muted small">MEASUREMENT ≠ EDGE · Candle path ≠ fill</p>
          <div className="row">
            <button type="button" className="btn-secondary" onClick={() => setStep("conditions")}>
              ← Conditions
            </button>
            <button type="button" className="btn-primary" onClick={() => setStep("name")}>
              Name →
            </button>
          </div>
        </section>
      ) : null}

      {step === "name" ? (
        <section className="ws-lab-step">
          <h2>Name this study</h2>
          <label className="ws-name-field">
            Name
            <input
              value={nameDraft}
              onChange={(e) => setNameDraft(e.target.value)}
              placeholder="e.g. FIRST80 Q3"
            />
          </label>
          <div className="row">
            <button
              type="button"
              className="btn-secondary"
              onClick={() => {
                const next = structuredClone(spec);
                next.identity = {
                  ...asObj(next.identity),
                  name: nameDraft.trim() || String(asObj(spec.identity).name || "Untitled study"),
                };
                setSpec(next);
                onSaveNamed(
                  nameDraft.trim() || String(asObj(spec.identity).name || "Untitled study"),
                );
              }}
            >
              Save locally
            </button>
            <button
              type="button"
              className="btn-primary"
              onClick={() => {
                const next = structuredClone(spec);
                next.identity = {
                  ...asObj(next.identity),
                  name: nameDraft.trim() || String(asObj(spec.identity).name || "Untitled study"),
                };
                setSpec(next);
                setStep("review");
              }}
            >
              Review →
            </button>
          </div>
          <p className="muted small">
            Local save only — not an authoritative registry entry.
          </p>
        </section>
      ) : null}

      {step === "review" ? (
        <section className="ws-lab-step">
          <h2>Review</h2>
          <ResearchStatus
            validationFreshness={validationFreshness}
            executionFreshness={executionFreshness}
            validationSnapshot={validationSnapshot}
            canRun={canRun}
            onRevalidate={onValidate}
          />
          {validationFreshness === "STALE" ? (
            <div className="ws-stale-banner">
              <p>
                Study changed since validation
                {lockedLeagues
                  ? ` · template leagues are locked to ${lockedLeagues.join(" · ")}`
                  : ""}
                . Preview never mutates research_spec — restore the template or revert, then
                revalidate.
              </p>
              <div className="row">
                <button type="button" className="btn-primary" onClick={onRevertToValidated}>
                  Revert to validated
                </button>
                <button type="button" className="btn-secondary" onClick={onReloadTemplate}>
                  Reload template
                </button>
              </div>
            </div>
          ) : null}
          <dl className="ws-review-dl">
            <div>
              <dt>Study</dt>
              <dd className="evidence">{String(identity.name || nameDraft || "—")}</dd>
            </div>
            <div>
              <dt>Population</dt>
              <dd className="evidence">
                {leagues.join(" · ") || "—"}
                {slices.length ? ` · ${slices.join(" · ")}` : ""}
                {lockedLeagues ? " · locked" : ""}
              </dd>
            </div>
            <div>
              <dt>Season scope</dt>
              <dd className="evidence">
                {hasCalendarScope(pop)
                  ? [
                      (asArr(pop.seasons) as string[]).join(", "),
                      (asArr(pop.season_months) as string[]).join(", "),
                      (asArr(pop.season_weeks) as string[]).join(", "),
                    ]
                      .filter(Boolean)
                      .join(" · ")
                  : "Full seasons (no calendar filter)"}
              </dd>
            </div>
            <div>
              <dt>Measurements</dt>
              <dd className="evidence">
                {measurements.map((m) => String(m.name)).filter(Boolean).join(" · ") || "—"}
              </dd>
            </div>
          </dl>
          <div className="row">
            <button type="button" className="btn-secondary" onClick={onValidate} disabled={runBusy}>
              Validate
            </button>
            <button
              type="button"
              className="btn-primary"
              disabled={runBusy || validationFreshness === "STALE"}
              onClick={() => {
                if (canRun) onRun();
                else onValidateAndRun();
              }}
            >
              {runBusy ? "Running…" : canRun ? "Run research" : "Validate & Run"}
            </button>
            <button type="button" className="v2-text-link" onClick={onOpenAdvanced}>
              {showAdvanced ? "Hide advanced editor" : "Advanced research object editor"}
            </button>
          </div>
        </section>
      ) : null}
    </div>
  );
}
