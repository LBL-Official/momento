/**
 * V2 template catalog — UI discovery layer.
 * Usability contract (honest, never fake executables):
 * - IMPLEMENTED → runnable when backend template present + Validate CURRENT + RUNNABLE
 * - CONFIGURABLE → loadable starting point; not a finished empirical claim
 * - REGISTERED → catalog only; not constructible as an executable route
 */

export type TemplateStatus = "IMPLEMENTED" | "STRUCTURAL" | "DRAFT" | "UNAVAILABLE";

/** Human usability — orthogonal to legacy status strings. */
export type TemplateUsability = "IMPLEMENTED" | "CONFIGURABLE" | "REGISTERED";

export type CatalogTemplate = {
  id: string;
  name: string;
  sport: "NBA" | "NCAAB" | "WNBA" | "MLB" | "MULTI";
  category:
    | "PRICE TOUCH"
    | "PATH"
    | "TERMINAL"
    | "TIME"
    | "GAME STATE"
    | "INFORMATION"
    | "BASIS"
    | "VOLATILITY";
  description: string;
  status: TemplateStatus;
  /** Authoritative usability for V2 gallery actions. */
  usability: TemplateUsability;
  /** True only when an authoritative backend template / binding exists */
  runnable: boolean;
  /** Backend template id when loadable via /research-object-templates */
  backendTemplateId?: string | null;
  measurements: string[];
  definitionVersion?: string | null;
  notes?: string;
};

const STRUCTURAL_NOTE =
  "STRUCTURAL TEMPLATE — requires an authoritative population binding before execution.";

function usabilityFromStatus(status: TemplateStatus, runnable: boolean): TemplateUsability {
  if (status === "IMPLEMENTED" && runnable) return "IMPLEMENTED";
  if (status === "IMPLEMENTED" || status === "STRUCTURAL" || status === "DRAFT") {
    return "CONFIGURABLE";
  }
  return "REGISTERED";
}

function t(
  partial: Omit<CatalogTemplate, "runnable" | "usability"> & {
    runnable?: boolean;
    usability?: TemplateUsability;
  },
): CatalogTemplate {
  const runnable =
    partial.runnable ??
    (partial.status === "IMPLEMENTED" && Boolean(partial.backendTemplateId));
  const usability = partial.usability ?? usabilityFromStatus(partial.status, runnable);
  return { ...partial, runnable, usability };
}

