import { apiFetch } from "../../api/base";

export type DriveArtifact = {
  artifact_id: string;
  name: string;
  artifact_type: string;
  warehouse_id?: string | null;
  table_name?: string | null;
  system_owner: string;
  sport?: string | null;
  strategy?: string | null;
  parent_folder?: string | null;
  source_path?: string | null;
  api_target?: string | null;
  frontend_target?: string | null;
  status?: string;
  research_stage?: string;
  description?: string;
  tags?: string[];
  canonical_key?: string | null;
  display_name?: string | null;
  slug?: string | null;
  doc_id?: string | null;
  kind?: string | null;
  uuid?: string | null;
  needs_resolution?: boolean;
  empty_message?: string | null;
  object_count?: number;
  provenance?: SourceRef[];
  children?: DriveArtifact[];
  updated_at?: string | null;
  created_at?: string | null;
};

export type SourceRef = {
  owner: string;
  role: string;
  path: string;
  status: string;
  note?: string;
  api_target?: string | null;
};

export type JumpObject = {
  canonical_key: string;
  display_name: string;
  name: string;
  sports: string[];
  home_sport: string;
  status: string;
  population_n: number | null;
  population_label: string;
  research_object_id?: string | null;
  package_id?: string | null;
  package_folder?: string | null;
  question_hash?: string | null;
  uuid?: string | null;
  metadata?: Record<string, unknown>;
  sources?: SourceRef[];
  unresolved_aliases?: SourceRef[];
  needs_resolution?: boolean;
  documents?: JumpDocument[];
  artifacts?: DriveArtifact[];
};

export type JumpDocument = {
  doc_id: string;
  canonical_key: string;
  slug: string;
  title: string;
  body_markdown: string;
  provenance: SourceRef[];
  status: string;
};

export type DriveFolder = {
  folder: DriveArtifact;
  breadcrumbs: { artifact_id: string; name: string }[];
  children: DriveArtifact[];
  empty_message?: string | null;
};

export type DriveArtifactDetail = {
  artifact: DriveArtifact;
  breadcrumbs: { artifact_id: string; name: string }[];
};

export type SearchHit = {
  title: string;
  name: string;
  kind: string;
  canonical_key?: string | null;
  folder?: string | null;
  sport?: string | null;
  artifact_id: string;
  doc_id?: string;
  slug?: string;
  snippet?: string;
};

export type SportInfo = {
  id: string;
  name: string;
  artifact_id: string;
  object_count: number;
  status: string;
  empty_message?: string | null;
};

async function parse<T>(res: Response): Promise<T> {
  const body = (await res.json()) as T & { detail?: string | { message?: string } };
  if (!res.ok) {
    const detail = body.detail;
    const message =
      typeof detail === "string"
        ? detail
        : detail && typeof detail === "object"
          ? detail.message || res.statusText
          : res.statusText;
    throw new Error(message || res.statusText);
  }
  return body;
}

export async function getDriveRoot(sport?: string): Promise<{
  default_sport: string;
  sport: string;
  sports: SportInfo[];
  roots: DriveArtifact[];
  children: DriveArtifact[];
  empty_message?: string | null;
}> {
  const suffix = sport ? `?sport=${encodeURIComponent(sport)}` : "";
  const res = await apiFetch(`/jump${suffix}`);
  return parse(res);
}

export async function getSports(): Promise<{ sports: SportInfo[]; default_sport: string }> {
  const res = await apiFetch("/jump/sports");
  return parse(res);
}

export async function getResearch(sport: string): Promise<{
  objects: JumpObject[];
  empty_message?: string | null;
  sport: string;
}> {
  const res = await apiFetch(`/jump/research?sport=${encodeURIComponent(sport)}`);
  return parse(res);
}

export async function getResearchObject(key: string): Promise<{ object: JumpObject }> {
  const res = await apiFetch(`/jump/research/${encodeURIComponent(key)}`);
  return parse(res);
}

export async function getResearchChildren(key: string): Promise<{
  object: JumpObject;
  children: DriveArtifact[];
  breadcrumbs: { artifact_id: string; name: string }[];
}> {
  const res = await apiFetch(`/jump/research/${encodeURIComponent(key)}/children`);
  return parse(res);
}

export async function getDocument(docId: string): Promise<{
  document: JumpDocument & { body?: string };
  object: JumpObject | null;
  breadcrumbs: { artifact_id: string; name: string }[];
}> {
  const res = await apiFetch(`/jump/documents/${encodeURIComponent(docId)}`);
  return parse(res);
}

export async function getDriveTree(): Promise<{ tree: DriveArtifact[] }> {
  const res = await apiFetch("/jump/tree");
  return parse(res);
}

export async function getDriveFolder(id: string): Promise<DriveFolder> {
  const res = await apiFetch(`/jump/folders/${encodeURIComponent(id)}`);
  return parse(res);
}

export async function getDriveArtifact(id: string): Promise<DriveArtifactDetail> {
  const res = await apiFetch(`/jump/artifacts/${encodeURIComponent(id)}`);
  return parse(res);
}

export async function searchDrive(q: string): Promise<{ results: SearchHit[] }> {
  const res = await apiFetch(`/jump/search?q=${encodeURIComponent(q)}`);
  return parse(res);
}

export async function getDriveRecent(): Promise<{ results: SearchHit[] }> {
  const res = await apiFetch("/jump/recent");
  return parse(res);
}

export async function previewArtifact(id: string): Promise<{
  artifact_id: string;
  name: string;
  source_path: string | null;
  kind?: string;
  status: string;
  preview: unknown;
  truncated?: boolean;
  note?: string;
}> {
  const res = await apiFetch(`/jump/artifacts/${encodeURIComponent(id)}/preview`);
  return parse(res);
}

export async function refreshIndex(): Promise<{ rebuilt_at: string; object_count: number }> {
  const res = await apiFetch("/jump/index/refresh", { method: "POST" });
  return parse(res);
}
