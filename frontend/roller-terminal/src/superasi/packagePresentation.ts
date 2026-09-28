import { nativeStrategyLabelFromDraft } from "../stax/nativeDraft";
import { emptyDraft } from "../v2/workflow/draft";
import { composeQuestionFromDraft } from "../v2/workflow/questionFromDraft";
import type { ConstructibilityResolution, WorkflowDraft } from "../v2/workflow/types";
import { shortHash } from "./format";

export type PackagePresentationSource = {
  package_id: string;
  name?: string | null;
  source?: string | null;
  research_object_id?: string | null;
  question_hash?: string | null;
  hashes?: Record<string, string | undefined> | null;
  research_spec?: { identity?: { name?: string | null } | null } | null;
  roller_handoff?: { workflow_draft?: unknown } | null;
  workflow_draft?: unknown;
};

function asDraft(raw: unknown): WorkflowDraft | null {
  if (!raw || typeof raw !== "object") return null;
  const d = raw as Partial<WorkflowDraft>;
  if (!d.universe || !Array.isArray(d.entryConditions)) return null;
  return {
    universe: d.universe,
    entryConditions: d.entryConditions,
    exitConditions: Array.isArray(d.exitConditions) ? d.exitConditions : [],
    teFilters: d.teFilters,
    recognizedIntent: d.recognizedIntent ?? emptyDraft().recognizedIntent,
    status: d.status ?? "DRAFT",
    matchedTemplateId: d.matchedTemplateId,
  };
}

export function packageDraft(pkg: PackagePresentationSource | null | undefined): WorkflowDraft | null {
  if (!pkg) return null;
  return asDraft(pkg.workflow_draft) ?? asDraft(pkg.roller_handoff?.workflow_draft);
}

export function packageHash(
  pkg: PackagePresentationSource | null | undefined,
  extra?: { question_hash?: string | null } | null,
): string | null {
  const hash =
    pkg?.question_hash ||
    pkg?.hashes?.question_hash ||
    extra?.question_hash ||
    null;
  return hash || null;
}

export function packageTitle(pkg: PackagePresentationSource | null | undefined): string {
  if (!pkg) return "No measurement";
  const named =
    pkg.name?.trim() ||
    pkg.research_spec?.identity?.name?.trim() ||
    pkg.research_object_id?.trim();
  if (named) return named;
  const fromDraft = nativeStrategyLabelFromDraft(packageDraft(pkg));
  if (fromDraft) return fromDraft;
  return pkg.package_id;
}

function frozenResolution(
  template: NonNullable<ConstructibilityResolution["matchedTemplate"]>,
): ConstructibilityResolution {
  return {
    status: "READY",
    matchedTemplate: template,
    frozenPopulation: true,
    blockingReasons: [],
    recognizedSelections: [],
  };
}

export function packageQuestion(pkg: PackagePresentationSource | null | undefined): string | null {
  if (!pkg) return null;
  const draft = packageDraft(pkg);
  const rid = pkg.research_object_id || "";
  if (rid.startsWith("NCAAB_FIRST80")) {
    return composeQuestionFromDraft(draft ?? emptyDraft(), frozenResolution("NCAAB_FIRST80_P5"));
  }
  if (rid.startsWith("FIRST80") || pkg.source === "seed_asked_six") {
    return composeQuestionFromDraft(draft ?? emptyDraft(), frozenResolution("FIRST80_Q3"));
  }
  if (draft) return composeQuestionFromDraft(draft);
  return null;
}

export function packageLabel(item: PackagePresentationSource): string {
  return packageTitle(item);
}

export function packageStatus(item: {
  decomposition_status?: string | null;
  population_n?: number | null;
}): string {
  return item.decomposition_status || (item.population_n != null ? "PRESENT" : "READY");
}

export function packageHashShort(
  pkg: PackagePresentationSource | null | undefined,
  extra?: { question_hash?: string | null } | null,
  head = 16,
): string | null {
  const hash = packageHash(pkg, extra);
  return hash ? shortHash(hash, head) : null;
}
