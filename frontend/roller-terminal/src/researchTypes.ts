/** Shared research session types. App owns the editable research_spec. */

export type Spec = Record<string, unknown>;

export type ValidateResult = {
  valid: boolean;
  runnable: boolean;
  status: "RUNNABLE" | "UNRESOLVED" | "INVALID" | string;
  research_object_id: string | null;
  errors: string[];
  unresolved: { field: string; reason: string }[];
};

export type InterpretMatch = {
  phrase: string;
  normalized_phrase: string;
  concept_id: string;
  source: string;
  confidence: "EXACT" | "ALIAS" | "PATTERN" | "AMBIGUOUS" | "UNKNOWN" | string;
};

export type InterpretResult = {
  status: "RESOLVED" | "PARTIAL" | "UNRESOLVED" | "NO_MATCH" | string;
  input: string;
  matches: InterpretMatch[];
  proposed_patch: Spec;
  proposed_spec: Spec;
  unresolved: { field: string; reason: string; source_text?: string }[];
  unknown_terms: string[];
  warnings: string[];
  template_hint?: string | null;
  applied_bindings?: { concept: string; fields: string[] }[];
  compiler_version?: string;
};

/** Transient Explorer orientation — never part of research_spec. */
export type ResearchContext = {
  internal_game_id: string;
  observation_id?: string | null;
  as_of: string;
  sport?: string | null;
  season?: string | null;
};

export function blankSpec(): Spec {
  return {
    schema_version: "research_spec_v0",
    identity: { name: "", description: "", tags: [] },
    universe: "BBALL1",
    population_binding: {
      leagues: ["NBA"],
      default_structural_slices: [],
      selection: "all_matching",
      p5_vs_p5_only: false,
      locked_population_id: null,
    },
    anchor: { event: "OBSERVATION_TIME", unresolved_parameters: [] },
    information_regime: "POINT_IN_TIME",
    information_set: "O_t",
    state_filters: { op: "AND", args: [] },
    path_conditions: [],
    terminal_conditions: [{ kind: "UNRESTRICTED" }],
    measurement_requests: [],
    sample_binding: {},
    definition_versions: {},
    dataset_versions: {},
    execution_interpretation: "OBSERVABLE_PATH_ONLY",
    caveats: ["MEASUREMENT ≠ EDGE", "CANDLE PATH ≠ FILL"],
    economic_layer: null,
    portfolio_layer: null,
    persistence: { kind: "ephemeral" },
  };
}

export function asObj(v: unknown): Record<string, unknown> {
  return v && typeof v === "object" && !Array.isArray(v) ? (v as Record<string, unknown>) : {};
}

export function asArr(v: unknown): unknown[] {
  return Array.isArray(v) ? v : [];
}
