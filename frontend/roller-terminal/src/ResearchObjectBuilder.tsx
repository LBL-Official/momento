import { useCallback, useEffect, useMemo, useRef, useState, type Dispatch, type SetStateAction } from "react";
import { apiFetch, classifyApiFailure } from "./api/base";
import BuilderSection from "./components/BuilderSection";
import BuilderSectionIndex from "./components/BuilderSectionIndex";
import ResearchActionRail from "./components/ResearchActionRail";
import ResearchCapabilityPanel from "./components/ResearchCapabilityPanel";
import ResearchCheckpoint from "./components/ResearchCheckpoint";
import ResearchGlanceStrip from "./components/ResearchGlanceStrip";
import ResearchSpecDiffView from "./components/ResearchSpecDiff";
import {
  sectionSummaries,
  sectionsForValidationIssues,
} from "./researchLifecycle";
import { diffResearchSpecs } from "./researchDiff";
import {
  measurementsSectionSummary,
  type ResearchCapabilitiesPayload,
  type ResearchCapabilityPreview,
} from "./researchCapabilityPreview";
import {
  type Freshness,
  type ValidationSnapshot,
  stableSpecFingerprint,
} from "./researchFreshness";
import {
  asArr,
  asObj,
  blankSpec,
  type InterpretResult,
  type Spec,
  type ValidateResult,
} from "./researchTypes";
import { lockedTemplateLeagues } from "./v2/populationLock";
import CalendarScopePicker from "./v2/components/CalendarScopePicker";

type Template = {
  id: string;
  label: string;
  source_file: string;
  research_spec: Spec;
};

type PreviewResult = {
  research_object_id: string | null;
  identity: Record<string, unknown>;
  universe: string;
  population: Record<string, unknown>;
  anchor: Record<string, unknown>;
  information: Record<string, unknown>;
  state: unknown;
  path: unknown[];
  terminal: unknown[];
  measurements: unknown[];
  definition_versions: Record<string, unknown>;
  dataset_versions: Record<string, unknown>;
  execution_interpretation: string;
  caveats: string[];
  valid: boolean;
  runnable: boolean;
  status: string;
  errors: string[];
  unresolved: { field: string; reason: string }[];
  note?: string;
};

type ResearchResultPayload = {
  research_object_id?: string | null;
  execution_status?: string;
  [key: string]: unknown;
};

type Props = {
  spec: Spec;
  setSpec: Dispatch<SetStateAction<Spec>>;
  validationSnapshot: ValidationSnapshot | null;
  setValidationSnapshot: Dispatch<SetStateAction<ValidationSnapshot | null>>;
  interpretation: InterpretResult | null;
  setInterpretation: Dispatch<SetStateAction<InterpretResult | null>>;
  runBusy: boolean;
  setRunBusy: Dispatch<SetStateAction<boolean>>;
  currentSpecFingerprint: string;
  validationFreshness: Freshness;
  executionFreshness: Freshness;
  canRun: boolean;
  capabilities: ResearchCapabilitiesPayload | null;
  capabilityPreview: ResearchCapabilityPreview | null;
  capabilitiesLoading: boolean;
  capabilitiesError: string | null;
  capabilitySummary: string | null;
  onResearchResult?: (
    result: ResearchResultPayload,
    specFingerprint: string,
    submittedSpec: Spec,
  ) => void;
  /** Optional hook so Lab Review can invoke the same validate/run path. */
  onActionsReady?: (actions: {
    validate: () => Promise<ValidateResult | null>;
    run: () => Promise<void>;
    validateAndRun: () => Promise<void>;
  }) => void;
  /** Fired when a backend/catalog template (or blank) is loaded into the builder. */
  onTemplateLoaded?: (templateId: string | null) => void;
  /** Restore last validated research_spec (undo accidental edits). */
  onRevertToValidated?: () => void;
  /** Reload the active IMPLEMENTED template from backend samples. */
  onReloadTemplate?: () => void;
};

const SLICES = ["Q1", "Q2", "Q3", "Q4", "H1_1", "H1_2", "H2_1", "H2_2", "ASKED_SIX"];
const LEAGUES = ["NBA", "WNBA", "NCAAB"];
const PATH_KINDS = [
  "NEVER_CLOSE_LE",
  "EVER_CLOSE_LE",
  "EVER_CLOSE_GE",
  "SURVIVE_THEN_TOUCH",
  "MAE_GT",
  "FORWARD_RESPONSE",
  "CUSTOM_BINDING",
  "UNRESOLVED",
];
const TERMINAL_KINDS = ["KALSHI_YES", "KALSHI_NO", "UNRESTRICTED", "CUSTOM_BINDING", "UNRESOLVED"];
const OPERATORS = ["eq", "neq", "lt", "lte", "gt", "gte", "in", "between", "exists"];

