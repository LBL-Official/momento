import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import ResearchObjectBuilder from "./ResearchObjectBuilder";
import ResearchAuditStrip from "./components/ResearchAuditStrip";
import ResultsView, { type ResearchResult } from "./ResultsView";
import DetailDrawer, { type DetailPayload } from "./v2/components/DetailDrawer";
import {
  analyzeResearchCapabilities,
  formatCapabilitySummary,
  type ResearchCapabilitiesPayload,
} from "./researchCapabilityPreview";
import {
  getExecutionFreshness,
  getValidationFreshness,
  snapshotDraftFingerprint,
  stableDraftFingerprint,
  stableSpecFingerprint,
  type ResultSnapshot,
  type ValidationSnapshot,
} from "./researchFreshness";
import {
  asObj,
  blankSpec,
  type InterpretResult,
  type Spec,
} from "./researchTypes";
import AppHeader from "./v2/components/AppHeader";
import ResearchSidebar from "./v2/shell/ResearchSidebar";
import AppShell from "./v2/shell/AppShell";
import { TEMPLATE_CATALOG, type CatalogTemplate } from "./v2/templateCatalog";
import {
  inferFolder,
  libraryEntryKind,
  loadLibrary,
  saveCurrentObject,
  saveImmutableResult,
  saveQuestionDraft,
  touchEntry,
  type LibraryEntry,
} from "./v2/researchLibrary";
import { loadSession, saveSession } from "./v2/researchSession";
import TemplatesView from "./v2/views/TemplatesView";
import ResultsLabsView from "./v2/warehouse/ResultsLabsView";
import DictionaryView from "./v2/views/DictionaryView";
import DocsView from "./v2/views/DocsView";
import AutoRollerView from "./v2/views/AutoRollerView";
import SettingsView from "./v2/views/SettingsView";
import PhenomenaView from "./v2/views/PhenomenaView";
import LabWorkspace from "./v2/lab/LabWorkspace";
import ResultsAnswer, { type AnswerResult } from "./v2/results/ResultsAnswer";
import { humanResearchStatus } from "./v2/researchStatus";
import {
  apiFetch,
  classifyApiFailure,
  probeApiHealth,
  type ApiAvailability,
} from "./api/base";
import { loadServerSave, saveResultToServer } from "./api/researchQuery";
import { compileWarehouseResearch, executeWarehouseResearch } from "./api/warehouseResearch";
import { importMeasurement } from "./superasi/api/superasiApi";
import WarehouseResults, { isWarehouseResult } from "./v2/warehouse/WarehouseResults";
import {
  isWarehouseDeskDraft,
  researchQuestionFromDraft,
} from "./v2/warehouse/researchQuestionFromDraft";
import { DEFAULT_ROUTE, normalizeRoute, type AppRoute } from "./v2/navigation";
import { emptyIntent } from "./v2/define/recognizedIntent";
import { specWithoutInventedSeasons } from "./v2/define/honesty";
import SaveResultsModal from "./v2/results/SaveResultsModal";
import { buildSavedSnapshot, compactResultSnapshot } from "./v2/results/savedSnapshot";
import {
  buildAggregateCsv,
  buildConstraintsJson,
  buildResultsJson,
  buildTradeLogCsv,
  buildWorkflowMarkdown,
  downloadText,
} from "./v2/results/markdownReport";
import ResultsMathStack from "./v2/results/ResultsMathStack";
import QuickStartScreen from "./v2/workflow/QuickStartScreen";
import EntryConditionsScreen from "./v2/workflow/EntryConditionsScreen";
import ExitConditionsScreen from "./v2/workflow/ExitConditionsScreen";
import ConfirmScreen from "./v2/workflow/ConfirmScreen";
import { emptyDraft, stripIncompleteHorizons } from "./v2/workflow/draft";
import {
  applyResolutionToDraft,
  intentFromResolution,
} from "./v2/workflow/constructibility";
import { resolveResearchPlan } from "./v2/workflow/resolveResearchPlan";
import { composeQuestionFromDraft } from "./v2/workflow/questionFromDraft";
import type { WorkflowDraft } from "./v2/workflow/types";
import SuperASIApp from "./superasi/SuperASIApp";
import JumpApp from "./jump/JumpApp";
import { openVitalDashboard } from "./origins";
import type { StaxRoute } from "./stax/types";

type ResearchProduct = "roller" | "superasi" | "jump";

function productFromLocation(): ResearchProduct {
  const app = new URLSearchParams(window.location.search).get("app");
  if (app === "jump" || app === "superasi") return app;
  return "roller";
}

type GameRow = {
  internal_game_id: string;
  sport: string;
  season: number;
  home_team: string;
  away_team: string;
};

type ExplorerResponse = {
  as_of: string;
  information_mode: string;
  count: number;
  games: GameRow[];
};

type ObjectPayload = {
  as_of: string;
  object: {
    identity: { home_team: string; away_team: string; sport: string; season: number };
    market_state?: { first_half_winner?: { yes_bid?: number | null; yes_ask?: number | null } };
    event_state?: { first_half?: { home_score?: number | null; away_score?: number | null } };
  };
};

type ResearchContext = {
  internal_game_id: string;
  as_of: string;
  sport: string;
  season: number;
};

type BackendTemplate = {
  id: string;
  label: string;
  research_spec: Spec;
};

