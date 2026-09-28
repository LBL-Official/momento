const PREFIX = "jump.drive.draft.query.";

export type QueryDraft = {
  queryId: string | null;
  name: string;
  sql: string;
  updatedAt: string;
};

export function draftKey(warehouseId: string): string {
  return `${PREFIX}${warehouseId}`;
}

export function readQueryDraft(warehouseId: string): QueryDraft | null {
  try {
    const raw = localStorage.getItem(draftKey(warehouseId));
    if (!raw) return null;
    const parsed = JSON.parse(raw) as QueryDraft;
    if (!parsed || typeof parsed.sql !== "string") return null;
    return parsed;
  } catch {
    return null;
  }
}

export function writeQueryDraft(warehouseId: string, draft: QueryDraft): void {
  localStorage.setItem(draftKey(warehouseId), JSON.stringify(draft));
}

export function looksLikeReadonlySql(sql: string): boolean {
  return /^\s*(select|with|describe|desc|explain|show|from)\b/i.test(sql.trim());
}
