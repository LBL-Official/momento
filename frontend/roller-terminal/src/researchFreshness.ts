/** Phase 5.6 — UI freshness identity for research_spec. Pure helpers only. */

import type { Spec, ValidateResult } from "./researchTypes";
import type { ResearchResult } from "./ResultsView";
import type { WorkflowDraft } from "./v2/workflow/types";

export type ValidationSnapshot = {
  payload: ValidateResult;
  /** Immutable clone of the App-owned spec submitted for this validation. */
  spec: Spec;
  specFingerprint: string;
};

export type ResultSnapshot = {
  payload: ResearchResult;
  /** Immutable clone of the App-owned spec submitted for this execution. */
  spec: Spec;
  specFingerprint: string;
  /** Draft that produced this run. SuperASI re-executes this, not the live editor. */
  workflowDraft?: WorkflowDraft;
  /** Measurement-identity hash of workflowDraft. Spec fingerprint alone is not the Quick Start question. */
  draftFingerprint?: string;
  acceptLimitations?: boolean;
};

export type Freshness = "NONE" | "UNVALIDATED" | "CURRENT" | "STALE";

/** Recursively sort object keys; preserve array order. Does not mutate input. */
export function canonicalize(value: unknown): unknown {
  if (value === null || typeof value !== "object") {
    if (typeof value === "number" && Number.isNaN(value)) return null;
    return value;
  }
  if (Array.isArray(value)) {
    return value.map((item) => canonicalize(item));
  }
  const obj = value as Record<string, unknown>;
  const out: Record<string, unknown> = {};
  for (const key of Object.keys(obj).sort()) {
    out[key] = canonicalize(obj[key]);
  }
  return out;
}

/** Lightweight non-crypto hash of a string (UI identity only). */
function fnv1a(str: string): string {
  let h = 0x811c9dc5;
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }
  return (h >>> 0).toString(16).padStart(8, "0");
}

/**
 * Deterministic fingerprint of a research_spec for UI freshness.
 * Not a replacement for backend research_object_id.
 */
export function stableSpecFingerprint(spec: Spec): string {
  const serialized = JSON.stringify(canonicalize(spec));
  return `fp_${fnv1a(serialized)}_${serialized.length.toString(16)}`;
}

/** Quick Start measurement identity. Ignores client condition ids. Dates stay as entered. */
export function stableDraftFingerprint(draft: WorkflowDraft): string {
  const u = draft.universe;
  const ident = {
    sports: u.sports,
    leagues: u.leagues,
    seasons: u.seasons,
    markets: u.markets,
    marketData: u.marketData,
    dataSources: u.dataSources ?? [],
    dates: { dateFrom: u.dateFrom ?? null, dateTo: u.dateTo ?? null },
    entry: draft.entryConditions.map((e) => ({
      family: e.family,
      priceCents: e.priceCents ?? null,
      priceFrom: e.priceFrom ?? null,
      priceTo: e.priceTo ?? null,
      period: e.period ?? null,
      clockFrom: e.clockFrom ?? null,
      clockTo: e.clockTo ?? null,
      periodWindows: e.periodWindows ?? [],
      gameFrom: e.gameFrom ?? null,
      gameTo: e.gameTo ?? null,
      touchN: e.touchN ?? null,
      touchNValue: e.touchNValue ?? null,
      direction: e.direction ?? null,
      magnitudeCents: e.magnitudeCents ?? null,
    })),
    exit: draft.exitConditions.map((e) => ({
      kind: e.kind,
      family: e.family,
      priceCents: e.priceCents ?? null,
      sequential: Boolean(e.sequential),
      outcome: e.outcome ?? null,
      horizonKind: e.horizonKind ?? null,
      horizonMinutes: e.horizonMinutes ?? null,
    })),
    te: draft.teFilters ?? null,
    exposure: {
      mode: draft.exposureEnforcementMode ?? null,
      unit: draft.exposureUnit ?? null,
      max: draft.maxEntriesPerGame ?? draft.maxEntriesPerUnit ?? null,
    },
  };
  const serialized = JSON.stringify(canonicalize(ident));
  return `dfp_${fnv1a(serialized)}_${serialized.length.toString(16)}`;
}

export function snapshotDraftFingerprint(snapshot: ResultSnapshot | null): string | null {
  if (!snapshot) return null;
  if (snapshot.draftFingerprint) return snapshot.draftFingerprint;
  if (snapshot.workflowDraft) return stableDraftFingerprint(snapshot.workflowDraft);
  return null;
}

export function snapshotMatchesDraft(
  snapshot: ResultSnapshot | null,
  draft: WorkflowDraft,
): boolean {
  const snapFp = snapshotDraftFingerprint(snapshot);
  return Boolean(snapFp && snapFp === stableDraftFingerprint(draft));
}

export function getValidationFreshness(
  currentFingerprint: string,
  snapshot: ValidationSnapshot | null,
): Freshness {
  if (!snapshot) return "UNVALIDATED";
  return snapshot.specFingerprint === currentFingerprint ? "CURRENT" : "STALE";
}

export function getExecutionFreshness(
  currentFingerprint: string,
  snapshot: ResultSnapshot | null,
  currentDraftFingerprint?: string | null,
): Freshness {
  if (!snapshot) return "NONE";
  if (currentDraftFingerprint) {
    const snapDraftFp = snapshotDraftFingerprint(snapshot);
    if (!snapDraftFp) return "STALE";
    return snapDraftFp === currentDraftFingerprint ? "CURRENT" : "STALE";
  }
  return snapshot.specFingerprint === currentFingerprint ? "CURRENT" : "STALE";
}

/** True only when validation is CURRENT and backend status is RUNNABLE. */
export function canRunResearch(
  validationFreshness: Freshness,
  snapshot: ValidationSnapshot | null,
): boolean {
  return (
    validationFreshness === "CURRENT" &&
    snapshot?.payload.status === "RUNNABLE" &&
    Boolean(snapshot.payload.runnable)
  );
}

export function effectiveSpecStatus(args: {
  validationFreshness: Freshness;
  validationSnapshot: ValidationSnapshot | null;
  hasProposedInterpretation: boolean;
}): string {
  if (args.validationFreshness === "STALE") return "STALE";
  if (args.validationFreshness === "UNVALIDATED") {
    return args.hasProposedInterpretation ? "PROPOSED" : "UNVALIDATED";
  }
  const status = args.validationSnapshot?.payload.status;
  if (status === "RUNNABLE") return "RUNNABLE";
  if (status === "UNRESOLVED") return "UNRESOLVED";
  if (status === "INVALID") return "INVALID";
  if (args.validationSnapshot?.payload.valid) return "VALID";
  return "UNVALIDATED";
}

export function effectiveExecutionStatus(args: {
  executionFreshness: Freshness;
  resultSnapshot: ResultSnapshot | null;
  runBusy: boolean;
}): string {
  if (args.runBusy) return "EXECUTING";
  if (args.executionFreshness === "NONE") return "ABSENT";
  if (args.executionFreshness === "STALE") return "STALE";
  return args.resultSnapshot?.payload.execution_status ?? "ABSENT";
}