export default function App() {
  const [route, setRoute] = useState<AppRoute>(DEFAULT_ROUTE);
  const [labAdvanced, setLabAdvanced] = useState(false);
  const [workflowDraft, setWorkflowDraft] = useState<WorkflowDraft>(
    () => stripIncompleteHorizons(loadSession().workflowDraft ?? emptyDraft()),
  );
  const [acceptLimitations, setAcceptLimitations] = useState(false);
  const [warehouseCompile, setWarehouseCompile] = useState<import("./api/warehouseResearch").WarehouseCompile | null>(
    null,
  );
  const [warehouseBusy, setWarehouseBusy] = useState(false);
  const [apiAvailability, setApiAvailability] = useState<ApiAvailability | null>(null);
  const [recognizedIntent, setRecognizedIntent] = useState(
    () => loadSession().recognizedIntent ?? emptyIntent(),
  );
  const [viewingSaved, setViewingSaved] = useState(false);
  const [viewingSavedAt, setViewingSavedAt] = useState<string | null>(null);
  const [saveModalOpen, setSaveModalOpen] = useState(false);
  const [saveBusy, setSaveBusy] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [detail, setDetail] = useState<DetailPayload | null>(null);
  const [docsInitial, setDocsInitial] = useState<string | undefined>(undefined);
  const [product, setProduct] = useState<ResearchProduct>(productFromLocation);
  const goProduct = useCallback((next: ResearchProduct) => {
    setProduct(next);
    const url = new URL(window.location.href);
    if (next === "roller") url.searchParams.delete("app");
    else url.searchParams.set("app", next);
    window.history.replaceState({}, "", `${url.pathname}${url.search}${url.hash}`);
  }, []);
  useEffect(() => {
    if (new URLSearchParams(window.location.search).get("app") === "vital") {
      openVitalDashboard();
    }
  }, []);
  const [researchMode, setResearchMode] = useState<"quickstart" | "stax">("quickstart");
  const [staxRoute, setStaxRoute] = useState<StaxRoute>("overview");
  const staxName = "Multi-strategy stack";
  const staxStrategyCount = 0;
  const [superasiPackageId, setSuperasiPackageId] = useState<string | null>(null);
  const [superasiImportNote, setSuperasiImportNote] = useState<string | null>(null);
  const [superasiLabId, setSuperasiLabId] = useState<string | null>(null);
  const [superasiBusy, setSuperasiBusy] = useState(false);

  const [spec, setSpec] = useState<Spec>(() => loadSession().spec);
  const [interpretation, setInterpretation] = useState<InterpretResult | null>(null);
  const [validationSnapshot, setValidationSnapshot] = useState<ValidationSnapshot | null>(
    () => loadSession().validationSnapshot,
  );
  const [resultSnapshot, setResultSnapshot] = useState<ResultSnapshot | null>(
    () => loadSession().resultSnapshot,
  );
  const [activeLibraryId, setActiveLibraryId] = useState<string | null>(
    () => loadSession().activeLibraryId,
  );
  const [researchContext, setResearchContext] = useState<ResearchContext | null>(null);
  const [runBusy, setRunBusy] = useState(false);
  const runBusyRef = useRef(false);

  const [asOf, setAsOf] = useState("2025-10-11");
  const [objectAsOf, setObjectAsOf] = useState("2025-10-10T23:15:00Z");
  const [explorer, setExplorer] = useState<ExplorerResponse | null>(null);
  const [selected, setSelected] = useState<GameRow | null>(null);
  const [objectPayload, setObjectPayload] = useState<ObjectPayload | null>(null);
  const [exploreError, setExploreError] = useState<string | null>(null);
  const [objectError, setObjectError] = useState<string | null>(null);
  const [exploreLoading, setExploreLoading] = useState(false);
  const [objectLoading, setObjectLoading] = useState(false);
  const [nlPrompt, setNlPrompt] = useState("");
  const [nlMessage, setNlMessage] = useState<string | null>(null);
  const [showValidatedJson, setShowValidatedJson] = useState(false);
  const [capabilities, setCapabilities] = useState<ResearchCapabilitiesPayload | null>(null);
  const [capabilitiesLoading, setCapabilitiesLoading] = useState(true);
  const [capabilitiesError, setCapabilitiesError] = useState<string | null>(null);
  const [backendTemplates, setBackendTemplates] = useState<BackendTemplate[]>([]);
  const [libraryTick, setLibraryTick] = useState(0);
  const [activeTemplateId, setActiveTemplateId] = useState<string | null>(
    () => loadSession().activeTemplateId,
  );
  const builderActionsRef = useRef<{
    validate: () => Promise<unknown>;
    run: () => Promise<void>;
    validateAndRun: () => Promise<void>;
  } | null>(null);
  const builderHostRef = useRef<HTMLDivElement | null>(null);
  const sessionReady = useRef(false);
  const runResearchRef = useRef<(() => Promise<void>) | null>(null);

  useEffect(() => {
    const el = builderHostRef.current;
    if (!el) return;
    const show = route === "start" && labAdvanced;
    if (show) el.removeAttribute("inert");
    else el.setAttribute("inert", "");
  }, [route, labAdvanced]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!(e.metaKey || e.ctrlKey) || e.key !== "Enter") return;
      if (route !== "confirm") return;
      const t = e.target as HTMLElement | null;
      if (t && (t.tagName === "TEXTAREA" || t.isContentEditable)) return;
      e.preventDefault();
      void runResearchRef.current?.();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [route]);

  useEffect(() => {
    runBusyRef.current = runBusy;
  }, [runBusy]);

  useEffect(() => {
    let cancelled = false;
    const apply = (status: ApiAvailability) => {
      if (cancelled) return;
      if (status !== "API_REACHABLE" && runBusyRef.current) return;
      setApiAvailability(status);
    };
    void probeApiHealth().then(apply);
    const tick = window.setInterval(() => {
      void probeApiHealth().then(apply);
    }, 10000);
    return () => {
      cancelled = true;
      window.clearInterval(tick);
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    setCapabilitiesLoading(true);
    setCapabilitiesError(null);
    apiFetch("/research-capabilities")
      .then(async (r) => {
        if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
        return r.json();
      })
      .then((body) => {
        if (!cancelled) {
          setCapabilities(body as ResearchCapabilitiesPayload);
          setApiAvailability("API_REACHABLE");
        }
      })
      .catch((e) => {
        if (!cancelled) {
          setCapabilities(null);
          setCapabilitiesError(classifyApiFailure(e));
        }
      })
      .finally(() => {
        if (!cancelled) setCapabilitiesLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    apiFetch("/research-object-templates")
      .then(async (r) => {
        if (!r.ok) throw new Error(`${r.status}`);
        return r.json();
      })
      .then((body) => {
        if (!cancelled) setBackendTemplates(body as BackendTemplate[]);
      })
      .catch(() => {
        if (!cancelled) {
          setBackendTemplates([]);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const libraryState = useMemo(() => {
    void libraryTick;
    return loadLibrary();
  }, [libraryTick]);

  const currentSpecFingerprint = useMemo(() => stableSpecFingerprint(spec), [spec]);
  const capabilityPreview = useMemo(
    () => analyzeResearchCapabilities(spec, capabilities),
    [spec, capabilities],
  );
  const capabilitySummaryLine = useMemo(
    () => formatCapabilitySummary(capabilityPreview),
    [capabilityPreview],
  );
  const validationFreshness = useMemo(
    () => getValidationFreshness(currentSpecFingerprint, validationSnapshot),
    [currentSpecFingerprint, validationSnapshot],
  );
  const researchDraft = useMemo(
    () => stripIncompleteHorizons(workflowDraft),
    [workflowDraft],
  );
  const currentDraftFingerprint = useMemo(
    () => stableDraftFingerprint(researchDraft),
    [researchDraft],
  );
  const executionFreshness = useMemo(
    () => getExecutionFreshness(currentSpecFingerprint, resultSnapshot, currentDraftFingerprint),
    [currentSpecFingerprint, currentDraftFingerprint, resultSnapshot],
  );
  const resolution = useMemo(
    () => resolveResearchPlan(researchDraft, { acceptLimitations }),
    [researchDraft, acceptLimitations],
  );
  const warehouseBuilt = useMemo(() => researchQuestionFromDraft(researchDraft), [researchDraft]);
  const warehouseDesk = isWarehouseDeskDraft(researchDraft);
  const warehouseOpts = useMemo(
    () => ({
      teFilters: researchDraft.teFilters,
      exposureUnit: researchDraft.exposureUnit,
      maxEntriesPerGame: researchDraft.maxEntriesPerGame,
      exposureEnforcementMode: researchDraft.exposureEnforcementMode,
    }),
    [
      researchDraft.teFilters,
      researchDraft.exposureUnit,
      researchDraft.maxEntriesPerGame,
      researchDraft.exposureEnforcementMode,
    ],
  );
  const canRun = useMemo(() => {
    return (
      warehouseDesk &&
      warehouseBuilt.errors.length === 0 &&
      warehouseCompile?.status === "READY"
    );
  }, [warehouseBuilt.errors.length, warehouseCompile?.status, warehouseDesk]);
  const humanQuestion = useMemo(
    () => composeQuestionFromDraft(researchDraft, resolution),
    [researchDraft, resolution],
  );

  useEffect(() => {
    if (researchDraft !== workflowDraft) setWorkflowDraft(researchDraft);
  }, [researchDraft, workflowDraft]);

  useEffect(() => {
    if (route !== "confirm" || !warehouseDesk) {
      setWarehouseCompile(null);
      return;
    }
    let cancelled = false;
    setWarehouseBusy(true);
    compileWarehouseResearch(warehouseBuilt.question, warehouseOpts)
      .then((body) => {
        if (!cancelled) {
          setWarehouseCompile(body);
          setApiAvailability("API_REACHABLE");
        }
      })
      .catch((e) => {
        if (!cancelled) {
          setWarehouseCompile(null);
          if (!runBusyRef.current) setApiAvailability(classifyApiFailure(e));
        }
      })
      .finally(() => {
        if (!cancelled) setWarehouseBusy(false);
      });
    return () => {
      cancelled = true;
    };
  }, [route, warehouseDesk, warehouseBuilt.question, warehouseOpts]);

  const go = useCallback((next: AppRoute) => {
    setRoute(normalizeRoute(next));
  }, []);

  const warehouseIdentity = useMemo(() => {
    const entry = researchDraft.entryConditions[0];
    if (!entry) return "NBA warehouse research";
    const fam = String(entry.family || "entry").replace(/_/g, " ");
    const price = entry.priceCents != null ? `${entry.priceCents}¢` : "";
    const period = entry.period || "";
    const league = researchDraft.universe.leagues[0] || researchDraft.universe.sports[0] || "NBA";
    return [league.toUpperCase() === "BASEBALL" ? "MLB" : league, fam, price, period].filter(Boolean).join(" ");
  }, [researchDraft]);
  const identityName = warehouseDesk
    ? warehouseIdentity
    : (asObj(spec.identity).name as string | undefined)?.trim() || "Untitled research object";
  const warehousePopulation = useMemo(() => {
    const payload = resultSnapshot?.payload;
    if (!payload || !isWarehouseResult(payload)) return null;
    const n = payload.results_contract?.statistics?.population ?? payload.results_contract?.population;
    return typeof n === "number" ? n : null;
  }, [resultSnapshot]);
  const populationN =
    warehousePopulation ??
    (resultSnapshot?.payload as ResearchResult | undefined)?.summary?.population_n ??
    (resultSnapshot?.payload as ResearchResult | undefined)?.population?.count ??
    null;

  const explore = useCallback(async () => {
    setExploreLoading(true);
    setExploreError(null);
    setObjectPayload(null);
    setSelected(null);
    try {
      const res = await apiFetch("/explorer/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          universe: "BBALL1",
          as_of: asOf,
          information_mode: "POINT_IN_TIME",
        }),
      });
      const body = await res.json();
      if (!res.ok) {
        throw new Error(body.detail || body.message || res.statusText);
      }
      setExplorer(body as ExplorerResponse);
    } catch (err) {
      setExplorer(null);
      setExploreError(err instanceof Error ? err.message : String(err));
    } finally {
      setExploreLoading(false);
    }
  }, [asOf]);

  const openObject = useCallback(
    async (row: GameRow) => {
      setSelected(row);
      setObjectLoading(true);
      setObjectError(null);
      setObjectPayload(null);
      try {
        const res = await apiFetch(
          `/objects/${encodeURIComponent(row.internal_game_id)}?as_of=${encodeURIComponent(objectAsOf)}&information_mode=POINT_IN_TIME`,
        );
        const body = await res.json();
        if (!res.ok) throw new Error(body.detail || body.message || res.statusText);
        setObjectPayload(body as ObjectPayload);
      } catch (err) {
        setObjectError(err instanceof Error ? err.message : String(err));
      } finally {
        setObjectLoading(false);
      }
    },
    [objectAsOf],
  );

  const useAsResearchContext = useCallback(() => {
    if (!objectPayload || !selected) return;
    setResearchContext({
      internal_game_id: selected.internal_game_id,
      as_of: objectPayload.as_of,
      sport: selected.sport,
      season: selected.season,
    });
    go("start");
    setLabAdvanced(false);
  }, [objectPayload, selected, go]);

  const interpretExplorer = useCallback(async () => {
    if (!nlPrompt.trim()) return;
    setNlMessage(null);
    try {
      const res = await apiFetch("/query/interpret", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: nlPrompt, current_spec: spec }),
      });
      const body = await res.json();
      if (!res.ok) throw new Error(body.detail || res.statusText);
      setInterpretation(body as InterpretResult);
      setNlMessage(`Interpret ${body.status}. Open Advanced details to APPLY.`);
      go("start");
      setLabAdvanced(true);
    } catch (err) {
      setNlMessage(err instanceof Error ? err.message : String(err));
    }
  }, [nlPrompt, spec, go]);

  useEffect(() => {
    if (!sessionReady.current) {
      sessionReady.current = true;
      return;
    }
    saveSession({
      version: 1,
      spec,
      validationSnapshot,
      resultSnapshot,
      activeLibraryId,
      activeTemplateId,
      recognizedIntent,
      workflowDraft,
    });
  }, [spec, validationSnapshot, resultSnapshot, activeLibraryId, activeTemplateId, recognizedIntent, workflowDraft]);

  const onTemplateLoaded = useCallback((templateId: string | null) => {
    setActiveTemplateId(templateId);
    setActiveLibraryId(null);
    setValidationSnapshot(null);
    setInterpretation(null);
    setViewingSaved(false);
    setViewingSavedAt(null);
  }, []);

  const loadBackendTemplate = useCallback(
    (templateId: string) => {
      const found = backendTemplates.find((t) => t.id === templateId);
      if (!found?.research_spec) return;
      setSpec(specWithoutInventedSeasons(structuredClone(found.research_spec)));
      onTemplateLoaded(templateId);
      setRecognizedIntent(emptyIntent());
      setResultSnapshot(null);
    },
    [backendTemplates, onTemplateLoaded],
  );

  useEffect(() => {
    if (labAdvanced || viewingSaved) return;
    if (!backendTemplates.length) return;
    if (resolution.status === "READY" && resolution.matchedTemplate) {
      if (activeTemplateId !== resolution.matchedTemplate) {
        loadBackendTemplate(resolution.matchedTemplate);
      }
    } else if (activeTemplateId) {
      setSpec(blankSpec());
      setActiveTemplateId(null);
      setValidationSnapshot(null);
      setResultSnapshot(null);
    }
  }, [
    activeTemplateId,
    backendTemplates.length,
    labAdvanced,
    loadBackendTemplate,
    resolution.matchedTemplate,
    resolution.status,
    viewingSaved,
  ]);

  useEffect(() => {
    if (viewingSaved) return;
    setRecognizedIntent(intentFromResolution(resolution));
  }, [resolution, viewingSaved]);

  const revertToValidated = useCallback(() => {
    if (!validationSnapshot?.spec) return;
    setSpec(structuredClone(validationSnapshot.spec));
  }, [validationSnapshot]);

  const reloadActiveTemplate = useCallback(() => {
    if (!activeTemplateId) return;
    const found = backendTemplates.find((t) => t.id === activeTemplateId);
    if (!found?.research_spec) return;
    setSpec(structuredClone(found.research_spec));
    setValidationSnapshot(null);
    setInterpretation(null);
  }, [activeTemplateId, backendTemplates]);

  const applyCatalogTemplate = useCallback(
    async (template: CatalogTemplate) => {
      const backendId = template.backendTemplateId;
      if (backendId) {
        const found = backendTemplates.find((t) => t.id === backendId);
        if (found?.research_spec) {
          setSpec(structuredClone(found.research_spec));
          onTemplateLoaded(backendId);
          go("start");
          setLabAdvanced(false);
          setRecognizedIntent(emptyIntent());
          setDetail({
            title: template.name,
            subtitle: `${template.usability} · ${template.status}`,
            sections: [
              {
                heading: "Loaded",
                body: (
                  <p>
                    Backend template <span className="evidence">{backendId}</span> applied.
                    {template.usability === "IMPLEMENTED"
                      ? " Validate, then Run."
                      : template.usability === "CONFIGURABLE"
                        ? " Starting point — edit in Define before treating as runnable."
                        : " Registered only — not constructible as an executable route."}
                  </p>
                ),
              },
            ],
          });
          return;
        }
      }
      const next = blankSpec();
      next.identity = {
        name: template.id,
        description: template.description,
        tags: [template.status, template.category, template.sport, template.usability],
      };
      if (template.sport === "NBA" || template.sport === "WNBA" || template.sport === "NCAAB") {
        next.population_binding = {
          ...asObj(next.population_binding),
          leagues: [template.sport],
        };
      }
      setSpec(next);
      onTemplateLoaded(null);
      go("start");
      setLabAdvanced(false);
      setRecognizedIntent(emptyIntent());
      setDetail({
        title: template.name,
        subtitle: template.usability,
        sections: [
          {
            heading: "Starting point",
            body: (
              <p>
                {template.notes ||
                  "No backend sample for this catalog entry. Identity seeded only — not an empirical route."}
              </p>
            ),
          },
        ],
      });
    },
    [backendTemplates, go, onTemplateLoaded],
  );

  const useTemplateById = useCallback(
    (id: string) => {
      const t = TEMPLATE_CATALOG.find((x) => x.id === id);
      if (t) void applyCatalogTemplate(t);
    },
    [applyCatalogTemplate],
  );

  const refreshLibrary = useCallback(() => setLibraryTick((n) => n + 1), []);

  const saveToLibrary = useCallback(
    (nameOverride?: string) => {
      if (resultSnapshot) {
        setSaveError(null);
        setSaveModalOpen(true);
        return;
      }
      const name = nameOverride || identityName;
      const saved = saveCurrentObject({
        name,
        description: String(asObj(spec.identity).description || ""),
        tags: (asObj(spec.identity).tags as string[] | undefined) || [],
        research_spec: structuredClone(spec),
        spec_fingerprint: currentSpecFingerprint,
        last_result: undefined,
        last_result_snapshot: null,
        workflow_draft: applyResolutionToDraft(workflowDraft, resolution),
        kind: "QUESTION",
      });
      setActiveLibraryId(saved.id);
      refreshLibrary();
    },
    [currentSpecFingerprint, identityName, refreshLibrary, resolution, resultSnapshot, spec, workflowDraft],
  );

  const commitSavedSnapshot = useCallback(
    async (input: { name: string; folder: string; description: string }) => {
      if (!resultSnapshot) return;
      setSaveBusy(true);
      setSaveError(null);
      try {
        const server = await saveResultToServer({
          name: input.name,
          folder: input.folder,
          description: input.description,
          question: humanQuestion,
          workflow_draft: applyResolutionToDraft(workflowDraft, resolution),
          research_spec: resultSnapshot.spec,
          hashes: (resultSnapshot.payload as AnswerResult | undefined)?.hashes,
          result: resultSnapshot.payload,
        });
        const snapshot = buildSavedSnapshot({
          name: input.name,
          folder: input.folder,
          description: input.description,
          spec,
          resultSnapshot: compactResultSnapshot(resultSnapshot),
          validationSnapshot,
          question: humanQuestion,
          workflowDraft: applyResolutionToDraft(workflowDraft, resolution),
        });
        const saved = saveImmutableResult({
          name: input.name,
          folder: input.folder,
          description: input.description,
          research_spec: structuredClone(snapshot.research_spec),
          spec_fingerprint: resultSnapshot.specFingerprint,
          last_result: snapshot.result_summary,
          last_result_snapshot: compactResultSnapshot(resultSnapshot),
          saved_snapshot: snapshot,
          workflow_draft: applyResolutionToDraft(workflowDraft, resolution),
          server_save_id: server.id,
        });
        setActiveLibraryId(saved.id);
        setViewingSaved(true);
        setViewingSavedAt(server.saved_at || snapshot.saved_at);
        setSaveModalOpen(false);
        refreshLibrary();
      } catch (err) {
        setSaveError(err instanceof Error ? err.message : String(err));
      } finally {
        setSaveBusy(false);
      }
    },
    [humanQuestion, refreshLibrary, resolution, resultSnapshot, spec, validationSnapshot, workflowDraft],
  );

  const persistRun = useCallback(
    (snapshot: ResultSnapshot) => {
      setViewingSaved(false);
      setViewingSavedAt(null);
      saveSession({
        version: 1,
        spec: structuredClone(snapshot.spec),
        validationSnapshot,
        resultSnapshot: snapshot,
        activeLibraryId,
        activeTemplateId,
        recognizedIntent,
        workflowDraft,
      });
    },
    [activeLibraryId, activeTemplateId, recognizedIntent, validationSnapshot, workflowDraft],
  );

  const openLibraryEntry = useCallback((entry: LibraryEntry) => {
    const snap = entry.saved_snapshot;
    const specToLoad = snap?.research_spec ?? entry.research_spec;
    const draftToLoad = snap?.workflow_draft ?? entry.workflow_draft ?? null;
    const kind = libraryEntryKind(entry);
    const apply = (resultToLoad: ResultSnapshot | null) => {
      setSpec(structuredClone(specToLoad));
      setValidationSnapshot(null);
      setInterpretation(null);
      setWorkflowDraft(draftToLoad ? structuredClone(draftToLoad) : emptyDraft());
      setRecognizedIntent(draftToLoad?.recognizedIntent ?? emptyIntent());
      setActiveTemplateId(null);
      setActiveLibraryId(entry.id);
      setResultSnapshot(
        resultToLoad && kind === "COMPLETE"
          ? {
              ...structuredClone(resultToLoad),
              workflowDraft:
                resultToLoad.workflowDraft ??
                (draftToLoad ? structuredClone(draftToLoad) : undefined),
            }
          : null,
      );
      setViewingSaved(kind === "COMPLETE");
      setViewingSavedAt(snap?.saved_at ?? null);
      touchEntry(entry.id);
      setLibraryTick((n) => n + 1);
      setRoute(kind === "COMPLETE" && resultToLoad ? "results" : "start");
      setLabAdvanced(false);
    };
    if (entry.server_save_id) {
      void loadServerSave(entry.server_save_id)
        .then((rec) => {
          const result = rec.result as AnswerResult | undefined;
          if (result && typeof result === "object") {
            apply({
              payload: result,
              spec: (rec.research_spec as Spec) ?? specToLoad,
              specFingerprint: entry.spec_fingerprint ?? "",
              workflowDraft: (rec.workflow_draft as WorkflowDraft | undefined) ?? draftToLoad ?? undefined,
            });
            return;
          }
          apply(snap?.result_snapshot ?? entry.last_result_snapshot ?? null);
        })
        .catch(() => {
          apply(snap?.result_snapshot ?? entry.last_result_snapshot ?? null);
        });
      return;
    }
    apply(snap?.result_snapshot ?? entry.last_result_snapshot ?? null);
  }, []);

  const newResearch = useCallback(() => {
    setSpec(blankSpec());
    setWorkflowDraft(emptyDraft());
    setRecognizedIntent(emptyIntent());
    setValidationSnapshot(null);
    setResultSnapshot(null);
    setInterpretation(null);
    setActiveLibraryId(null);
    setActiveTemplateId(null);
    setViewingSaved(false);
    setViewingSavedAt(null);
    setLabAdvanced(false);
    setAcceptLimitations(false);
    setRoute("start");
  }, []);

  const downloadReport = useCallback(
    (kind: "md" | "constraints" | "results" | "csv" | "trades" | "print") => {
      const result = (resultSnapshot?.payload as AnswerResult | undefined) ?? null;
      const stem = identityName.replace(/[^\w.-]+/g, "_") || "research";
      if (kind === "print") {
        window.print();
        return;
      }
      if (kind === "md") {
        downloadText(
          `${stem}.md`,
          buildWorkflowMarkdown({
            draft: workflowDraft,
            resolution,
            spec,
            result,
            question: humanQuestion,
          }),
          "text/markdown",
        );
        return;
      }
      if (kind === "constraints") {
        downloadText(
          `${stem}-constraints.json`,
          buildConstraintsJson({ draft: workflowDraft, resolution }),
          "application/json",
        );
        return;
      }
      if (kind === "results" && result) {
        downloadText(`${stem}-results.json`, buildResultsJson(result), "application/json");
        return;
      }
      if (kind === "csv" && result) {
        downloadText(`${stem}-aggregate.csv`, buildAggregateCsv(result), "text/csv");
        return;
      }
      if (kind === "trades" && result) {
        downloadText(`${stem}-trades.csv`, buildTradeLogCsv(result), "text/csv");
      }
    },
    [humanQuestion, identityName, resolution, resultSnapshot, spec, workflowDraft],
  );

  const validateThenReview = useCallback(async () => {
    setViewingSaved(false);
    setWorkflowDraft((d) => stripIncompleteHorizons(d));
    await builderActionsRef.current?.validate();
    setRoute("confirm");
  }, []);

  const runResearch = useCallback(async () => {
    if (!warehouseDesk) {
      setDetail({
        title: "NOT AVAILABLE",
        subtitle: "Production ROLLER executes NBA, MLB, NCAAB, ATP, and WTA warehouse research.",
        sections: [
          {
            heading: "Sport lock",
            body: "Pick exactly one tour for tennis. Mixed ATP+WTA and WNBA are not available. Confirm & Run / FIRST80 is not a fallback.",
          },
        ],
      });
      return;
    }
    if (warehouseBuilt.errors.length || warehouseCompile?.status !== "READY") return;
    setRunBusy(true);
    try {
      const body = await executeWarehouseResearch(warehouseBuilt.question, warehouseOpts);
      const snapshot: ResultSnapshot = {
        payload: body as unknown as ResearchResult,
        spec: structuredClone(spec),
        specFingerprint: currentSpecFingerprint,
        workflowDraft: structuredClone(researchDraft),
        draftFingerprint: stableDraftFingerprint(researchDraft),
        acceptLimitations,
      };
      setResultSnapshot(snapshot);
      persistRun(snapshot);
      setApiAvailability("API_REACHABLE");
      setViewingSaved(false);
      setViewingSavedAt(null);
      setRoute("results");
    } catch (err) {
      const availability = classifyApiFailure(err);
      setApiAvailability(availability);
      setDetail({
        title: availability === "API_UNREACHABLE" ? "API_UNREACHABLE" : "Warehouse research failed",
        subtitle: err instanceof Error ? err.message : String(err),
        sections: [
          {
            heading: "What happened",
            body: "The warehouse ResearchQuestion path did not complete. Confirm & Run was not used as a fallback.",
          },
        ],
      });
    } finally {
      setRunBusy(false);
    }
  }, [
    acceptLimitations,
    currentSpecFingerprint,
    warehouseCompile,
    warehouseDesk,
    warehouseBuilt,
    warehouseOpts,
    spec,
    researchDraft,
    persistRun,
  ]);

  useEffect(() => {
    runResearchRef.current = () => runResearch();
  }, [runResearch]);

  const changeDraft = useCallback((next: WorkflowDraft) => {
    const nextFp = stableDraftFingerprint(stripIncompleteHorizons(next));
    const snapFp = snapshotDraftFingerprint(resultSnapshot);
    const identityChanged = Boolean(resultSnapshot && snapFp && snapFp !== nextFp);
    if (viewingSaved) {
      setViewingSaved(false);
      setViewingSavedAt(null);
      setResultSnapshot(null);
      setActiveLibraryId(null);
    } else if (identityChanged) {
      setResultSnapshot(null);
    }
    setWorkflowDraft(next);
  }, [viewingSaved, resultSnapshot]);

  const saveQuestionOnly = useCallback(() => {
    const saved = saveQuestionDraft({
      name: identityName === "Untitled research object" ? humanQuestion.slice(0, 80) : identityName,
      description: humanQuestion,
      workflow_draft: applyResolutionToDraft(workflowDraft, resolution),
    });
    setActiveLibraryId(saved.id);
    refreshLibrary();
    go("library");
  }, [go, humanQuestion, identityName, refreshLibrary, resolution, workflowDraft]);

  const openDocs = useCallback((id?: string) => {
    setDocsInitial(id);
    setRoute("docs");
  }, []);

  const humanStatus = useMemo(
    () =>
      humanResearchStatus({
        validationFreshness,
        executionFreshness,
        canRun,
        validationSnapshot,
        apiAvailability,
        blockedByOverlay:
          resolution.status === "DATA_REQUIRED" || resolution.status === "OPERATION_REQUIRED",
      }),
    [validationFreshness, executionFreshness, canRun, resolution, validationSnapshot, apiAvailability],
  );

  const setSpecHonest = useCallback((next: Spec | ((s: Spec) => Spec)) => {
    setSpec((prev) => specWithoutInventedSeasons(typeof next === "function" ? next(prev) : next));
  }, []);

  const moveToSuperASI = useCallback(() => {
    setSuperasiPackageId(null);
    setSuperasiImportNote(null);
    const payload = resultSnapshot?.payload;
    const question = warehouseDesk ? warehouseBuilt.question : undefined;
    setSuperasiBusy(true);
    void importMeasurement({
      question,
      workflow_draft: researchDraft,
      client_result: payload,
      accept_limitations: acceptLimitations,
    })
      .then((imported) => {
        setSuperasiPackageId(imported.package_id || null);
        setSuperasiImportNote(imported.message || "Imported into SuperASI");
        goProduct("superasi");
      })
      .catch((err) => {
        setSuperasiImportNote(err instanceof Error ? err.message : String(err));
        goProduct("superasi");
      })
      .finally(() => {
        setSuperasiBusy(false);
      });
  }, [acceptLimitations, goProduct, researchDraft, resultSnapshot, warehouseBuilt.question, warehouseDesk]);

  const builderSlot = (
    <>
      <details className="audit-details">
        <summary>Audit · fingerprints</summary>
        <ResearchAuditStrip
          currentSpec={spec}
          currentSpecFingerprint={currentSpecFingerprint}
          validationSnapshot={validationSnapshot}
          resultSnapshot={resultSnapshot}
          validationFreshness={validationFreshness}
          executionFreshness={executionFreshness}
          onOpenValidatedJson={() => setShowValidatedJson(true)}
        />
      </details>
      {showValidatedJson && validationSnapshot?.spec ? (
        <section className="research-object">
          <div className="row">
            <h2 style={{ margin: 0, flex: 1 }}>Validated spec</h2>
            <button type="button" className="btn-secondary" onClick={() => setShowValidatedJson(false)}>
              Close
            </button>
          </div>
          <pre className="spec-json">{JSON.stringify(validationSnapshot.spec, null, 2)}</pre>
        </section>
      ) : null}
      <ResearchObjectBuilder
        spec={spec}
        setSpec={setSpecHonest}
        validationSnapshot={validationSnapshot}
        setValidationSnapshot={setValidationSnapshot}
        interpretation={interpretation}
        setInterpretation={setInterpretation}
        runBusy={runBusy}
        setRunBusy={setRunBusy}
        currentSpecFingerprint={currentSpecFingerprint}
        validationFreshness={validationFreshness}
        executionFreshness={executionFreshness}
        canRun={canRun}
        capabilities={capabilities}
        capabilityPreview={capabilityPreview}
        capabilitiesLoading={capabilitiesLoading}
        capabilitiesError={capabilitiesError}
        capabilitySummary={capabilitySummaryLine}
        onActionsReady={(actions) => {
          builderActionsRef.current = actions;
        }}
        onTemplateLoaded={onTemplateLoaded}
        onRevertToValidated={revertToValidated}
        onReloadTemplate={reloadActiveTemplate}
        onResearchResult={(result, specFingerprint, submittedSpec) => {
          const snapshot: ResultSnapshot = {
            payload: result as ResearchResult,
            spec: structuredClone(submittedSpec),
            specFingerprint,
            workflowDraft: structuredClone(researchDraft),
            draftFingerprint: currentDraftFingerprint,
            acceptLimitations,
          };
          setResultSnapshot(snapshot);
          if (result.execution_status === "COMPLETE" || result.execution_status === "PARTIAL") {
            persistRun(snapshot);
            setRoute("results");
          }
        }}
      />
    </>
  );

  if (product === "jump") {
    return (
      <JumpApp
        onBackToSuperASI={() => goProduct("superasi")}
        onBackToRoller={() => goProduct("roller")}
      />
    );
  }

  if (product === "superasi") {
    return (
      <SuperASIApp
        initialPackageId={superasiPackageId}
        importNote={superasiImportNote}
        initialLabId={superasiLabId}
        onBackToRoller={() => goProduct("roller")}
        onOpenJump={() => {
          goProduct("jump");
        }}
        onOpenVital={() => openVitalDashboard()}
      />
    );
  }

  return (
    <div className="app-root ws-app">
      <AppHeader
        status={humanStatus}
        onOpenDocs={() => openDocs()}
        onOpenSuperASI={() => goProduct("superasi")}
        onOpenVital={() => openVitalDashboard()}
        onOpenHome={() => {
          setResearchMode("quickstart");
          go("start");
        }}
      />
      <AppShell
        sidebarCollapsed={sidebarCollapsed}
        onToggleSidebar={() => setSidebarCollapsed((c) => !c)}
        sidebar={
          <ResearchSidebar
            collapsed={sidebarCollapsed}
            route={route}
            identityName={identityName}
            status={humanStatus}
            validationFreshness={validationFreshness}
            executionFreshness={executionFreshness}
            validationSnapshot={validationSnapshot}
            canRun={canRun}
            runBusy={runBusy}
            populationN={populationN}
            resultsFresh={Boolean(resultSnapshot) && executionFreshness === "CURRENT"}
            recent={libraryState.entries.filter(
              (e) => !/last.?trade|LAST_TRADE|FIRST80|NCAAB/i.test(`${e.name} ${e.id}`),
            )}
            currentSpecFingerprint={currentSpecFingerprint}
            onValidate={() => void validateThenReview()}
            onRun={() => void runResearch()}
            onSave={() => saveToLibrary()}
            onRevertToValidated={revertToValidated}
            onReloadTemplate={activeTemplateId ? reloadActiveTemplate : undefined}
            onOpenRecent={openLibraryEntry}
            onNavigate={(next) => {
              if (
                next === "explorer" ||
                next === "dictionary" ||
                next === "docs" ||
                next === "templates" ||
                next === "library" ||
                next === "settings"
              ) {
                setResearchMode("quickstart");
              }
              go(next);
            }}
            researchMode={researchMode}
            onResearchMode={(mode) => {
              if (mode === "stax") return;
              setResearchMode("quickstart");
            }}
            staxRoute={staxRoute}
            onStaxNavigate={setStaxRoute}
            staxName={staxName}
            staxStrategyCount={staxStrategyCount}
          />
        }
      >
        <main className="main-pane">
          {researchContext ? (
            <div className="banner">
              Context: {researchContext.sport} {researchContext.season} · {researchContext.internal_game_id} ·
              as_of {researchContext.as_of}
              <button type="button" className="banner-clear" onClick={() => setResearchContext(null)}>
                Clear
              </button>
            </div>
          ) : null}

          {route === "explorer" ? (
            <>
              <section className="ws-hero">
                <p className="ws-kicker">Discover</p>
                <h1 className="ws-title">Explorer</h1>
                <p className="ws-lede">
                  Browse point-in-time games, then carry one into Define as research context.
                </p>
              </section>
              <section className="panel">
                <div className="row">
                  <label>
                    as_of
                    <input value={asOf} onChange={(e) => setAsOf(e.target.value)} />
                  </label>
                  <button type="button" onClick={() => void explore()} disabled={exploreLoading}>
                    {exploreLoading ? "Loading…" : "Load games"}
                  </button>
                </div>
                {exploreError ? <p className="error">{exploreError}</p> : null}
                {explorer ? (
                  <p className="muted">
                    {explorer.count} games · mode {explorer.information_mode}
                  </p>
                ) : null}
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Sport</th>
                        <th>Season</th>
                        <th>Away</th>
                        <th>Home</th>
                        <th>Game</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(explorer?.games ?? []).map((g) => (
                        <tr
                          key={g.internal_game_id}
                          className={selected?.internal_game_id === g.internal_game_id ? "selected" : ""}
                          onClick={() => void openObject(g)}
                        >
                          <td>{g.sport}</td>
                          <td>{g.season}</td>
                          <td>{g.away_team}</td>
                          <td>{g.home_team}</td>
                          <td className="mono">{g.internal_game_id}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
              <section className="panel">
                <h2>Object</h2>
                <div className="row">
                  <label>
                    object as_of
                    <input value={objectAsOf} onChange={(e) => setObjectAsOf(e.target.value)} />
                  </label>
                  {selected ? (
                    <button type="button" onClick={() => void openObject(selected)} disabled={objectLoading}>
                      Reload object
                    </button>
                  ) : null}
                  {objectPayload && selected ? (
                    <button type="button" className="btn-primary" onClick={useAsResearchContext}>
                      Use as research context
                    </button>
                  ) : null}
                </div>
                {objectError ? <p className="error">{objectError}</p> : null}
                {objectPayload ? (
                  <pre className="spec-json">{JSON.stringify(objectPayload.object, null, 2)}</pre>
                ) : (
                  <p className="muted">Select a game to inspect the research object.</p>
                )}
              </section>
              <section className="panel">
                <h2>Natural language (interpret only)</h2>
                <textarea
                  rows={3}
                  value={nlPrompt}
                  onChange={(e) => setNlPrompt(e.target.value)}
                  placeholder="Describe a research question…"
                />
                <div className="row">
                  <button type="button" onClick={() => void interpretExplorer()}>
                    Interpret
                  </button>
                </div>
                {nlMessage ? <p className="muted">{nlMessage}</p> : null}
              </section>
            </>
          ) : null}

          {researchMode === "quickstart" && route === "start" ? (
            <>
              <QuickStartScreen
                draft={workflowDraft}
                onChange={changeDraft}
                onEnter={() => go("entry")}
              />
              <button type="button" className="v2-text-link ws-advanced-link" onClick={() => setLabAdvanced((v) => !v)}>
                {labAdvanced ? "Hide Advanced (A–I)" : "Advanced (A–I builder)"}
              </button>
            </>
          ) : null}

          {researchMode === "quickstart" && route === "entry" ? (
            <EntryConditionsScreen
              key={[...workflowDraft.universe.sports, ...workflowDraft.universe.leagues].join("|")}
              draft={workflowDraft}
              onChange={changeDraft}
              onBack={() => go("start")}
              onEnter={() => go("exit")}
            />
          ) : null}

          {researchMode === "quickstart" && route === "exit" ? (
            <ExitConditionsScreen
              draft={researchDraft}
              onChange={changeDraft}
              onBack={() => go("entry")}
              onEnter={() => {
                changeDraft(stripIncompleteHorizons(workflowDraft));
                go("confirm");
              }}
            />
          ) : null}

          {researchMode === "quickstart" && route === "confirm" ? (
            <ConfirmScreen
              draft={researchDraft}
              resolution={resolution}
              spec={spec}
              validationSnapshot={validationSnapshot}
              capabilityPreview={capabilityPreview}
              runBusy={runBusy}
              templateReady
              acceptLimitations={acceptLimitations}
              onAcceptLimitations={setAcceptLimitations}
              compile={null}
              compileBusy={false}
              warehouseQuestion={warehouseDesk ? warehouseBuilt.question : null}
              warehouseErrors={warehouseBuilt.errors}
              warehouseCompile={warehouseCompile}
              warehouseBusy={warehouseBusy}
              apiAvailability={apiAvailability}
              onRun={() => void runResearch()}
              onEdit={(step) => go(step)}
              onSaveQuestion={saveQuestionOnly}
            />
          ) : null}

          {researchMode === "quickstart" && route === "start" && labAdvanced ? (
            <LabWorkspace
              spec={spec}
              setSpec={(next) => {
                if (typeof next === "function") {
                  setSpec((prev) => specWithoutInventedSeasons(next(prev)));
                } else {
                  setSpec(specWithoutInventedSeasons(next));
                }
              }}
              backendTemplates={backendTemplates}
              catalog={TEMPLATE_CATALOG}
              validationFreshness={validationFreshness}
              executionFreshness={executionFreshness}
              validationSnapshot={validationSnapshot}
              canRun={canRun}
              runBusy={runBusy}
              onValidate={() => void validateThenReview()}
              onRun={() => void runResearch()}
              onValidateAndRun={() => {
                void (async () => {
                  await builderActionsRef.current?.validate();
                  await runResearch();
                })();
              }}
              onSaveNamed={(name) => saveToLibrary(name)}
              onOpenAdvanced={() => setLabAdvanced((v) => !v)}
              showAdvanced={labAdvanced}
              onTemplateLoaded={onTemplateLoaded}
              onRevertToValidated={revertToValidated}
              onReloadTemplate={reloadActiveTemplate}
            />
          ) : null}

          {researchMode === "quickstart" ? (
          <div
            ref={builderHostRef}
            className={route === "start" && labAdvanced ? "ws-advanced" : "ws-builder-host"}
            aria-hidden={!(route === "start" && labAdvanced)}
          >
            {builderSlot}
          </div>
          ) : null}

          {researchMode === "quickstart" && route === "results" && isWarehouseResult(resultSnapshot?.payload) ? (
            <WarehouseResults
              payload={resultSnapshot?.payload as import("./api/warehouseResearch").WarehouseCompile}
              onReturn={() => go("confirm")}
              onMoveToSuperASI={(handoff) => {
                setSuperasiLabId(handoff.labId);
                setSuperasiPackageId(null);
                setSuperasiImportNote(
                  `${handoff.name} saved under ${handoff.folder}. SuperASI will run A then B. ITI stays a separate step.`,
                );
                goProduct("superasi");
              }}
            />
          ) : null}

          {researchMode === "quickstart" && route === "results" && !isWarehouseResult(resultSnapshot?.payload) ? (
            <div className="ws-results-workspace">
              <ResultsAnswer
                result={(resultSnapshot?.payload as AnswerResult | undefined) ?? null}
                spec={spec}
                isStale={executionFreshness === "STALE"}
                viewingSaved={viewingSaved}
                savedAt={viewingSavedAt}
                onOpenDetail={setDetail}
                onOpenEvidence={() =>
                  setDetail({
                    title: "Evidence & provenance",
                    subtitle: "Secondary to the empirical answer",
                    sections: [
                      {
                        heading: "Provenance",
                        body: (
                          <pre className="spec-json">
                            {JSON.stringify(
                              (resultSnapshot?.payload as ResearchResult | undefined)?.provenance ?? {},
                              null,
                              2,
                            )}
                          </pre>
                        ),
                      },
                      {
                        heading: "Caveats",
                        body: (
                          <ul>
                            {(
                              (resultSnapshot?.payload as ResearchResult | undefined)?.caveats ?? []
                            ).map((c) => (
                              <li key={c}>{c}</li>
                            ))}
                          </ul>
                        ),
                      },
                    ],
                  })
                }
                onReturnToDefine={() => go("start")}
                onMeasureCurrent={() => {
                  if (canRun) void runResearch();
                  else go("confirm");
                }}
                onSaveResults={() => setSaveModalOpen(true)}
                onDownload={() => downloadReport("md")}
                onPrint={() => downloadReport("print")}
                onNewResearch={newResearch}
                onMoveToSuperASI={() => void moveToSuperASI()}
                moveToSuperASIBusy={superasiBusy}
              />
              {executionFreshness === "CURRENT" || viewingSaved ? (
              <div className="ws-download-bar">
                <button type="button" className="v2-text-link" onClick={() => downloadReport("md")}>
                  Markdown
                </button>
                <button type="button" className="v2-text-link" onClick={() => downloadReport("print")}>
                  PDF / print
                </button>
                <button type="button" className="v2-text-link" onClick={() => downloadReport("csv")}>
                  CSV aggregate
                </button>
                <button type="button" className="v2-text-link" onClick={() => downloadReport("trades")}>
                  Trade log CSV
                </button>
                <button type="button" className="v2-text-link" onClick={() => downloadReport("constraints")}>
                  JSON constraints
                </button>
                <button type="button" className="v2-text-link" onClick={() => downloadReport("results")}>
                  JSON results
                </button>
              </div>
              ) : null}
              {resultSnapshot?.payload && (executionFreshness === "CURRENT" || viewingSaved) ? (
                <ResultsMathStack
                  result={resultSnapshot.payload as AnswerResult}
                  draft={resultSnapshot.workflowDraft ?? workflowDraft}
                  onOpenDetail={setDetail}
                />
              ) : null}
              {viewingSaved ? (
                <p className="ws-immutable-note">
                  This result is immutable. Changing the question creates new research.{" "}
                  <button type="button" className="v2-text-link" onClick={newResearch}>
                    Duplicate as new research
                  </button>
                </p>
              ) : null}
              {executionFreshness === "CURRENT" || viewingSaved ? (
              <details className="audit-details ws-secondary-block">
                <summary>Full results dossier (optional)</summary>
                <ResultsView
                  resultSnapshot={resultSnapshot}
                  currentSpec={spec}
                  currentSpecFingerprint={currentSpecFingerprint}
                  executionFreshness={executionFreshness}
                  validationFreshness={validationFreshness}
                  capabilities={capabilities}
                  capabilityPreview={capabilityPreview}
                  onReturnToResearchObject={() => go("start")}
                />
              </details>
              ) : null}
            </div>
          ) : null}

          {route === "templates" ? (
            <TemplatesView
              backendTemplateIds={backendTemplates.map((t) => t.id)}
              onUse={applyCatalogTemplate}
              onInspect={(t) =>
                setDetail({
                  title: t.name,
                  subtitle: `${t.usability} · ${t.status}`,
                  sections: [
                    { heading: "Description", body: <p>{t.description}</p> },
                    {
                      heading: "Usability",
                      body: (
                        <p>
                          {t.usability === "IMPLEMENTED" &&
                            "Runnable when Validate → CURRENT + RUNNABLE."}
                          {t.usability === "CONFIGURABLE" &&
                            "Starting point — may load a backend draft; not a finished empirical claim."}
                          {t.usability === "REGISTERED" &&
                            "Catalog only — not constructible as an executable route."}
                        </p>
                      ),
                    },
                    { heading: "Notes", body: <p>{t.notes || "—"}</p> },
                  ],
                })
              }
            />
          ) : null}

          {researchMode === "quickstart" && route === "library" ? (
            <ResultsLabsView />
          ) : null}

          {route === "dictionary" ? <DictionaryView onOpenTemplate={useTemplateById} /> : null}

          {route === "docs" ? <DocsView initialId={docsInitial} /> : null}

          {route === "settings" ? <SettingsView /> : null}

          {route === "auto_roller" ? <AutoRollerView /> : null}

          {route === "phenomena" ? <PhenomenaView onOpenTemplate={useTemplateById} /> : null}
        </main>
      </AppShell>
      <DetailDrawer detail={detail} onClose={() => setDetail(null)} />
      {saveModalOpen ? (
        <SaveResultsModal
          defaultName={identityName}
          defaultFolder={inferFolder(spec)}
          defaultDescription={String(asObj(spec.identity).description || humanQuestion)}
          busy={saveBusy}
          error={saveError}
          onCancel={() => {
            if (!saveBusy) {
              setSaveModalOpen(false);
              setSaveError(null);
            }
          }}
          onSave={(input) => void commitSavedSnapshot(input)}
        />
      ) : null}
    </div>
  );
}
