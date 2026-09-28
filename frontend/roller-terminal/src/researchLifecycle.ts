import { asArr, asObj, type InterpretResult, type Spec, type ValidateResult } from "./researchTypes";
import type { Freshness, ResultSnapshot, ValidationSnapshot } from "./researchFreshness";
import {
  effectiveExecutionStatus,
  effectiveSpecStatus,
} from "./researchFreshness";

export type SpecStatus =
  | "UNVALIDATED"
  | "PROPOSED"
  | "VALID"
  | "RUNNABLE"
  | "UNRESOLVED"
  | "INVALID"
  | "STALE";

export type ExecutionStatus =
  | "ABSENT"
  | "COMPLETE"
  | "PARTIAL"
  | "INVALID"
  | "UNRESOLVED"
  | "STALE"
  | "EXECUTING"
  | string;

export function deriveObjectId(
  validationFreshness: Freshness,
  validationSnapshot: ValidationSnapshot | null,
  executionFreshness: Freshness,
  resultSnapshot: ResultSnapshot | null,
): string {
  if (validationFreshness === "CURRENT" && validationSnapshot?.payload.research_object_id) {
    return validationSnapshot.payload.research_object_id;
  }
  if (executionFreshness === "CURRENT" && resultSnapshot?.payload.research_object_id) {
    return resultSnapshot.payload.research_object_id;
  }
  // Prior IDs may still be shown as prior — header uses UNVALIDATED for current object
  if (validationFreshness === "STALE" || executionFreshness === "STALE") {
    return "UNVALIDATED";
  }
  return "UNVALIDATED";
}

export function deriveSpecStatus(
  validationFreshness: Freshness,
  validationSnapshot: ValidationSnapshot | null,
  interpretation: InterpretResult | null,
): SpecStatus {
  return effectiveSpecStatus({
    validationFreshness,
    validationSnapshot,
    hasProposedInterpretation: Boolean(interpretation?.proposed_spec),
  }) as SpecStatus;
}

export function deriveExecutionStatus(
  executionFreshness: Freshness,
  resultSnapshot: ResultSnapshot | null,
  runBusy: boolean,
): ExecutionStatus {
  return effectiveExecutionStatus({
    executionFreshness,
    resultSnapshot,
    runBusy,
  });
}

/** Spec summary chips — never invent FIRST80 from anchor alone. */
export function deriveSpecSummary(spec: Spec): string[] {
  const chips: string[] = [];
  const universe = spec.universe;
  if (typeof universe === "string" && universe) chips.push(universe);

  const pop = asObj(spec.population_binding);
  const leagues = asArr(pop.leagues).filter((x) => typeof x === "string") as string[];
  if (leagues.length) chips.push(leagues.join(","));

  const slices = asArr(pop.default_structural_slices).filter(
    (x) => typeof x === "string",
  ) as string[];
  if (slices.length) chips.push(slices.join(","));

  const defs = asObj(spec.definition_versions);
  for (const key of Object.keys(defs)) {
    chips.push(key);
  }

  const anchor = asObj(spec.anchor);
  if (typeof anchor.event === "string" && anchor.event) {
    let a = anchor.event;
    if (anchor.price_e4 != null && anchor.price_e4 !== "") {
      a += ` @ ${String(anchor.price_e4)} E4`;
    }
    chips.push(a);
  }

  return chips;
}

export type LifecycleStage = {
  id: "EXPLORE" | "DEFINE" | "INTERPRET" | "VALIDATE" | "EXECUTE";
  label: string;
  state: string;
  active: boolean;
};

export function deriveLifecycleStages(args: {
  workspace: string;
  hasExplorerRows: boolean;
  hasResearchContext: boolean;
  interpretation: InterpretResult | null;
  validationFreshness: Freshness;
  validationSnapshot: ValidationSnapshot | null;
  executionFreshness: Freshness;
  resultSnapshot: ResultSnapshot | null;
  runBusy: boolean;
  specModifiedSinceValidation: boolean;
}): LifecycleStage[] {
  const specStatus = deriveSpecStatus(
    args.validationFreshness,
    args.validationSnapshot,
    args.interpretation,
  );
  const exec = deriveExecutionStatus(
    args.executionFreshness,
    args.resultSnapshot,
    args.runBusy,
  );

  let defineState = "READY";
  if (args.workspace === "research_object") defineState = "ACTIVE";
  if (args.specModifiedSinceValidation || args.validationFreshness === "STALE") {
    defineState = "MODIFIED";
  }

  return [
    {
      id: "EXPLORE",
      label: "EXPLORE",
      state: args.hasResearchContext
        ? "CONTEXT"
        : args.hasExplorerRows
          ? "QUERIED"
          : "IDLE",
      active: args.workspace === "explorer",
    },
    {
      id: "DEFINE",
      label: "DEFINE",
      state: defineState,
      active: args.workspace === "research_object",
    },
    {
      id: "INTERPRET",
      label: "INTERPRET",
      state: args.interpretation ? String(args.interpretation.status) : "IDLE",
      active: Boolean(args.interpretation),
    },
    {
      id: "VALIDATE",
      label: "VALIDATE",
      state:
        args.validationFreshness === "STALE"
          ? "STALE"
          : args.validationFreshness === "CURRENT"
            ? `${specStatus}`
            : "UNVALIDATED",
      active: Boolean(args.validationSnapshot),
    },
    {
      id: "EXECUTE",
      label: "EXECUTE",
      state: String(exec),
      active: args.runBusy || Boolean(args.resultSnapshot),
    },
  ];
}

