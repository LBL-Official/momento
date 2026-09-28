/** Phase 5.7 — structural research_spec diff. Pure helpers only. */

import { canonicalize } from "./researchFreshness";
import type { Spec } from "./researchTypes";

export type DiffStatus = "UNCHANGED" | "CHANGED" | "ADDED" | "REMOVED";

export type ResearchSpecDiffEntry = {
  path: string;
  status: DiffStatus;
  current: unknown;
  snapshot: unknown;
};

export type ResearchSpecDiff = {
  equal: boolean;
  entries: ResearchSpecDiffEntry[];
  changed_count: number;
};

function isPlainObject(v: unknown): v is Record<string, unknown> {
  return v !== null && typeof v === "object" && !Array.isArray(v);
}

function deepEqual(a: unknown, b: unknown): boolean {
  return JSON.stringify(canonicalize(a)) === JSON.stringify(canonicalize(b));
}

function compact(value: unknown): unknown {
  // Keep values small for display; full objects remain inspectable via JSON.stringify in UI.
  return value;
}

/**
 * Structural diff between current editable spec and an immutable snapshot spec.
 * Object key order ignored (via canonicalize). Array order is meaningful.
 * Leaf-oriented paths; arrays compared as a whole at their path when contents differ.
 */
export function diffResearchSpecs(
  current: Spec,
  snapshot: Spec | null | undefined,
): ResearchSpecDiff {
  if (!snapshot) {
    return { equal: false, entries: [], changed_count: 0 };
  }

  const cur = canonicalize(current) as Record<string, unknown>;
  const snap = canonicalize(snapshot) as Record<string, unknown>;
  const entries: ResearchSpecDiffEntry[] = [];

  function walk(path: string, c: unknown, s: unknown): void {
    if (deepEqual(c, s)) return;

    // Both arrays → treat as single leaf change (no sequence alignment).
    if (Array.isArray(c) || Array.isArray(s)) {
      if (c === undefined) {
        entries.push({ path, status: "REMOVED", current: null, snapshot: compact(s) });
      } else if (s === undefined) {
        entries.push({ path, status: "ADDED", current: compact(c), snapshot: null });
      } else {
        entries.push({ path, status: "CHANGED", current: compact(c), snapshot: compact(s) });
      }
      return;
    }

    // Both plain objects → recurse into keys
    if (isPlainObject(c) && isPlainObject(s)) {
      const keys = new Set([...Object.keys(c), ...Object.keys(s)]);
      for (const key of [...keys].sort()) {
        const next = path ? `${path}.${key}` : key;
        const cv = c[key];
        const sv = s[key];
        if (!(key in c)) {
          entries.push({ path: next, status: "REMOVED", current: null, snapshot: compact(sv) });
        } else if (!(key in s)) {
          entries.push({ path: next, status: "ADDED", current: compact(cv), snapshot: null });
        } else {
          walk(next, cv, sv);
        }
      }
      return;
    }

    // One object / one scalar / mismatched types → leaf
    if (c === undefined || c === null && s !== null && s !== undefined && !isPlainObject(s) && !Array.isArray(s)) {
      // handled below
    }
    if (s === undefined) {
      entries.push({ path, status: "ADDED", current: compact(c), snapshot: null });
      return;
    }
    if (c === undefined) {
      entries.push({ path, status: "REMOVED", current: null, snapshot: compact(s) });
      return;
    }
    entries.push({ path, status: "CHANGED", current: compact(c), snapshot: compact(s) });
  }

  walk("", cur, snap);

  // Root-only equality check when no leaf entries
  const meaningful = entries.filter((e) => e.status !== "UNCHANGED" && e.path !== "");
  return {
    equal: meaningful.length === 0 && deepEqual(cur, snap),
    entries: meaningful,
    changed_count: meaningful.length,
  };
}

export function shortFingerprint(fp: string | null | undefined): string {
  if (!fp) return "—";
  // fp_XXXXXXXX_len → show first 8 hex chars of hash
  const m = /^fp_([0-9a-f]+)_/i.exec(fp);
  if (m) return m[1].slice(0, 8);
  return fp.slice(0, 10);
}

export function formatDiffValue(v: unknown): string {
  if (v === null || v === undefined) return "absent";
  if (typeof v === "string") return JSON.stringify(v);
  if (typeof v === "number" || typeof v === "boolean") return String(v);
  try {
    const s = JSON.stringify(v);
    return s.length > 120 ? `${s.slice(0, 117)}…` : s;
  } catch {
    return String(v);
  }
}