/** ~50 catalog entries. Honest status only. */
export const TEMPLATE_CATALOG: CatalogTemplate[] = [
  t({
    id: "FIRST80_Q3",
    name: "FIRST80 Q3",
    sport: "NBA",
    category: "PRICE TOUCH",
    description: "First qualifying 80¢ touch during Q3 with T40 path and Kalshi terminal.",
    status: "IMPLEMENTED",
    usability: "IMPLEMENTED",
    backendTemplateId: "FIRST80_Q3",
    measurements: ["t40_rate", "kalshi_yes_rate"],
    definitionVersion: "warehouse_frozen_v1",
    runnable: true,
  }),
  t({
    id: "NCAAB_FIRST80_P5",
    name: "NCAAB FIRST80 P5",
    sport: "NCAAB",
    category: "PRICE TOUCH",
    description: "P5∩P5 FIRST80 with half-bucket path survival and Kalshi terminal.",
    status: "IMPLEMENTED",
    usability: "IMPLEMENTED",
    backendTemplateId: "NCAAB_FIRST80_P5",
    measurements: ["t40_rate", "kalshi_yes_rate"],
    definitionVersion: "ncaab_first80_p5_v1",
    runnable: true,
  }),
  t({
    id: "LARGE_DOWN_MOVE_Q4",
    name: "Large Down Move Q4",
    sport: "NBA",
    category: "VOLATILITY",
    description: "Observation-time large down move — unresolved magnitude until filled.",
    status: "STRUCTURAL",
    backendTemplateId: "LARGE_DOWN_MOVE_Q4",
    measurements: [],
    notes: STRUCTURAL_NOTE,
  }),
  t({
    id: "BASIS_EXTREME_AT_OBSERVATION",
    name: "Basis Extreme at Observation",
    sport: "NBA",
    category: "BASIS",
    description: "Market–fundamental basis extreme at O_t. Measurement ≠ edge.",
    status: "STRUCTURAL",
    backendTemplateId: "BASIS_EXTREME_AT_OBSERVATION",
    measurements: ["basis"],
    notes: STRUCTURAL_NOTE,
  }),
  // --- Structural catalog expansion (not runnable unless later bound) ---
  t({
    id: "FIRST80_Q1",
    name: "FIRST80 Q1",
    sport: "NBA",
    category: "PRICE TOUCH",
    description: "First 80¢ touch in Q1 — structural slice variant of FIRST80.",
    status: "STRUCTURAL",
    measurements: ["t40_rate", "kalshi_yes_rate"],
    notes: STRUCTURAL_NOTE,
  }),
  t({
    id: "FIRST80_Q2",
    name: "FIRST80 Q2",
    sport: "NBA",
    category: "PRICE TOUCH",
    description: "First 80¢ touch in Q2.",
    status: "STRUCTURAL",
    measurements: ["t40_rate", "kalshi_yes_rate"],
    notes: STRUCTURAL_NOTE,
  }),
  t({
    id: "FIRST80_Q4",
    name: "FIRST80 Q4",
    sport: "NBA",
    category: "PRICE TOUCH",
    description: "First 80¢ touch in Q4. Q4 ≠ 'late game' automatically.",
    status: "STRUCTURAL",
    measurements: ["t40_rate", "kalshi_yes_rate"],
    notes: STRUCTURAL_NOTE,
  }),
  t({
    id: "FIRST80_ASKED_SIX",
    name: "FIRST80 Asked-Six",
    sport: "NBA",
    category: "TIME",
    description: "FIRST80 across ASKED_SIX structural slices (Q2,Q3,H1_2,H2_1).",
    status: "STRUCTURAL",
    measurements: ["t40_rate", "kalshi_yes_rate"],
    notes: STRUCTURAL_NOTE,
  }),
  t({
    id: "FIRST83_Q3",
    name: "FIRST83 Q3",
    sport: "NBA",
    category: "PRICE TOUCH",
    description: "First touch at 83¢ in Q3. No frozen population lock in V1.",
    status: "UNAVAILABLE",
    measurements: [],
    notes: "No authoritative FIRST83 population binding in Phases 0–6.",
  }),
  t({
    id: "FIRST75_Q3",
    name: "FIRST75 Q3",
    sport: "NBA",
    category: "PRICE TOUCH",
    description: "First touch at 75¢. Explicitly out of V1 warehouse scope.",
    status: "UNAVAILABLE",
    measurements: [],
    notes: "FIRST75 ingest excluded from ROLLER V1.",
  }),
  t({
    id: "T40_ONLY_PATH",
    name: "T40 Path Only",
    sport: "NBA",
    category: "PATH",
    description: "Barrier survival to 40¢ without terminal measurement.",
    status: "STRUCTURAL",
    measurements: ["t40_rate"],
    notes: STRUCTURAL_NOTE,
  }),
  t({
    id: "TERMINAL_YES_ONLY",
    name: "Terminal YES Only",
    sport: "NBA",
    category: "TERMINAL",
    description: "Kalshi settlement YES proportion on a bound population.",
    status: "STRUCTURAL",
    measurements: ["kalshi_yes_rate"],
    notes: STRUCTURAL_NOTE,
  }),
  t({
    id: "TERMINAL_NO_ONLY",
    name: "Terminal NO Only",
    sport: "NBA",
    category: "TERMINAL",
    description: "Kalshi settlement NO proportion.",
    status: "STRUCTURAL",
    measurements: [],
    notes: STRUCTURAL_NOTE,
  }),
  t({
    id: "WNBA_FIRST80_Q3",
    name: "WNBA FIRST80 Q3",
    sport: "WNBA",
    category: "PRICE TOUCH",
    description: "WNBA FIRST80 Q3 — requires sport-specific frozen binding.",
    status: "STRUCTURAL",
    measurements: ["t40_rate", "kalshi_yes_rate"],
    notes: STRUCTURAL_NOTE,
  }),
  t({
    id: "WNBA_FIRST80_H1",
    name: "WNBA FIRST80 H1",
    sport: "WNBA",
    category: "PRICE TOUCH",
    description: "WNBA first-half FIRST80 structural starting point.",
    status: "DRAFT",
    measurements: [],
    notes: "Draft — no Phase 0–6 executable WNBA FIRST80 route yet.",
  }),
  t({
    id: "NCAAB_FIRST80_H1_2",
    name: "NCAAB FIRST80 H1_2",
    sport: "NCAAB",
    category: "TIME",
    description: "P5 FIRST80 filtered to late first half (H1_2).",
    status: "STRUCTURAL",
    measurements: ["t40_rate", "kalshi_yes_rate"],
    notes: STRUCTURAL_NOTE,
  }),
  t({
    id: "NCAAB_FIRST80_H2_1",
    name: "NCAAB FIRST80 H2_1",
    sport: "NCAAB",
    category: "TIME",
    description: "P5 FIRST80 filtered to early second half (H2_1).",
    status: "STRUCTURAL",
    measurements: ["t40_rate", "kalshi_yes_rate"],
    notes: STRUCTURAL_NOTE,
  }),
  t({
    id: "NCAAB_FIRST80_FULL",
    name: "NCAAB FIRST80 Full (non-P5)",
    sport: "NCAAB",
    category: "PRICE TOUCH",
    description: "Full NCAAB FIRST80 without P5 filter — not the locked V1 default.",
    status: "UNAVAILABLE",
    measurements: [],
    notes: "Default research binding is P5∩P5. Full universe not locked.",
  }),
  t({
    id: "OBSERVATION_TIME_BASE",
    name: "Observation Time Base",
    sport: "MULTI",
    category: "INFORMATION",
    description: "Anchor at OBSERVATION_TIME / O_t without path conditions.",
    status: "STRUCTURAL",
    measurements: [],
    notes: STRUCTURAL_NOTE,
  }),
  t({
    id: "POINT_IN_TIME_INSPECT",
    name: "Point-in-Time Inspect",
    sport: "MULTI",
    category: "INFORMATION",
    description: "Use Explorer to assemble O_t — not a population measurement.",
    status: "DRAFT",
    measurements: [],
    notes: "Prefer Explore workspace for O_t inspection.",
  }),
  t({
    id: "CANDLE_1M_REGIME",
    name: "Candle 1m Regime",
    sport: "MULTI",
    category: "INFORMATION",
    description: "Information regime CANDLE_1M. Candle path ≠ fill.",
    status: "STRUCTURAL",
    measurements: [],
    notes: STRUCTURAL_NOTE,
  }),
  t({
    id: "MARGIN_LEAD_Q3",
    name: "Score Margin Lead Q3",
    sport: "NBA",
    category: "GAME STATE",
    description: "State filter on score margin during Q3 — requires explicit threshold.",
    status: "DRAFT",
    measurements: [],
    notes: "Ambiguous margins stay UNRESOLVED — never invent thresholds.",
  }),
  t({
    id: "CLOCK_UNDER_5",
    name: "Clock Under 5 Minutes",
    sport: "NBA",
    category: "TIME",
    description: "period_remaining_s < 300 structural condition.",
    status: "STRUCTURAL",
    measurements: [],
    notes: STRUCTURAL_NOTE,
  }),
  t({
    id: "EVER_CLOSE_GE_90",
    name: "Ever Close ≥ 90¢",
    sport: "NBA",
    category: "PATH",
    description: "Path condition EVER_CLOSE_GE at 90¢.",
    status: "STRUCTURAL",
    measurements: [],
    notes: STRUCTURAL_NOTE,
  }),
  t({
    id: "NEVER_CLOSE_LE_20",
    name: "Never Close ≤ 20¢",
    sport: "NBA",
    category: "PATH",
    description: "Path never tradable close ≤ 20¢.",
    status: "STRUCTURAL",
    measurements: [],
    notes: STRUCTURAL_NOTE,
  }),
  t({
    id: "SURVIVE_THEN_TOUCH",
    name: "Survive Then Touch",
    sport: "NBA",
    category: "PATH",
    description: "SURVIVE_THEN_TOUCH compound path — parameters must be explicit.",
    status: "DRAFT",
    measurements: [],
    notes: "Requires explicit stop and touch parameters.",
  }),
  t({
    id: "FUNDAMENTAL_FT_AT_OT",
    name: "Fundamental F_t at O_t",
    sport: "NBA",
    category: "INFORMATION",
    description: "Request F_t prior-only estimate. F_t ≠ true probability ≠ edge.",
    status: "STRUCTURAL",
    measurements: ["fundamental_f_t"],
    notes: STRUCTURAL_NOTE,
  }),
  t({
    id: "MARKET_DELTA_1M",
    name: "Market Delta 1m",
    sport: "NBA",
    category: "VOLATILITY",
    description: "V4B market delta measurement. Δ ≠ edge.",
    status: "STRUCTURAL",
    measurements: ["market_delta_1m"],
    notes: STRUCTURAL_NOTE,
  }),
  t({
    id: "RESIDUAL_RESPONSE",
    name: "Response Residual",
    sport: "NBA",
    category: "BASIS",
    description: "V3 residual measurement. Residual ≠ edge.",
    status: "STRUCTURAL",
    measurements: ["residual"],
    notes: STRUCTURAL_NOTE,
  }),
  t({
    id: "MLB_FIRST01_STUB",
    name: "MLB FIRST01 (stub)",
    sport: "MLB",
    category: "PRICE TOUCH",
    description: "MLB sticky-bid FIRST01 lives in research-replay — not BBALL1.",
    status: "UNAVAILABLE",
    measurements: [],
    notes: "Different sport/semantics — do not bind to BBALL1.",
  }),
  t({
    id: "NBA_Q2_FIRST80",
    name: "NBA Q2 FIRST80",
    sport: "NBA",
    category: "PRICE TOUCH",
    description: "Alias structural entry for Q2 FIRST80.",
    status: "STRUCTURAL",
    measurements: ["t40_rate", "kalshi_yes_rate"],
    notes: STRUCTURAL_NOTE,
  }),
  t({
    id: "NBA_H2_PRESSURE",
    name: "NBA H2 Pressure Window",
    sport: "NBA",
    category: "GAME STATE",
    description: "Second-half pressure window — draft structural filters only.",
    status: "DRAFT",
    measurements: [],
  }),
  t({
    id: "SPREAD_QUALITY_GATE",
    name: "Spread Quality Gate",
    sport: "NBA",
    category: "INFORMATION",
    description: "Tradable quality / max spread gate (frozen_v1 quality semantics).",
    status: "STRUCTURAL",
    measurements: [],
    notes: STRUCTURAL_NOTE,
  }),
  t({
    id: "HIT80_HIT40_PAIR",
    name: "HIT80 / HIT40 Pair",
    sport: "NBA",
    category: "PATH",
    description: "Paired touch definitions HIT80=8000, HIT40=4000 E4.",
    status: "STRUCTURAL",
    measurements: ["t40_rate"],
    notes: STRUCTURAL_NOTE,
  }),
  t({
    id: "WICK_STOP_SECONDARY",
    name: "Wick Stop Secondary",
    sport: "NBA",
    category: "PATH",
    description: "Secondary wick-based stop — primary remains close ≤ 40.",
    status: "DRAFT",
    measurements: [],
    notes: "Wick is secondary only in FIRST80 contract.",
  }),
  t({
    id: "MULTI_SLICE_COMPARE",
    name: "Multi-Slice Compare",
    sport: "NBA",
    category: "TIME",
    description: "Compare structural slices — needs multi-slice population support.",
    status: "DRAFT",
    measurements: [],
    notes: "Phase 7 portfolio compare is out of scope.",
  }),
  t({
    id: "POPULATION_ALL_FIRST80",
    name: "All FIRST80 Settled",
    sport: "NBA",
    category: "PRICE TOUCH",
    description: "Full settled FIRST80 ledger without Q3 filter (n≈1230 candidates).",
    status: "STRUCTURAL",
    measurements: ["t40_rate", "kalshi_yes_rate"],
    notes: STRUCTURAL_NOTE + " Locked Q3 template remains n=290.",
  }),
  t({
    id: "YES_BID_CLOSE_FIELD",
    name: "yes_bid_close Field Discipline",
    sport: "MULTI",
    category: "INFORMATION",
    description: "Anchor price_field = yes_bid_close (E4 integer).",
    status: "STRUCTURAL",
    measurements: [],
    notes: STRUCTURAL_NOTE,
  }),
  t({
    id: "REQUIRES_SEEN_BELOW",
    name: "Requires Seen Below",
    sport: "NBA",
    category: "PRICE TOUCH",
    description: "FIRST_PRICE_TOUCH with requires_seen_below=true.",
    status: "STRUCTURAL",
    measurements: [],
    notes: STRUCTURAL_NOTE,
  }),
  t({
    id: "UNRESTRICTED_TERMINAL",
    name: "Unrestricted Terminal",
    sport: "MULTI",
    category: "TERMINAL",
    description: "terminal_conditions UNRESTRICTED — no settlement filter.",
    status: "STRUCTURAL",
    measurements: [],
    notes: STRUCTURAL_NOTE,
  }),
  t({
    id: "P5_VS_P5_ONLY",
    name: "P5 vs P5 Only",
    sport: "NCAAB",
    category: "GAME STATE",
    description: "population_binding.p5_vs_p5_only = true.",
    status: "STRUCTURAL",
    measurements: [],
    notes: STRUCTURAL_NOTE,
  }),
  t({
    id: "BBALL1_UNIVERSE",
    name: "BBALL1 Universe Shell",
    sport: "MULTI",
    category: "INFORMATION",
    description: "Empty BBALL1 research_spec shell for manual construction.",
    status: "DRAFT",
    measurements: [],
  }),
  t({
    id: "EXPORT_ONLY_SPEC",
    name: "Export-Oriented Spec",
    sport: "MULTI",
    category: "INFORMATION",
    description: "Minimal identity + bindings for JSON export workflows.",
    status: "DRAFT",
    measurements: [],
  }),
  t({
    id: "PROVENANCE_AUDIT",
    name: "Provenance Audit Focus",
    sport: "NBA",
    category: "INFORMATION",
    description: "Starting point emphasizing definition_versions and artifacts.",
    status: "DRAFT",
    measurements: [],
  }),
  t({
    id: "CAVEAT_DISCIPLINE",
    name: "Caveat Discipline Shell",
    sport: "MULTI",
    category: "INFORMATION",
    description: "Shell preloaded with MEASUREMENT≠EDGE / PATH≠FILL caveats.",
    status: "DRAFT",
    measurements: [],
  }),
  t({
    id: "NBA_OVERTIME_TOUCH",
    name: "NBA Overtime Touch",
    sport: "NBA",
    category: "TIME",
    description: "OT structural slice — often empty / unsupported.",
    status: "UNAVAILABLE",
    measurements: [],
    notes: "OT population not locked in Phases 0–6.",
  }),
  t({
    id: "WNBA_TERMINAL_YES",
    name: "WNBA Terminal YES",
    sport: "WNBA",
    category: "TERMINAL",
    description: "WNBA Kalshi YES rate on bound population.",
    status: "STRUCTURAL",
    measurements: ["kalshi_yes_rate"],
    notes: STRUCTURAL_NOTE,
  }),
  t({
    id: "NCAAB_TERMINAL_YES",
    name: "NCAAB Terminal YES",
    sport: "NCAAB",
    category: "TERMINAL",
    description: "NCAAB Kalshi YES on P5 FIRST80 population.",
    status: "STRUCTURAL",
    measurements: ["kalshi_yes_rate"],
    notes: STRUCTURAL_NOTE,
  }),
  t({
    id: "PATH_VOL_PLACEHOLDER",
    name: "Path Volatility Placeholder",
    sport: "NBA",
    category: "VOLATILITY",
    description: "Path volatility analytics require bound price-path series.",
    status: "UNAVAILABLE",
    measurements: [],
    notes: "NOT AVAILABLE until authoritative path series is bound.",
  }),
  t({
    id: "SCENARIO_EV_SHELL",
    name: "Scenario EV Shell",
    sport: "MULTI",
    category: "INFORMATION",
    description: "Opens Results scenario calculator — not empirical EV.",
    status: "DRAFT",
    measurements: [],
    notes: "USER-SUPPLIED HYPOTHETICAL ECONOMICS only.",
  }),
];

