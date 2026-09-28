/** Phase 5.8 — advisory capability preview. Pure helpers only.

CAPABILITY ≠ CONSTRUCTIBILITY ≠ EXECUTION
Registry:  Does the system know this measurement?
Preview:   Given explicit research_spec bindings, is a route registered?
Executor:  Did the authoritative route actually produce the measurement?
*/

import { asArr, asObj, type Spec } from "./researchTypes";

export type CapabilityStatus =
  | "IMPLEMENTED"
  | "REGISTERED"
  | "NOT_CONSTRUCTIBLE"
  | "UNSUPPORTED"
  | "ABSENT"
  | "ABSENT_IF_UNAVAILABLE"
  | "UNKNOWN";

export type ResearchCapabilitiesPayload = {
  phase?: number;
  population_bindings?: PopulationBindingCap[];
  measurements?: MeasurementCap[];
  notes?: string[];
};

export type PopulationBindingCap = {
  name: string;
  definition_version: string;
  status: string;
  note?: string;
  artifacts?: string[];
};

export type MeasurementCap = {
  name: string;
  kind?: string;
  definition_version?: string | null;
  status: string;
  population_requirements?: {
    definition_family?: string;
    definition_families?: string[];
  };
  requires?: Record<string, unknown>;
  caveat?: string | null;
};

export type MeasurementCapabilityPreview = {
  name: string;
  status: CapabilityStatus;
  kind?: string | null;
  definitionVersion?: string | null;
  reason?: string | null;
  populationRequirement?: string | null;
  registryStatus?: string | null;
};

export type PopulationCapabilityPreview = {
  family: string | null;
  requestedDefinitionVersion: string | null;
  status: CapabilityStatus;
  reason?: string | null;
};

export type ResearchCapabilityPreview = {
  population: PopulationCapabilityPreview;
  measurements: MeasurementCapabilityPreview[];
  summary: {
    implemented: number;
    registered: number;
    notConstructible: number;
    unsupported: number;
    absent: number;
  };
};

function mapRegistryMeasurementStatus(apiStatus: string): CapabilityStatus {
  if (apiStatus === "IMPLEMENTED") return "IMPLEMENTED";
  if (apiStatus === "REGISTERED_NOT_EXECUTABLE" || apiStatus === "REGISTERED") {
    return "REGISTERED";
  }
  return "UNKNOWN";
}

function mapPopulationStatus(apiStatus: string): CapabilityStatus {
  if (apiStatus === "IMPLEMENTED") return "IMPLEMENTED";
  if (apiStatus === "ABSENT_IF_UNAVAILABLE") return "ABSENT_IF_UNAVAILABLE";
  if (apiStatus === "ABSENT") return "ABSENT";
  return "UNKNOWN";
}

function analyzePopulation(
  spec: Spec,
  bindings: PopulationBindingCap[],
): PopulationCapabilityPreview {
  const defs = asObj(spec.definition_versions);
  const keys = Object.keys(defs);
  if (keys.length === 0) {
    return {
      family: null,
      requestedDefinitionVersion: null,
      status: "ABSENT",
      reason: "NO EXPLICIT REGISTERED POPULATION BINDING",
    };
  }

  // Explicit keys only — never infer from anchor. Prefer NCAAB_FIRST80_P5 then FIRST80.
  const family = keys.includes("NCAAB_FIRST80_P5")
    ? "NCAAB_FIRST80_P5"
    : keys.includes("FIRST80")
      ? "FIRST80"
      : keys[0];
  const requested =
    defs[family] == null || defs[family] === ""
      ? null
      : String(defs[family]);

  if (!requested) {
    return {
      family,
      requestedDefinitionVersion: null,
      status: "ABSENT",
      reason: `definition_versions.${family} present but empty`,
    };
  }

  const match = bindings.find(
    (b) => b.name === family && b.definition_version === requested,
  );
  if (!match) {
    return {
      family,
      requestedDefinitionVersion: requested,
      status: "UNSUPPORTED",
      reason: `No registered population binding for ${family} @ ${requested}`,
    };
  }

  return {
    family,
    requestedDefinitionVersion: requested,
    status: mapPopulationStatus(match.status),
    reason: match.note || null,
  };
}

function allowedMeasurementFamilies(
  req: MeasurementCap["population_requirements"] | undefined,
): string[] {
  if (!req) return [];
  if (Array.isArray(req.definition_families) && req.definition_families.length) {
    return req.definition_families.map(String);
  }
  if (req.definition_family) return [String(req.definition_family)];
  return [];
}

