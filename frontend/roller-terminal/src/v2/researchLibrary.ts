/** Local UI research library — NOT authoritative empirical persistence. */

import type { ResultSnapshot } from "../researchFreshness";
import type { Spec } from "../researchTypes";
import { asObj, blankSpec } from "../researchTypes";
import type { SavedResultSnapshot } from "./results/savedSnapshot";
import type { WorkflowDraft } from "./workflow/types";

export const LIBRARY_STORAGE_KEY = "roller.v2.research_library.v1";

export type LibraryFolder =
  | "Basketball/NBA/FIRST80"
  | "Basketball/NBA/Volatility"
  | "Basketball/NBA/Market Response"
  | "Basketball/NCAAB/FIRST80 P5"
  | "Baseball"
  | "Experimental"
  | "Archived";

export const DEFAULT_FOLDERS: LibraryFolder[] = [
  "Basketball/NBA/FIRST80",
  "Basketball/NBA/Volatility",
  "Basketball/NBA/Market Response",
  "Basketball/NCAAB/FIRST80 P5",
  "Baseball",
  "Experimental",
  "Archived",
];

export type LibraryEntry = {
  id: string;
  name: string;
  description: string;
  research_spec: Spec;
  created_at: string;
  updated_at: string;
  tags: string[];
  folder: string;
  spec_fingerprint?: string;
  /** Last known result summary — UI convenience only */
  last_result?: {
    population_n?: number | null;
    execution_status?: string | null;
    t40_rate?: number | null;
    kalshi_yes_rate?: number | null;
  } | null;
  /** Full last run so Results can be restored. Not a warehouse artifact. */
  last_result_snapshot?: ResultSnapshot | null;
  /** Immutable SAVE RESULTS snapshot. Reopen this, not the live study. */
  saved_snapshot?: SavedResultSnapshot | null;
  /** Disk save on the terminal API. Full trades live here, not in localStorage. */
  server_save_id?: string | null;
  /** QUESTION = draft only. COMPLETE = immutable result snapshot. */
  kind?: "QUESTION" | "COMPLETE";
  workflow_draft?: WorkflowDraft | null;
};

export function libraryEntryKind(entry: LibraryEntry): "QUESTION" | "COMPLETE" {
  if (entry.kind) return entry.kind;
  if (entry.saved_snapshot || entry.last_result_snapshot) return "COMPLETE";
  return "QUESTION";
}

export type LibraryState = {
  version: 1;
  entries: LibraryEntry[];
  folders: string[];
};

function emptyState(): LibraryState {
  return { version: 1, entries: [], folders: [...DEFAULT_FOLDERS] };
}

export function loadLibrary(): LibraryState {
  try {
    const raw = localStorage.getItem(LIBRARY_STORAGE_KEY);
    if (!raw) return emptyState();
    const parsed = JSON.parse(raw) as LibraryState;
    if (!parsed || parsed.version !== 1 || !Array.isArray(parsed.entries)) {
      return emptyState();
    }
    return {
      version: 1,
      entries: parsed.entries,
      folders: parsed.folders?.length ? parsed.folders : [...DEFAULT_FOLDERS],
    };
  } catch {
    return emptyState();
  }
}

export class LibraryPersistError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "LibraryPersistError";
  }
}

export function saveLibrary(state: LibraryState): void {
  try {
    localStorage.setItem(LIBRARY_STORAGE_KEY, JSON.stringify(state));
  } catch (err) {
    throw new LibraryPersistError(
      err instanceof Error
        ? `Could not write the local library (${err.name}). The full measurement is on the API disk save.`
        : "Could not write the local library.",
    );
  }
}

function newId(): string {
  return `lib_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`;
}

export function inferFolder(spec: Spec): string {
  const pop = asObj(spec.population_binding);
  const leagues = Array.isArray(pop.leagues) ? (pop.leagues as string[]) : [];
  const name = String(asObj(spec.identity).name || "");
  if (leagues.includes("NCAAB") || /NCAAB/i.test(name)) return "Basketball/NCAAB/FIRST80 P5";
  if (leagues.includes("NBA") || /FIRST80/i.test(name)) return "Basketball/NBA/FIRST80";
  return "Experimental";
}

export function saveCurrentObject(input: {
  name: string;
  description?: string;
  folder?: string;
  tags?: string[];
  research_spec: Spec;
  spec_fingerprint?: string;
  last_result?: LibraryEntry["last_result"];
  last_result_snapshot?: ResultSnapshot | null;
  saved_snapshot?: SavedResultSnapshot | null;
  workflow_draft?: WorkflowDraft | null;
  kind?: "QUESTION" | "COMPLETE";
  replaceId?: string;
  server_save_id?: string | null;
}): LibraryEntry {
  const state = loadLibrary();
  const now = new Date().toISOString();
  if (input.replaceId) {
    const idx = state.entries.findIndex((e) => e.id === input.replaceId);
    if (idx >= 0) {
      const next: LibraryEntry = {
        ...state.entries[idx],
        name: input.name,
        description: input.description ?? state.entries[idx].description,
        folder: input.folder ?? state.entries[idx].folder,
        tags: input.tags ?? state.entries[idx].tags,
        research_spec: structuredClone(input.research_spec),
        spec_fingerprint: input.spec_fingerprint ?? state.entries[idx].spec_fingerprint,
        updated_at: now,
        last_result:
          input.last_result !== undefined ? input.last_result : state.entries[idx].last_result,
        last_result_snapshot:
          input.last_result_snapshot !== undefined
            ? input.last_result_snapshot
            : state.entries[idx].last_result_snapshot,
        saved_snapshot:
          input.saved_snapshot !== undefined
            ? input.saved_snapshot
            : state.entries[idx].saved_snapshot,
        workflow_draft:
          input.workflow_draft !== undefined
            ? input.workflow_draft
            : state.entries[idx].workflow_draft,
        kind: input.kind ?? state.entries[idx].kind,
        server_save_id:
          input.server_save_id !== undefined
            ? input.server_save_id
            : state.entries[idx].server_save_id,
      };
      state.entries[idx] = next;
      state.entries = [next, ...state.entries.filter((e) => e.id !== next.id)];
      saveLibrary(state);
      return next;
    }
  }
  const entry: LibraryEntry = {
    id: newId(),
    name: input.name,
    description: input.description ?? "",
    research_spec: structuredClone(input.research_spec),
    spec_fingerprint: input.spec_fingerprint,
    created_at: now,
    updated_at: now,
    tags: input.tags ?? [],
    folder: input.folder ?? inferFolder(input.research_spec),
    last_result: input.last_result ?? null,
    last_result_snapshot: input.last_result_snapshot ?? null,
    saved_snapshot: input.saved_snapshot ?? null,
    workflow_draft: input.workflow_draft ?? null,
    kind:
      input.kind ??
      (input.saved_snapshot || input.last_result_snapshot ? "COMPLETE" : "QUESTION"),
    server_save_id: input.server_save_id ?? null,
  };
  state.entries.unshift(entry);
  if (!state.folders.includes(entry.folder)) state.folders.push(entry.folder);
  saveLibrary(state);
  return entry;
}

