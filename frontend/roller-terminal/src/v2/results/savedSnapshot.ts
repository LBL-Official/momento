/** Immutable local result snapshot. Not a warehouse artifact. */

import type { ResultSnapshot, ValidationSnapshot } from "../../researchFreshness";
import type { Spec } from "../../researchTypes";
import { asObj } from "../../researchTypes";
import type { AnswerResult } from "./ResultsAnswer";
import type { WorkflowDraft } from "../workflow/types";

export const SAVED_SNAPSHOT_KIND = "SAVED_RESULT_SNAPSHOT_LOCAL" as const;

export type SavedResultSnapshot = {
  kind: typeof SAVED_SNAPSHOT_KIND;
  saved_at: string;
  name: string;
  folder: string;
  description: string;
  identity: Record<string, unknown>;
  research_spec: Spec;
  validation_status: string | null;
  execution_identity: {
    status?: string;
    research_object_id?: string | null;
  };
  result_summary: {
    population_n?: number | null;
    execution_status?: string | null;
    t40_rate?: number | null;
    kalshi_yes_rate?: number | null;
  } | null;
  population_n: number | null;
  measurements: unknown;
  empirical_partition: unknown;
  provenance: unknown;
  result_snapshot: ResultSnapshot;
  question: string;
  workflow_draft?: WorkflowDraft | null;
};

/** Drop the N-row trade list so localStorage can hold a pointer, not the warehouse. */
export function compactResultSnapshot<T extends { payload?: unknown }>(snapshot: T): T {
  const payload = snapshot.payload as
    | {
        population?: {
          trades?: unknown[];
          rows?: unknown[];
          count?: number;
          rows_truncated?: boolean;
        };
      }
    | undefined;
  const pop = payload?.population;
  if (!pop?.trades?.length) return snapshot;
  return {
    ...snapshot,
    payload: {
      ...(payload as object),
      population: {
        ...pop,
        trades: [],
        rows: Array.isArray(pop.rows) ? pop.rows.slice(0, 25) : [],
        rows_truncated: true,
      },
    },
  };
}

export function buildSavedSnapshot(input: {
  name: string;
  folder: string;
  description: string;
  spec: Spec;
  resultSnapshot: ResultSnapshot;
  validationSnapshot: ValidationSnapshot | null;
  question: string;
  workflowDraft?: WorkflowDraft | null;
}): SavedResultSnapshot {
  const payload = input.resultSnapshot.payload as AnswerResult;
  const t40 = payload.measurements?.find((m) => m.name === "t40_rate");
  const yes = payload.measurements?.find((m) => m.name === "kalshi_yes_rate");
  const n = payload.summary?.population_n ?? payload.population?.count ?? null;
  return {
    kind: SAVED_SNAPSHOT_KIND,
    saved_at: new Date().toISOString(),
    name: input.name,
    folder: input.folder,
    description: input.description,
    identity: asObj(input.spec.identity),
    research_spec: structuredClone(input.spec),
    validation_status: input.validationSnapshot?.payload.status ?? null,
    execution_identity: {
      status: payload.execution_status,
      research_object_id: payload.research_object_id ?? null,
    },
    result_summary: {
      population_n: n,
      execution_status: payload.execution_status ?? null,
      t40_rate: t40?.value ?? null,
      kalshi_yes_rate: yes?.value ?? null,
    },
    population_n: n,
    measurements: payload.measurements ?? null,
    empirical_partition: payload.empirical_partition ?? null,
    provenance: payload.provenance ?? null,
    result_snapshot: compactResultSnapshot(structuredClone(input.resultSnapshot)),
    question: input.question,
    workflow_draft: input.workflowDraft ? structuredClone(input.workflowDraft) : null,
  };
}
