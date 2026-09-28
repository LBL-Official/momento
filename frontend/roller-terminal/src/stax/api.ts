import { apiFetch } from "../api/base";
import type { LibraryRow, StaxCandidate, StaxCompare, StaxHead, StaxMember, StaxVersion } from "./types";

export class StaxApiError extends Error {
  code?: string;
  details?: Record<string, unknown>;

  constructor(message: string, code?: string, details?: Record<string, unknown>) {
    super(message);
    this.name = "StaxApiError";
    this.code = code;
    this.details = details;
  }
}

function formatMismatches(details?: Record<string, unknown>): string {
  if (!details) return "";
  return Object.entries(details)
    .map(([key, value]) => {
      if (value && typeof value === "object") {
        return `${key}: ${JSON.stringify(value)}`;
      }
      return `${key}: ${String(value)}`;
    })
    .join("\n");
}

async function parse<T>(res: Response): Promise<T> {
  const body = (await res.json()) as T & {
    detail?: { message?: string; code?: string; details?: Record<string, unknown> } | string;
    message?: string;
    code?: string;
    details?: Record<string, unknown>;
  };
  if (!res.ok) {
    const detail = body.detail;
    const code = (typeof detail === "object" && detail?.code) || body.code;
    const details = (typeof detail === "object" && detail?.details) || body.details;
    const raw =
      (typeof detail === "object" && detail?.message) ||
      (typeof detail === "string" ? detail : null) ||
      body.message ||
      res.statusText;
    const extra = formatMismatches(details);
    const message =
      code === "STAX_CONSTRAINT_VIOLATION"
        ? ["STAX CONSTRAINT VIOLATION", raw, extra].filter(Boolean).join("\n")
        : extra
          ? `${raw}\n${extra}`
          : String(raw);
    throw new StaxApiError(message, code, details);
  }
  return body;
}

export async function createStax(body: Record<string, unknown>): Promise<{
  stax: StaxHead;
  members: StaxMember[];
}> {
  const res = await apiFetch("/stax", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return parse(res);
}

export async function listStax(): Promise<{ stax: LibraryRow[]; n: number }> {
  const res = await apiFetch("/stax");
  return parse(res);
}

export async function getStax(staxId: string): Promise<{
  stax: StaxHead;
  members: StaxMember[];
  latest: StaxVersion | null;
  versions: Array<{ version: string; kind?: string; created_at?: string; status?: string; strategy_count?: number }>;
}> {
  const res = await apiFetch(`/stax/${encodeURIComponent(staxId)}`);
  return parse(res);
}

export async function getStaxVersion(staxId: string, version: string): Promise<StaxVersion> {
  const res = await apiFetch(`/stax/${encodeURIComponent(staxId)}/versions/${encodeURIComponent(version)}`);
  return parse(res);
}

export type StaxCreateStrategyResponse = {
  ok?: boolean;
  valid?: boolean;
  persisted?: boolean;
  duplicate?: boolean;
  duplicate_member_ids?: string[];
  message?: string;
  code?: string;
  reasons?: string[];
  compile?: { status?: string; reasons?: string[]; question?: Record<string, unknown> };
  hashes?: { question_hash?: string };
  universe?: StaxHead["universe"];
  name?: string;
  stax?: StaxHead;
  members?: StaxMember[];
  member?: StaxMember;
  roller?: {
    save_id?: string;
    research_object_id?: string | null;
    question_hash?: string;
    question?: Record<string, unknown>;
  };
};

export async function createStaxStrategy(
  staxId: string,
  body: Record<string, unknown>,
): Promise<StaxCreateStrategyResponse> {
  const res = await apiFetch(`/stax/${encodeURIComponent(staxId)}/strategies`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return parse<StaxCreateStrategyResponse>(res);
}

export async function validateStax(staxId: string, body: Record<string, unknown>) {
  const res = await apiFetch(`/stax/${encodeURIComponent(staxId)}/validate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return parse<{ ok: boolean; universe?: unknown; members: StaxMember[]; message?: string }>(res);
}

export async function runStax(staxId: string, body: Record<string, unknown> = {}) {
  const res = await apiFetch(`/stax/${encodeURIComponent(staxId)}/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return parse<StaxVersion>(res);
}

export async function setAutomation(staxId: string, body: Record<string, unknown>) {
  const res = await apiFetch(`/stax/${encodeURIComponent(staxId)}/automation`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return parse<{
    automation_enabled: boolean;
    timezone: string;
    schedule: string;
    next_run_at?: string;
    message: string;
    live_execution: boolean;
  }>(res);
}

export async function compareStax(staxId: string, from: string, to: string) {
  const res = await apiFetch(`/stax/${encodeURIComponent(staxId)}/compare`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ from, to }),
  });
  return parse<StaxCompare>(res);
}

export async function listCandidates() {
  const res = await apiFetch("/stax/candidates");
  return parse<{ candidates: StaxCandidate[]; n: number }>(res);
}

export async function exportStax(staxId: string, version?: string) {
  const q = version ? `?version=${encodeURIComponent(version)}` : "";
  const res = await apiFetch(`/stax/${encodeURIComponent(staxId)}/export${q}`);
  return parse<Record<string, unknown>>(res);
}