/** Explicit SAVE RESULTS — always a new immutable local snapshot. */
export function saveImmutableResult(input: {
  name: string;
  folder: string;
  description: string;
  research_spec: Spec;
  spec_fingerprint?: string;
  last_result: LibraryEntry["last_result"];
  last_result_snapshot: ResultSnapshot;
  saved_snapshot: SavedResultSnapshot;
  workflow_draft?: WorkflowDraft | null;
  server_save_id?: string | null;
}): LibraryEntry {
  return saveCurrentObject({
    name: input.name,
    description: input.description,
    folder: input.folder,
    research_spec: input.research_spec,
    spec_fingerprint: input.spec_fingerprint,
    last_result: input.last_result,
    last_result_snapshot: input.last_result_snapshot,
    saved_snapshot: input.saved_snapshot,
    workflow_draft: input.workflow_draft ?? null,
    kind: "COMPLETE",
    server_save_id: input.server_save_id ?? null,
  });
}

export function saveQuestionDraft(input: {
  name: string;
  folder?: string;
  description?: string;
  workflow_draft: WorkflowDraft;
}): LibraryEntry {
  return saveCurrentObject({
    name: input.name,
    folder: input.folder ?? "Experimental",
    description: input.description ?? "",
    research_spec: blankSpec(),
    workflow_draft: input.workflow_draft,
    kind: "QUESTION",
  });
}

/** Create or update the library row for a completed run so Results survive refresh. */
export function upsertRunResult(input: {
  name: string;
  description?: string;
  tags?: string[];
  research_spec: Spec;
  spec_fingerprint: string;
  last_result: LibraryEntry["last_result"];
  last_result_snapshot: ResultSnapshot;
  replaceId?: string | null;
}): LibraryEntry {
  const state = loadLibrary();
  const byId = input.replaceId
    ? state.entries.find((e) => e.id === input.replaceId)?.id
    : undefined;
  const byFp = state.entries.find((e) => e.spec_fingerprint === input.spec_fingerprint)?.id;
  return saveCurrentObject({
    name: input.name,
    description: input.description,
    tags: input.tags,
    research_spec: input.research_spec,
    spec_fingerprint: input.spec_fingerprint,
    last_result: input.last_result,
    last_result_snapshot: input.last_result_snapshot,
    replaceId: byId ?? byFp,
  });
}

export function deleteLibraryEntry(id: string): void {
  const state = loadLibrary();
  state.entries = state.entries.filter((e) => e.id !== id);
  saveLibrary(state);
}

/** Bump updated_at so the entry sorts into Recent — local UI only. */
export function touchEntry(id: string): void {
  const state = loadLibrary();
  const e = state.entries.find((x) => x.id === id);
  if (!e) return;
  e.updated_at = new Date().toISOString();
  state.entries = [e, ...state.entries.filter((x) => x.id !== id)];
  saveLibrary(state);
}

export function duplicateLibraryEntry(id: string): LibraryEntry | null {
  const state = loadLibrary();
  const src = state.entries.find((e) => e.id === id);
  if (!src) return null;
  return saveCurrentObject({
    name: `${src.name} (copy)`,
    description: src.description,
    folder: src.folder,
    tags: [...src.tags],
    research_spec: src.research_spec,
    spec_fingerprint: src.spec_fingerprint,
    last_result: src.last_result,
    last_result_snapshot: src.last_result_snapshot,
    saved_snapshot: src.saved_snapshot,
    workflow_draft: src.workflow_draft,
    kind: src.kind === "COMPLETE" ? "QUESTION" : src.kind,
  });
}

export function renameLibraryEntry(id: string, name: string): void {
  const state = loadLibrary();
  const e = state.entries.find((x) => x.id === id);
  if (!e) return;
  e.name = name;
  e.updated_at = new Date().toISOString();
  saveLibrary(state);
}

export function moveLibraryEntry(id: string, folder: string): void {
  const state = loadLibrary();
  const e = state.entries.find((x) => x.id === id);
  if (!e) return;
  e.folder = folder;
  e.updated_at = new Date().toISOString();
  if (!state.folders.includes(folder)) state.folders.push(folder);
  saveLibrary(state);
}

export function addLibraryFolder(folder: string): void {
  const state = loadLibrary();
  if (!state.folders.includes(folder)) {
    state.folders.push(folder);
    saveLibrary(state);
  }
}