function analyzeMeasurement(
  name: string,
  registry: MeasurementCap[],
  population: PopulationCapabilityPreview,
): MeasurementCapabilityPreview {
  const entry = registry.find((m) => m.name === name);
  if (!entry) {
    return {
      name,
      status: "UNSUPPORTED",
      reason: "No registered measurement definition.",
      registryStatus: null,
    };
  }

  const mapped = mapRegistryMeasurementStatus(entry.status);
  const allowed = allowedMeasurementFamilies(entry.population_requirements);
  const requirementLabel = allowed.length ? allowed.join("|") : null;

  if (mapped === "REGISTERED") {
    return {
      name,
      status: "REGISTERED",
      kind: entry.kind ?? null,
      definitionVersion: entry.definition_version ?? null,
      reason: "NOT CONSTRUCTIBLE IN CURRENT PHASE",
      populationRequirement: requirementLabel,
      registryStatus: entry.status,
    };
  }

  if (mapped === "IMPLEMENTED") {
    if (allowed.length > 0) {
      if (!population.family || !allowed.includes(population.family) || !population.requestedDefinitionVersion) {
        return {
          name,
          status: "NOT_CONSTRUCTIBLE",
          kind: entry.kind ?? null,
          definitionVersion: entry.definition_version ?? null,
          reason: `Requires explicit definition_versions for one of: ${allowed.join(", ")}`,
          populationRequirement: requirementLabel,
          registryStatus: entry.status,
        };
      }
    }
    return {
      name,
      status: "IMPLEMENTED",
      kind: entry.kind ?? null,
      definitionVersion: entry.definition_version ?? null,
      reason: "REGISTERED ROUTE AVAILABLE",
      populationRequirement: requirementLabel,
      registryStatus: entry.status,
    };
  }

  return {
    name,
    status: "UNKNOWN",
    kind: entry.kind ?? null,
    definitionVersion: entry.definition_version ?? null,
    reason: `Unrecognized registry status ${entry.status}`,
    populationRequirement: requirementLabel,
    registryStatus: entry.status,
  };
}

export function analyzeResearchCapabilities(
  spec: Spec,
  capabilities: ResearchCapabilitiesPayload | null,
): ResearchCapabilityPreview | null {
  if (!capabilities) return null;

  const bindings = capabilities.population_bindings || [];
  const registry = capabilities.measurements || [];
  const population = analyzePopulation(spec, bindings);

  const requests = asArr(spec.measurement_requests) as Record<string, unknown>[];
  const measurements: MeasurementCapabilityPreview[] = requests.map((req) => {
    const name = typeof req.name === "string" ? req.name : "";
    if (!name) {
      return {
        name: "(unnamed)",
        status: "UNSUPPORTED",
        reason: "measurement_request missing name",
      };
    }
    return analyzeMeasurement(name, registry, population);
  });

  const summary = {
    implemented: 0,
    registered: 0,
    notConstructible: 0,
    unsupported: 0,
    absent: 0,
  };
  for (const m of measurements) {
    if (m.status === "IMPLEMENTED") summary.implemented += 1;
    else if (m.status === "REGISTERED") summary.registered += 1;
    else if (m.status === "NOT_CONSTRUCTIBLE") summary.notConstructible += 1;
    else if (m.status === "UNSUPPORTED") summary.unsupported += 1;
    else if (m.status === "ABSENT" || m.status === "ABSENT_IF_UNAVAILABLE") summary.absent += 1;
  }

  return { population, measurements, summary };
}

export function formatCapabilitySummary(preview: ResearchCapabilityPreview | null): string | null {
  if (!preview) return null;
  const parts: string[] = [];
  if (preview.summary.implemented) parts.push(`${preview.summary.implemented} IMPLEMENTED`);
  if (preview.summary.registered) parts.push(`${preview.summary.registered} REGISTERED`);
  if (preview.summary.notConstructible) {
    parts.push(`${preview.summary.notConstructible} NOT_CONSTRUCTIBLE`);
  }
  if (preview.summary.unsupported) parts.push(`${preview.summary.unsupported} UNSUPPORTED`);
  if (preview.summary.absent) parts.push(`${preview.summary.absent} ABSENT`);
  return parts.length ? parts.join(" · ") : "0 MEASUREMENT REQUESTS";
}

export function measurementsSectionSummary(
  requestCount: number,
  preview: ResearchCapabilityPreview | null,
  loading: boolean,
  error: string | null,
): string {
  if (loading) return `${requestCount} REQUESTS · CAPABILITY REGISTRY LOADING`;
  if (error) return `${requestCount} REQUESTS · CAPABILITY REGISTRY UNAVAILABLE`;
  if (!preview) return `${requestCount} REQUESTS`;
  const bits = [`${requestCount} REQUESTS`];
  if (preview.summary.implemented) bits.push(`${preview.summary.implemented} IMPLEMENTED`);
  if (preview.summary.registered) bits.push(`${preview.summary.registered} REGISTERED`);
  if (preview.summary.notConstructible) {
    bits.push(`${preview.summary.notConstructible} NOT_CONSTRUCTIBLE`);
  }
  if (preview.summary.unsupported) bits.push(`${preview.summary.unsupported} UNSUPPORTED`);
  return bits.join(" · ");
}