export default function ResearchObjectBuilder({
  spec,
  setSpec,
  validationSnapshot,
  setValidationSnapshot,
  interpretation,
  setInterpretation,
  runBusy,
  setRunBusy,
  currentSpecFingerprint,
  validationFreshness,
  executionFreshness,
  canRun,
  capabilities,
  capabilityPreview,
  capabilitiesLoading,
  capabilitiesError,
  capabilitySummary,
  onResearchResult,
  onActionsReady,
  onTemplateLoaded,
  onRevertToValidated,
  onReloadTemplate,
}: Props) {
  const validation = validationSnapshot?.payload ?? null;
  // Transient UI only — no shadow editable research_spec.
  const [templates, setTemplates] = useState<Template[]>([]);
  const [preview, setPreview] = useState<PreviewResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [ideaText, setIdeaText] = useState("");
  const [interpretBusy, setInterpretBusy] = useState(false);
  const glanceRef = useRef<HTMLDivElement | null>(null);
  const validationRef = useRef<HTMLElement | null>(null);
  const ideaRef = useRef<HTMLTextAreaElement | null>(null);
  const [openSections, setOpenSections] = useState<Record<string, boolean>>({
    A: false,
    B: false,
    C: false,
    D: false,
    E: false,
    F: false,
    G: false,
    H: false,
    I: false,
  });
  const toggleSection = (id: string) =>
    setOpenSections((prev) => ({ ...prev, [id]: !prev[id] }));
  const ensureSectionOpen = useCallback((id: string) => {
    setOpenSections((prev) => (prev[id] ? prev : { ...prev, [id]: true }));
  }, []);
  const summaries = useMemo(
    () => sectionSummaries(spec, validationFreshness, validation),
    [spec, validationFreshness, validation],
  );
  const hSummary = useMemo(
    () =>
      measurementsSectionSummary(
        asArr(spec.measurement_requests).length,
        capabilityPreview,
        capabilitiesLoading,
        capabilitiesError,
      ),
    [spec.measurement_requests, capabilityPreview, capabilitiesLoading, capabilitiesError],
  );
  const vsValidated = useMemo(
    () => diffResearchSpecs(spec, validationSnapshot?.spec ?? null),
    [spec, validationSnapshot],
  );
  const knownMeasurements = capabilities?.measurements ?? [];

  useEffect(() => {
    if (validationFreshness !== "CURRENT" || !validation) return;
    const ids = sectionsForValidationIssues(validation.errors || [], validation.unresolved || []);
    if (!ids.length) return;
    setOpenSections((prev) => {
      const next = { ...prev };
      for (const id of ids) next[id] = true;
      return next;
    });
  }, [validationFreshness, validation]);

  useEffect(() => {
    apiFetch("/research-object-templates")
      .then((r) => r.json())
      .then((data) => setTemplates(data as Template[]))
      .catch((e) => setError(String(e)));
  }, []);

  const identity = asObj(spec.identity);
  const population = asObj(spec.population_binding);
  const anchor = asObj(spec.anchor);
  const leagues = asArr(population.leagues) as string[];
  const slices = asArr(population.default_structural_slices) as string[];
  const pathConditions = asArr(spec.path_conditions) as Record<string, unknown>[];
  const terminalConditions = asArr(spec.terminal_conditions) as Record<string, unknown>[];
  const measurements = asArr(spec.measurement_requests) as Record<string, unknown>[];
  const unresolvedParams = asArr(anchor.unresolved_parameters) as string[];

  const patch = useCallback(
    (updater: (prev: Spec) => Spec) => {
      setSpec((prev) => updater(prev));
      // Do not clear validationSnapshot — freshness is derived from fingerprints.
    },
    [setSpec],
  );

  const setIdentity = (key: string, value: unknown) => {
    patch((prev) => ({ ...prev, identity: { ...asObj(prev.identity), [key]: value } }));
  };

  const setPopulation = (key: string, value: unknown) => {
    patch((prev) => ({
      ...prev,
      population_binding: { ...asObj(prev.population_binding), [key]: value },
    }));
  };

  const setAnchor = (key: string, value: unknown) => {
    patch((prev) => {
      const nextAnchor = { ...asObj(prev.anchor), [key]: value };
      // Keep magnitude unresolved when empty for PRICE_MOVE
      if (key === "magnitude_e4") {
        const params = new Set(asArr(nextAnchor.unresolved_parameters) as string[]);
        if (value === null || value === "" || value === undefined) {
          params.add("magnitude_e4");
          nextAnchor.magnitude_e4 = null;
        } else {
          params.delete("magnitude_e4");
          nextAnchor.magnitude_e4 = Number(value);
        }
        nextAnchor.unresolved_parameters = [...params];
      }
      return { ...prev, anchor: nextAnchor };
    });
  };

  const loadTemplate = (id: string | "BLANK") => {
    if (id === "BLANK") {
      setSpec(blankSpec());
      setPreview(null);
      setValidationSnapshot(null);
      setInterpretation(null);
      onTemplateLoaded?.(null);
      return;
    }
    const t = templates.find((x) => x.id === id);
    if (!t) return;
    setSpec(structuredClone(t.research_spec));
    setPreview(null);
    setValidationSnapshot(null);
    setInterpretation(null);
    onTemplateLoaded?.(t.id);
  };

  const validate = async () => {
    setBusy(true);
    setError(null);
    try {
      const [vRes, pRes] = await Promise.all([
        apiFetch("/research-objects/validate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ research_spec: spec }),
        }),
        apiFetch("/research-objects/preview", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ research_spec: spec }),
        }),
      ]);
      const vBody = await vRes.json();
      const pBody = await pRes.json();
      const fp = stableSpecFingerprint(spec);
      setValidationSnapshot({
        payload: vBody as ValidateResult,
        spec: structuredClone(spec),
        specFingerprint: fp,
      });
      setPreview(pBody as PreviewResult);
      requestAnimationFrame(() => {
        validationRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
        validationRef.current?.focus();
      });
      return vBody as ValidateResult;
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      return null;
    } finally {
      setBusy(false);
    }
  };

  const executeCurrentSpec = async () => {
    setRunBusy(true);
    setError(null);
    try {
      const submittedFp = stableSpecFingerprint(spec);
      const res = await apiFetch("/research-objects/execute", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ research_spec: spec }),
      });
      const body = (await res.json()) as ResearchResultPayload;
      if (!res.ok) {
        throw new Error(String((body as { detail?: string }).detail || res.statusText));
      }
      const submittedSpec = structuredClone(spec);
      setValidationSnapshot({
        payload: {
          valid: Boolean((body as { validation?: { valid?: boolean } }).validation?.valid),
          runnable: Boolean((body as { validation?: { runnable?: boolean } }).validation?.runnable),
          status: String(
            (body as { validation?: { status?: string } }).validation?.status || body.execution_status,
          ),
          research_object_id: (body.research_object_id as string) || null,
          errors: ((body as { validation?: { errors?: string[] } }).validation?.errors || []) as string[],
          unresolved: ((
            body as { validation?: { unresolved?: { field: string; reason: string }[] } }
          ).validation?.unresolved || []) as { field: string; reason: string }[],
        },
        spec: submittedSpec,
        specFingerprint: submittedFp,
      });
      onResearchResult?.(body, submittedFp, submittedSpec);
      if (body.execution_status === "INVALID" || body.execution_status === "UNRESOLVED") {
        setError(`NO EXECUTION — ${body.execution_status}`);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setRunBusy(false);
    }
  };

  const runResearch = async () => {
    if (!canRun) {
      if (validationFreshness === "STALE") {
        setError("SPEC CHANGED — REVALIDATE BEFORE EXECUTION");
      } else if (validationFreshness === "UNVALIDATED") {
        setError("CURRENT SPEC HAS NOT BEEN VALIDATED");
      } else {
        setError("SPEC CHANGED — REVALIDATE REQUIRED");
      }
      return;
    }
    await executeCurrentSpec();
  };

  const validateAndRun = async () => {
    if (validationFreshness === "STALE") {
      setError("SPEC CHANGED — REVERT OR REVALIDATE BEFORE VALIDATE & RUN");
      return;
    }
    if (canRun) {
      await executeCurrentSpec();
      return;
    }
    const vBody = await validate();
    if (!vBody) return;
    const unresolved = vBody.unresolved || [];
    if (vBody.valid && vBody.runnable && unresolved.length === 0) {
      await executeCurrentSpec();
      return;
    }
    setError(
      `NOT RUNNABLE AFTER VALIDATE — ${vBody.status}${
        unresolved.length ? ` · ${unresolved.map((u) => u.field).join(", ")}` : ""
      }`,
    );
  };

  useEffect(() => {
    onActionsReady?.({ validate, run: runResearch, validateAndRun });
  });

  const exportSpec = () => {
    const blob = new Blob([JSON.stringify(spec, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${String(identity.name || "research_spec")}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const interpret = async () => {
    setInterpretBusy(true);
    setError(null);
    try {
      const res = await apiFetch("/query/interpret", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: ideaText }),
      });
      const body = (await res.json()) as InterpretResult;
      setInterpretation(body);
    } catch (e) {
      const availability = classifyApiFailure(e);
      setError(availability === "API_UNREACHABLE" ? "API_UNREACHABLE" : e instanceof Error ? e.message : String(e));
    } finally {
      setInterpretBusy(false);
    }
  };

  const applyToBuilder = () => {
    if (!interpretation?.proposed_spec) return;
    setSpec(structuredClone(interpretation.proposed_spec));
    setPreview(null);
    requestAnimationFrame(() => {
      glanceRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
      glanceRef.current?.focus();
    });
  };

  const jsonText = useMemo(() => JSON.stringify(spec, null, 2), [spec]);

  const lockedLeagues = useMemo(() => lockedTemplateLeagues(spec), [spec]);

  const toggleLeague = (league: string) => {
    if (lockedLeagues) return;
    const next = leagues.includes(league)
      ? leagues.filter((x) => x !== league)
      : [...leagues, league];
    setPopulation("leagues", next);
  };

  const toggleSlice = (slice: string) => {
    const next = slices.includes(slice) ? slices.filter((x) => x !== slice) : [...slices, slice];
    setPopulation("default_structural_slices", next);
  };

  return (
    <div className="ro-workspace">
      <ResearchActionRail
        ideaText={ideaText}
        hasProposedSpec={Boolean(interpretation?.proposed_spec)}
        canRun={canRun}
        interpretBusy={interpretBusy}
        validateBusy={busy}
        runBusy={runBusy}
        validationFreshness={validationFreshness}
        onInterpret={interpret}
        onApply={applyToBuilder}
        onValidate={validate}
        onRun={runResearch}
        onExport={exportSpec}
      />

      <div ref={glanceRef} tabIndex={-1}>
        <ResearchGlanceStrip
          spec={spec}
          validationFreshness={validationFreshness}
          validationStatus={validation?.status ?? null}
          executionFreshness={executionFreshness}
          executionStatus={
            executionFreshness === "NONE"
              ? null
              : executionFreshness === "STALE"
                ? "PRIOR"
                : "COMPLETE"
          }
        />
      </div>

      <BuilderSectionIndex onEnsureOpen={ensureSectionOpen} />

      {validationFreshness === "STALE" ? (
        <div className="freshness-callout stale-workflow">
          <div className="empty-title">CURRENT SPEC CHANGED</div>
          <div>VALIDATION IS STALE</div>
          {vsValidated.changed_count > 0 ? (
            <div className="muted">{vsValidated.changed_count} FIELDS DIFFER</div>
          ) : null}
          <div className="notice">REVALIDATE REQUIRED</div>
        </div>
      ) : null}

      {executionFreshness === "STALE" ? (
        <div className="freshness-callout stale-workflow">
          <div className="empty-title">CURRENT SPEC CHANGED</div>
          <div>RESULT BELOW IS A PRIOR EMPIRICAL RESULT</div>
          <div className="muted small">Prior result preserved — RUN RESEARCH disabled until revalidate.</div>
        </div>
      ) : null}

      <div className="ro-layout">
      <div className="ro-left research-object">
        <section className="research-terminal">
          <h2>Research Terminal</h2>
          <p className="muted">
            Deterministic vocabulary interpretation only. WORDS ≠ RESEARCH SPEC. No LLM.
            Use the action rail for INTERPRET / APPLY.
          </p>
          <label className="grow">
            Describe the research object
            <textarea
              ref={ideaRef}
              rows={2}
              value={ideaText}
              onChange={(e) => setIdeaText(e.target.value)}
              onKeyDown={(e) => {
                if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
                  e.preventDefault();
                  if (ideaText.trim() && !interpretBusy) void interpret();
                }
              }}
              placeholder="e.g. first time price hits 80 in Q3"
            />
          </label>
          <p className="muted small">Cmd/Ctrl + Enter → INTERPRET</p>
          {interpretation ? (
            <div className="interpret-panel">
              <div className="row interpret-status">
                <span>
                  STATUS <strong className={`status-${interpretation.status}`}>{interpretation.status}</strong>
                </span>
                {interpretation.template_hint ? (
                  <span className="muted">TEMPLATE HINT: {interpretation.template_hint}</span>
                ) : null}
                {interpretation.compiler_version ? (
                  <span className="muted">compiler {interpretation.compiler_version}</span>
                ) : null}
              </div>
              <div className="interpret-cols">
                <div>
                  <h3>Matched</h3>
                  {interpretation.matches.length === 0 ? (
                    <div className="muted">None</div>
                  ) : (
                    <ul>
                      {interpretation.matches.map((m) => (
                        <li key={`${m.concept_id}-${m.normalized_phrase}`}>
                          ✓ {m.concept_id}{" "}
                          <span className="muted">
                            [{m.confidence}] {m.phrase}
                          </span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
                <div>
                  <h3>Bound</h3>
                  {(interpretation.applied_bindings || []).length === 0 ? (
                    <div className="muted">None (blank defaults are not bindings)</div>
                  ) : (
                    <ul>
                      {(interpretation.applied_bindings || []).map((b) => (
                        <li key={`${b.concept}-${b.fields.join(",")}`}>
                          ✓ {b.concept}
                          <div className="muted small">{b.fields.join(", ")}</div>
                        </li>
                      ))}
                    </ul>
                  )}
                  {interpretation.proposed_spec?.anchor &&
                  typeof interpretation.proposed_spec.anchor === "object" ? (
                    <div className="muted small" style={{ marginTop: "0.4rem" }}>
                      anchor.event ={" "}
                      {String(
                        (interpretation.proposed_spec.anchor as Record<string, unknown>).event,
                      )}
                      {(interpretation.proposed_spec.anchor as Record<string, unknown>).price_e4 !=
                      null
                        ? ` · price_e4 = ${String(
                            (interpretation.proposed_spec.anchor as Record<string, unknown>)
                              .price_e4,
                          )}`
                        : ""}
                    </div>
                  ) : null}
                </div>
                <div>
                  <h3>Unresolved</h3>
                  {interpretation.unresolved.length === 0 ? (
                    <div className="muted">None</div>
                  ) : (
                    <ul>
                      {interpretation.unresolved.map((u) => (
                        <li key={`${u.field}-${u.reason}`}>
                          ! {u.field}: {u.reason}
                          {u.source_text ? (
                            <span className="muted"> (“{u.source_text}”)</span>
                          ) : null}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
                <div>
                  <h3>Unknown</h3>
                  {interpretation.unknown_terms.length === 0 ? (
                    <div className="muted">None</div>
                  ) : (
                    <ul>
                      {interpretation.unknown_terms.map((t) => (
                        <li key={t}>? {t}</li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>
              {interpretation.warnings.length > 0 ? (
                <div className="interpret-warnings">
                  <h3>Warnings</h3>
                  <ul>
                    {interpretation.warnings.map((w) => (
                      <li key={w}>{w}</li>
                    ))}
                  </ul>
                </div>
              ) : null}
              <p className="muted small">
                Interpretation is separate from builder state until APPLY (action rail).
              </p>
            </div>
          ) : null}
        </section>

        <section>
          <h2>Research Object Builder</h2>
          <p className="muted">Define an empirical phenomenon. One research_spec. No silent math.</p>
          <ResearchCheckpoint
            validationFreshness={validationFreshness}
            executionFreshness={executionFreshness}
            validationStatus={validation?.status ?? null}
            executionStatus={
              executionFreshness === "NONE"
                ? null
                : executionFreshness === "STALE"
                  ? "PRIOR"
                  : "COMPLETE"
            }
            capabilitySummary={capabilitySummary}
            capabilitiesLoading={capabilitiesLoading}
            capabilitiesError={capabilitiesError}
          />
          <ResearchCapabilityPanel
            preview={capabilityPreview}
            capabilities={capabilities}
            loading={capabilitiesLoading}
            error={capabilitiesError}
          />
          {validationFreshness === "STALE" && vsValidated.changed_count > 0 ? (
            <>
              <ResearchSpecDiffView
                title={`SPEC CHANGED SINCE VALIDATION · ${vsValidated.changed_count} CHANGES`}
                diff={vsValidated}
              />
              <div className="row ws-stale-actions">
                {onRevertToValidated ? (
                  <button type="button" className="btn-primary" onClick={onRevertToValidated}>
                    Revert to validated
                  </button>
                ) : null}
                {onReloadTemplate ? (
                  <button type="button" className="btn-secondary" onClick={onReloadTemplate}>
                    Reload template
                  </button>
                ) : null}
                <button type="button" className="btn-secondary" onClick={() => void validate()}>
                  Revalidate current
                </button>
              </div>
            </>
          ) : null}
          <div className="row">
            <label>
              Template
              <select
                defaultValue=""
                onChange={(e) => {
                  if (e.target.value) loadTemplate(e.target.value as string);
                  e.target.value = "";
                }}
              >
                <option value="" disabled>
                  Load template…
                </option>
                <option value="BLANK">Blank</option>
                {templates
                  .filter((t) => !/FIRST80/i.test(`${t.id} ${t.label}`))
                  .map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.label}
                    </option>
                  ))}
              </select>
            </label>
            <p className="muted small" style={{ margin: 0, alignSelf: "center" }}>
              Production run is NBA, MLB, NCAAB, ATP, or WTA warehouse Confirm → Run. FIRST80 / Confirm & Run is not a path.
            </p>
          </div>
          {runBusy ? (
            <div className="notice">
              VALIDATED → RESOLVING BINDING → EXECUTING AUTHORITATIVE ROUTE
              <div className="muted small">UI busy indicator — backend does not stream stages.</div>
            </div>
          ) : null}
          {error ? <div className="error">{error}</div> : null}
        </section>

        <BuilderSection id="A" title="A · Identity" summary={summaries.A} open={openSections.A} onToggle={() => toggleSection("A")}>
          <div className="row">
            <label className="grow">
              Name
              <input
                value={String(identity.name ?? "")}
                onChange={(e) => setIdentity("name", e.target.value)}
              />
            </label>
          </div>
          <label className="block-label">
            Description
            <textarea
              value={String(identity.description ?? "")}
              onChange={(e) => setIdentity("description", e.target.value)}
              rows={2}
            />
          </label>
          <label className="block-label">
            Tags (comma-separated)
            <input
              value={(asArr(identity.tags) as string[]).join(", ")}
              onChange={(e) =>
                setIdentity(
                  "tags",
                  e.target.value
                    .split(",")
                    .map((x) => x.trim())
                    .filter(Boolean),
                )
              }
            />
          </label>
        </BuilderSection>

        <BuilderSection id="B" title="B · Universe / Population" summary={summaries.B} open={openSections.B} onToggle={() => toggleSection("B")}>
          <div className="meta">Universe: {String(spec.universe ?? "BBALL1")}</div>
          {lockedLeagues ? (
            <p className="notice">
              League locked by template binding ({lockedLeagues.join(" · ")}). Accidental multi-league
              edits are disabled — use Reload template if the study drifted.
            </p>
          ) : null}
          <div className="chip-row">
            {LEAGUES.map((l) => (
              <button
                key={l}
                type="button"
                className={leagues.includes(l) ? "chip on" : "chip"}
                onClick={() => toggleLeague(l)}
                disabled={Boolean(lockedLeagues)}
                title={
                  lockedLeagues
                    ? `Locked to ${lockedLeagues.join(", ")} by authoritative template`
                    : undefined
                }
              >
                {l}
              </button>
            ))}
          </div>
          <div className="chip-row">
            {SLICES.map((s) => (
              <button
                key={s}
                type="button"
                className={slices.includes(s) ? "chip on" : "chip"}
                onClick={() => toggleSlice(s)}
              >
                {s}
              </button>
            ))}
          </div>
          <CalendarScopePicker
            spec={spec}
            setSpec={setSpec}
            locked={Boolean(lockedLeagues)}
          />
          <div className="row">
            <label>
              P5 vs P5
              <select
                value={population.p5_vs_p5_only ? "true" : "false"}
                onChange={(e) => setPopulation("p5_vs_p5_only", e.target.value === "true")}
              >
                <option value="false">false</option>
                <option value="true">true</option>
              </select>
            </label>
            <label>
              Selection
              <select
                value={String(population.selection ?? "all_matching")}
                onChange={(e) => setPopulation("selection", e.target.value)}
              >
                <option value="all_matching">all_matching</option>
                <option value="locked_population">locked_population</option>
                <option value="explicit_ids">explicit_ids</option>
              </select>
            </label>
            <label className="grow">
              Locked Population ID
              <input
                value={
                  population.locked_population_id == null
                    ? ""
                    : String(population.locked_population_id)
                }
                onChange={(e) =>
                  setPopulation("locked_population_id", e.target.value || null)
                }
                placeholder="do not fabricate"
              />
            </label>
          </div>
        </BuilderSection>

        <BuilderSection id="C" title="C · Anchor" summary={summaries.C} open={openSections.C} onToggle={() => toggleSection("C")}>
          <div className="row">
            <label>
              Event
              <select
                value={String(anchor.event ?? "OBSERVATION_TIME")}
                onChange={(e) => setAnchor("event", e.target.value)}
              >
                <option value="FIRST_PRICE_TOUCH">FIRST_PRICE_TOUCH</option>
                <option value="OBSERVATION_TIME">OBSERVATION_TIME</option>
                <option value="PRICE_MOVE">PRICE_MOVE</option>
              </select>
            </label>
          </div>
          {anchor.event === "FIRST_PRICE_TOUCH" ? (
            <div className="row">
              <label>
                price_e4
                <input
                  type="number"
                  value={anchor.price_e4 == null ? "" : String(anchor.price_e4)}
                  onChange={(e) =>
                    setAnchor("price_e4", e.target.value === "" ? null : Number(e.target.value))
                  }
                />
              </label>
              <label>
                price_field
                <select
                  value={String(anchor.price_field ?? "yes_bid_close")}
                  onChange={(e) => setAnchor("price_field", e.target.value)}
                >
                  <option value="yes_bid_close">yes_bid_close</option>
                  <option value="yes_ask_close">yes_ask_close</option>
                  <option value="yes_bid_low">yes_bid_low</option>
                  <option value="yes_bid_high">yes_bid_high</option>
                </select>
              </label>
              <label>
                requires_seen_below
                <select
                  value={anchor.requires_seen_below ? "true" : "false"}
                  onChange={(e) => setAnchor("requires_seen_below", e.target.value === "true")}
                >
                  <option value="true">true</option>
                  <option value="false">false</option>
                </select>
              </label>
            </div>
          ) : null}
          {anchor.event === "PRICE_MOVE" ? (
            <div className="row">
              <label>
                direction
                <select
                  value={String(anchor.direction ?? "DOWN")}
                  onChange={(e) => setAnchor("direction", e.target.value)}
                >
                  <option value="UP">UP</option>
                  <option value="DOWN">DOWN</option>
                  <option value="ABS">ABS</option>
                  <option value="UNRESOLVED">UNRESOLVED</option>
                </select>
              </label>
              <label>
                magnitude_e4 (empty = unresolved)
                <input
                  type="number"
                  value={
                    unresolvedParams.includes("magnitude_e4") || anchor.magnitude_e4 == null
                      ? ""
                      : String(anchor.magnitude_e4)
                  }
                  onChange={(e) => setAnchor("magnitude_e4", e.target.value)}
                  placeholder="do not invent"
                />
              </label>
            </div>
          ) : null}
        </BuilderSection>

        <BuilderSection id="D" title="D · Information" summary={summaries.D} open={openSections.D} onToggle={() => toggleSection("D")}>
          <div className="row">
            <label>
              information_regime
              <select
                value={String(spec.information_regime ?? "POINT_IN_TIME")}
                onChange={(e) => patch((p) => ({ ...p, information_regime: e.target.value }))}
              >
                {[
                  "CANDLE_1M",
                  "POINT_IN_TIME",
                  "FROZEN_ARTIFACT",
                  "FULL_HISTORY",
                  "BOOK_SNAPSHOT",
                  "UNRESOLVED",
                ].map((x) => (
                  <option key={x} value={x}>
                    {x}
                  </option>
                ))}
              </select>
            </label>
            <label>
              information_set
              <select
                value={String(spec.information_set ?? "O_t")}
                onChange={(e) => patch((p) => ({ ...p, information_set: e.target.value }))}
              >
                {["I_t_anchor", "O_t", "L_forward", "FROZEN", "UNRESOLVED"].map((x) => (
                  <option key={x} value={x}>
                    {x}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </BuilderSection>

        <BuilderSection id="E" title="E · State conditions" summary={summaries.E} open={openSections.E} onToggle={() => toggleSection("E")}>
          {(() => {
            const sf = asObj(spec.state_filters);
            const hasMass =
              sf.op === "ATOM"
                ? Boolean(sf.field)
                : asArr(sf.args).length > 0;
            return (
              <>
                {!hasMass ? (
                  <div className="conditional-structure empty">NO CONDITIONS DEFINED</div>
                ) : null}
                <div className={hasMass ? "conditional-structure" : undefined}>
                  <StateFilterEditor
                    value={sf}
                    onChange={(next) => patch((p) => ({ ...p, state_filters: next }))}
                  />
                </div>
              </>
            );
          })()}
        </BuilderSection>

        <BuilderSection id="F" title="F · Path conditions" summary={summaries.F} open={openSections.F} onToggle={() => toggleSection("F")}>
          {pathConditions.length === 0 ? (
            <div className="conditional-structure empty">NO CONDITIONS DEFINED</div>
          ) : (
            <div className="conditional-structure">
              {pathConditions.map((cond, i) => (
                <div className="row" key={i}>
                  <label>
                    kind
                    <select
                      value={String(cond.kind ?? "UNRESOLVED")}
                      onChange={(e) => {
                        const next = [...pathConditions];
                        next[i] = { ...cond, kind: e.target.value };
                        patch((p) => ({ ...p, path_conditions: next }));
                      }}
                    >
                      {PATH_KINDS.map((k) => (
                        <option key={k} value={k}>
                          {k}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    price_e4
                    <input
                      type="number"
                      value={cond.price_e4 == null ? "" : String(cond.price_e4)}
                      onChange={(e) => {
                        const next = [...pathConditions];
                        next[i] = {
                          ...cond,
                          price_e4: e.target.value === "" ? null : Number(e.target.value),
                        };
                        patch((p) => ({ ...p, path_conditions: next }));
                      }}
                    />
                  </label>
                  <label>
                    binding
                    <input
                      value={String(cond.binding ?? "")}
                      onChange={(e) => {
                        const next = [...pathConditions];
                        next[i] = { ...cond, binding: e.target.value || undefined };
                        patch((p) => ({ ...p, path_conditions: next }));
                      }}
                    />
                  </label>
                  <button
                    type="button"
                    onClick={() =>
                      patch((p) => ({
                        ...p,
                        path_conditions: pathConditions.filter((_, j) => j !== i),
                      }))
                    }
                  >
                    ×
                  </button>
                </div>
              ))}
            </div>
          )}
          <button
            type="button"
            className="btn-secondary"
            onClick={() =>
              patch((p) => ({
                ...p,
                path_conditions: [...pathConditions, { kind: "EVER_CLOSE_LE", price_e4: 4000 }],
              }))
            }
          >
            + Path condition
          </button>
        </BuilderSection>

        <BuilderSection id="G" title="G · Terminal conditions" summary={summaries.G} open={openSections.G} onToggle={() => toggleSection("G")}>
          {terminalConditions.length === 0 ? (
            <div className="conditional-structure empty">NO CONDITIONS DEFINED</div>
          ) : (
            <div className="conditional-structure">
              {terminalConditions.map((cond, i) => (
                <div className="row" key={i}>
                  <label>
                    kind
                    <select
                      value={String(cond.kind ?? "UNRESTRICTED")}
                      onChange={(e) => {
                        const next = [...terminalConditions];
                        next[i] = { ...cond, kind: e.target.value };
                        patch((p) => ({ ...p, terminal_conditions: next }));
                      }}
                    >
                      {TERMINAL_KINDS.map((k) => (
                        <option key={k} value={k}>
                          {k}
                        </option>
                      ))}
                    </select>
                  </label>
                  <button
                    type="button"
                    onClick={() =>
                      patch((p) => ({
                        ...p,
                        terminal_conditions: terminalConditions.filter((_, j) => j !== i),
                      }))
                    }
                  >
                    ×
                  </button>
                </div>
              ))}
            </div>
          )}
          <button
            type="button"
            className="btn-secondary"
            onClick={() =>
              patch((p) => ({
                ...p,
                terminal_conditions: [...terminalConditions, { kind: "KALSHI_YES" }],
              }))
            }
          >
            + Terminal condition
          </button>
        </BuilderSection>

        <BuilderSection id="H" title="H · Measurements" summary={hSummary} open={openSections.H} onToggle={() => toggleSection("H")}>
          <p className="muted">MEASUREMENT ≠ EDGE · unknown names remain representable (UNSUPPORTED)</p>
          {knownMeasurements.length > 0 ? (
            <div className="row">
              <label>
                Insert known measurement (convenience only)
                <select
                  defaultValue=""
                  onChange={(e) => {
                    const name = e.target.value;
                    e.target.value = "";
                    if (!name) return;
                    patch((p) => ({
                      ...p,
                      measurement_requests: [
                        ...asArr(p.measurement_requests),
                        { name, not_edge: true },
                      ],
                    }));
                  }}
                >
                  <option value="" disabled>
                    Registry names…
                  </option>
                  {knownMeasurements.map((km) => (
                    <option key={km.name} value={km.name}>
                      {km.status === "IMPLEMENTED" ? "IMPLEMENTED" : "REGISTERED"} · {km.name}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          ) : null}
          <datalist id="known-measurement-names">
            {knownMeasurements.map((km) => (
              <option key={km.name} value={km.name} />
            ))}
          </datalist>
          {measurements.map((m, i) => (
            <div className="row" key={i}>
              <label>
                name
                <input
                  list="known-measurement-names"
                  value={String(m.name ?? "")}
                  onChange={(e) => {
                    const next = [...measurements];
                    next[i] = { ...m, name: e.target.value, not_edge: true };
                    patch((p) => ({ ...p, measurement_requests: next }));
                  }}
                />
              </label>
              <label>
                binding
                <input
                  value={String(m.binding ?? "")}
                  onChange={(e) => {
                    const next = [...measurements];
                    next[i] = { ...m, binding: e.target.value, not_edge: true };
                    patch((p) => ({ ...p, measurement_requests: next }));
                  }}
                />
              </label>
              <button
                type="button"
                onClick={() =>
                  patch((p) => ({
                    ...p,
                    measurement_requests: measurements.filter((_, j) => j !== i),
                  }))
                }
              >
                ×
              </button>
            </div>
          ))}
          <button
            type="button"
            onClick={() =>
              patch((p) => ({
                ...p,
                measurement_requests: [
                  ...measurements,
                  { name: "fundamental", binding: "roller_4.0.0-A", not_edge: true },
                ],
              }))
            }
          >
            + Measurement
          </button>
        </BuilderSection>

        <BuilderSection id="I" title="I · Bindings" summary={summaries.I} open={openSections.I} onToggle={() => toggleSection("I")}>
          <label className="block-label">
            execution_interpretation
            <select
              value={String(spec.execution_interpretation ?? "OBSERVABLE_PATH_ONLY")}
              onChange={(e) =>
                patch((p) => ({ ...p, execution_interpretation: e.target.value }))
              }
            >
              {[
                "OBSERVABLE_PATH_ONLY",
                "CANDLE_PATH_PROXY",
                "EXECUTION_VALIDATED",
                "UNRESOLVED",
              ].map((x) => (
                <option key={x} value={x}>
                  {x}
                </option>
              ))}
            </select>
          </label>
          <label className="block-label">
            definition_versions (JSON object)
            <textarea
              rows={4}
              value={JSON.stringify(spec.definition_versions ?? {}, null, 2)}
              onChange={(e) => {
                try {
                  const parsed = JSON.parse(e.target.value);
                  patch((p) => ({ ...p, definition_versions: parsed }));
                } catch {
                  /* keep typing */
                }
              }}
            />
          </label>
          <label className="block-label">
            caveats (one per line)
            <textarea
              rows={3}
              value={(asArr(spec.caveats) as string[]).join("\n")}
              onChange={(e) =>
                patch((p) => ({
                  ...p,
                  caveats: e.target.value.split("\n").filter((x) => x.trim()),
                }))
              }
            />
          </label>
        </BuilderSection>
      </div>

      <div className="ro-right">
        <section className="research-object">
          <h2>Canonical research_spec</h2>
          <p className="muted">Exact object submitted to validate</p>
          <pre className="spec-json">{jsonText}</pre>
        </section>

        <section className="research-object" ref={validationRef} tabIndex={-1} id="validation-panel">
          <h2>Validation</h2>
          {validationFreshness === "STALE" && validation ? (
            <div className="stale-banner stale-workflow">
              <div className="status-banner status-stale">CURRENT SPEC CHANGED</div>
              <div>VALIDATION IS STALE</div>
              {vsValidated.changed_count > 0 ? (
                <div className="muted">{vsValidated.changed_count} FIELDS DIFFER</div>
              ) : null}
              <p className="notice">REVALIDATE REQUIRED</p>
              <div className="muted small">
                Prior status was {validation.status} · id {validation.research_object_id ?? "—"}
              </div>
              <div className="muted small mono">fp {validationSnapshot?.specFingerprint}</div>
            </div>
          ) : validationFreshness === "CURRENT" && validation ? (
            <>
              <div className={`status-banner status-${validation.status.toLowerCase()}`}>
                SPEC STATUS: {validation.status}
              </div>
              <div className="muted">
                valid={String(validation.valid)} · runnable={String(validation.runnable)} · freshness=CURRENT
              </div>
              <div className="mono">{validation.research_object_id ?? "—"}</div>
              <div className="muted small mono">fp {currentSpecFingerprint}</div>
              {validation.errors.length ? (
                <ul>
                  {validation.errors.map((err) => (
                    <li key={err} className="error-item">
                      {err}
                    </li>
                  ))}
                </ul>
              ) : null}
              {validation.unresolved.length ? (
                <ul>
                  {validation.unresolved.map((u) => (
                    <li key={u.field}>
                      <strong>{u.field}</strong>: {u.reason}
                    </li>
                  ))}
                </ul>
              ) : null}
            </>
          ) : (
            <div className="muted">
              SPEC STATUS: UNVALIDATED · Press VALIDATE to check schema + runnability.
            </div>
          )}
          {executionFreshness === "STALE" ? (
            <div className="stale-banner" style={{ marginTop: "0.75rem" }}>
              <div className="status-banner status-stale">EXECUTION: STALE</div>
              <div className="muted small">PRIOR RESULT PRESERVED FOR INSPECTION</div>
            </div>
          ) : null}
        </section>

        <section className="research-object">
          <h2>Research Object Inspector</h2>
          <p className="muted">Structural only — not the Phase 1 empirical O_t inspector</p>
          {preview ? (
            <div className="inspector-grid">
              <div className="block">
                <h3>IDENTITY</h3>
                <pre>{JSON.stringify(preview.identity, null, 2)}</pre>
              </div>
              <div className="block">
                <h3>UNIVERSE / POPULATION</h3>
                <pre>
                  {JSON.stringify(
                    { universe: preview.universe, population: preview.population },
                    null,
                    2,
                  )}
                </pre>
              </div>
              <div className="block">
                <h3>ANCHOR</h3>
                <pre>{JSON.stringify(preview.anchor, null, 2)}</pre>
              </div>
              <div className="block">
                <h3>INFORMATION</h3>
                <pre>{JSON.stringify(preview.information, null, 2)}</pre>
              </div>
              <div className="block">
                <h3>STATE / PATH / TERMINAL</h3>
                <pre>
                  {JSON.stringify(
                    { state: preview.state, path: preview.path, terminal: preview.terminal },
                    null,
                    2,
                  )}
                </pre>
              </div>
              <div className="block">
                <h3>MEASUREMENTS / BINDINGS</h3>
                <pre>
                  {JSON.stringify(
                    {
                      measurements: preview.measurements,
                      definition_versions: preview.definition_versions,
                      dataset_versions: preview.dataset_versions,
                      execution_interpretation: preview.execution_interpretation,
                      caveats: preview.caveats,
                      status: preview.status,
                      runnable: preview.runnable,
                    },
                    null,
                    2,
                  )}
                </pre>
              </div>
            </div>
          ) : (
            <div className="muted">Validate to populate structural inspector.</div>
          )}
        </section>
      </div>
      </div>
    </div>
  );
}

function StateFilterEditor({
  value,
  onChange,
}: {
  value: Record<string, unknown>;
  onChange: (next: Record<string, unknown>) => void;
}) {
  const op = String(value.op ?? "AND");
  const args = asArr(value.args) as Record<string, unknown>[];

  if (op === "ATOM") {
    return (
      <div className="row">
        <label>
          field
          <input
            value={String(value.field ?? "")}
            onChange={(e) => onChange({ ...value, op: "ATOM", field: e.target.value })}
          />
        </label>
        <label>
          operator
          <select
            value={String(value.operator ?? "eq")}
            onChange={(e) => onChange({ ...value, op: "ATOM", operator: e.target.value })}
          >
            {OPERATORS.map((o) => (
              <option key={o} value={o}>
                {o}
              </option>
            ))}
          </select>
        </label>
        <label>
          value
          <input
            value={
              typeof value.value === "string" || typeof value.value === "number"
                ? String(value.value)
                : JSON.stringify(value.value ?? "")
            }
            onChange={(e) => {
              let parsed: unknown = e.target.value;
              try {
                parsed = JSON.parse(e.target.value);
              } catch {
                parsed = e.target.value;
              }
              onChange({ ...value, op: "ATOM", value: parsed });
            }}
          />
        </label>
      </div>
    );
  }

  return (
    <div>
      <div className="row">
        <label>
          op
          <select
            value={op}
            onChange={(e) => {
              const nextOp = e.target.value;
              if (nextOp === "ATOM") {
                onChange({ op: "ATOM", field: "entry_slice", operator: "eq", value: "Q3" });
              } else if (nextOp === "NOT") {
                onChange({
                  op: "NOT",
                  args: args[0] ? [args[0]] : [{ op: "ATOM", field: "period", operator: "eq", value: "Q4" }],
                });
              } else {
                onChange({ op: nextOp, args });
              }
            }}
          >
            <option value="AND">AND</option>
            <option value="OR">OR</option>
            <option value="NOT">NOT</option>
            <option value="ATOM">ATOM</option>
          </select>
        </label>
        {op !== "NOT" ? (
          <button
            type="button"
            onClick={() =>
              onChange({
                ...value,
                args: [
                  ...args,
                  { op: "ATOM", field: "entry_slice", operator: "eq", value: "Q3" },
                ],
              })
            }
          >
            + Atom
          </button>
        ) : null}
      </div>
      {args.map((child, i) => (
        <div key={i} className="nested">
          <StateFilterEditor
            value={asObj(child)}
            onChange={(nextChild) => {
              const nextArgs = [...args];
              nextArgs[i] = nextChild;
              onChange({ ...value, args: nextArgs });
            }}
          />
          <button
            type="button"
            onClick={() =>
              onChange({ ...value, args: args.filter((_, j) => j !== i) })
            }
          >
            remove
          </button>
        </div>
      ))}
    </div>
  );
}