export function sectionSummaries(
  spec: Spec,
  validationFreshness: Freshness,
  validation: ValidateResult | null,
) {
  const identity = asObj(spec.identity);
  const pop = asObj(spec.population_binding);
  const leagues = asArr(pop.leagues).filter((x) => typeof x === "string") as string[];
  const slices = asArr(pop.default_structural_slices).filter(
    (x) => typeof x === "string",
  ) as string[];
  const anchor = asObj(spec.anchor);
  const measurements = asArr(spec.measurement_requests);
  const defs = asObj(spec.definition_versions);
  const path = asArr(spec.path_conditions);
  const terminal = asArr(spec.terminal_conditions);
  const state = asObj(spec.state_filters);

  const name = String(identity.name || "").trim();
  const anchorLabel =
    typeof anchor.event === "string" && anchor.event
      ? anchor.price_e4 != null && anchor.price_e4 !== ""
        ? `${anchor.event} @ ${String(anchor.price_e4)}`
        : String(anchor.event)
      : "—";

  const terminalKinds = terminal
    .map((t) => {
      const o = t && typeof t === "object" ? (t as Record<string, unknown>) : {};
      return typeof o.kind === "string" ? o.kind : null;
    })
    .filter((x): x is string => Boolean(x));

  const defKeys = Object.keys(defs);
  let bindingsSummary: string;
  if (validationFreshness === "STALE") {
    bindingsSummary = defKeys.length
      ? `${defKeys.join(" · ")} · STALE`
      : "STALE";
  } else if (defKeys.length) {
    bindingsSummary = defKeys
      .map((k) => {
        const v = defs[k];
        return typeof v === "string" && v ? `${k} · ${v}` : k;
      })
      .join(" · ");
  } else if (validationFreshness === "CURRENT" && validation?.status) {
    bindingsSummary = validation.status;
  } else {
    bindingsSummary = "NO EXPLICIT BINDINGS";
  }

  const identityBits = [
    name || "unnamed",
    path.length ? "Path" : null,
    terminalKinds.length ? "Terminal" : null,
  ].filter(Boolean);

  return {
    A: identityBits.join(" · "),
    B: [leagues.join(", ") || null, slices.join(", ") || null]
      .filter(Boolean)
      .join(" · ") || String(spec.universe ?? "—"),
    C: anchorLabel,
    D: `${String(spec.information_regime ?? "—")} · ${String(spec.information_set ?? "—")}`,
    E: `${asArr(state.args).length} CONDITION${asArr(state.args).length === 1 ? "" : "S"}`,
    F: `${path.length} CONDITION${path.length === 1 ? "" : "S"}`,
    G: terminalKinds.length ? terminalKinds.join(", ") : "—",
    H: `${measurements.length} REQUEST${measurements.length === 1 ? "" : "S"}`,
    I: bindingsSummary,
  };
}

/** Workspace nav suffixes — derived only from existing freshness/status. */
export function researchObjectNavLabel(
  validationFreshness: Freshness,
  validationStatus: string | null | undefined,
): string {
  if (validationFreshness === "STALE") return "RESEARCH OBJECT · STALE";
  if (validationFreshness === "CURRENT" && validationStatus) {
    return `RESEARCH OBJECT · ${validationStatus}`;
  }
  return "RESEARCH OBJECT · UNVALIDATED";
}

export function resultsNavLabel(executionFreshness: Freshness): string {
  if (executionFreshness === "CURRENT") return "RESULTS · CURRENT";
  if (executionFreshness === "STALE") return "RESULTS · PRIOR";
  return "RESULTS · NONE";
}

/** Heuristic: which builder sections mention validation errors (UI only). */
export function sectionsForValidationIssues(
  errors: string[],
  unresolved: { field: string; reason: string }[],
): string[] {
  const open = new Set<string>();
  const hay = [...errors, ...unresolved.map((u) => `${u.field} ${u.reason}`)]
    .join(" ")
    .toLowerCase();
  if (!hay) return [];
  if (/identity|name|description|tag/.test(hay)) open.add("A");
  if (/population|league|slice|universe/.test(hay)) open.add("B");
  if (/anchor|price_e4|event/.test(hay)) open.add("C");
  if (/information|regime|o_t/.test(hay)) open.add("D");
  if (/state_filter|state /.test(hay)) open.add("E");
  if (/path_condition|path /.test(hay)) open.add("F");
  if (/terminal/.test(hay)) open.add("G");
  if (/measurement/.test(hay)) open.add("H");
  if (/definition|binding|dataset_version/.test(hay)) open.add("I");
  return [...open];
}