export function catalogStats(catalog: CatalogTemplate[] = TEMPLATE_CATALOG) {
  const implemented = catalog.filter((c) => c.usability === "IMPLEMENTED").length;
  const configurable = catalog.filter((c) => c.usability === "CONFIGURABLE").length;
  const registered = catalog.filter((c) => c.usability === "REGISTERED").length;
  const structural = catalog.filter((c) => c.status === "STRUCTURAL").length;
  const draft = catalog.filter((c) => c.status === "DRAFT").length;
  const unavailable = catalog.filter((c) => c.status === "UNAVAILABLE").length;
  const runnable = catalog.filter((c) => c.runnable).length;
  return {
    total: catalog.length,
    implemented,
    configurable,
    registered,
    structural,
    draft,
    unavailable,
    runnable,
  };
}

/** Merge backend template availability into catalog runnable / usability flags. */
export function mergeBackendTemplates(
  catalog: CatalogTemplate[],
  backendIds: Set<string>,
): CatalogTemplate[] {
  return catalog.map((c) => {
    if (!c.backendTemplateId) {
      return {
        ...c,
        runnable: false,
        usability: c.status === "UNAVAILABLE" ? "REGISTERED" : c.usability === "IMPLEMENTED" ? "CONFIGURABLE" : c.usability,
      };
    }
    const present = backendIds.has(c.backendTemplateId);
    if (c.status === "IMPLEMENTED" && present) {
      return { ...c, runnable: true, usability: "IMPLEMENTED" };
    }
    if (c.status === "IMPLEMENTED" && !present) {
      return {
        ...c,
        runnable: false,
        usability: "CONFIGURABLE",
        notes: (c.notes ?? "") + (c.notes ? " " : "") + "Backend template not currently loaded.",
      };
    }
    return {
      ...c,
      runnable: false,
      usability: c.status === "UNAVAILABLE" ? "REGISTERED" : "CONFIGURABLE",
      notes: present
        ? (c.notes ?? STRUCTURAL_NOTE) + " Backend sample loadable."
        : c.notes,
    };
  });
}
