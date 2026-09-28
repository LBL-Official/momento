/**
 * Define search → vocabulary grammar. Language ≠ constructibility ≠ implementation.
 * Never rewrites SECOND80 to FIRST80.
 */

import { parsePhenomenon } from "../vocabulary/grammar";
import type { ConstructibilityStatus } from "../vocabulary/types";
import type { IntentClause } from "./recognizedIntent";

export type SearchOutcome = "RUNNABLE" | "PARTIALLY_AVAILABLE" | "RECOGNIZED" | "UNKNOWN";

export type DefineSearchResult = {
  outcome: SearchOutcome;
  templateId: "FIRST80_Q3" | "NCAAB_FIRST80_P5" | null;
  /** Overlay clauses for anything recognized but not constructible. */
  overlayClauses: IntentClause[];
  /** True when a SECOND/NTH (or similar) lock was requested — do not load FIRST80. */
  forbidFirst80Rewrite: boolean;
  summary: string;
};

function clauseFor(id: string, family: IntentClause["family"], label: string): IntentClause {
  return { id, family, label, constructible: false };
}

export function interpretDefineSearch(query: string): DefineSearchResult {
  const parsed = parsePhenomenon(query);
  if (!parsed.recognized && parsed.clauses.length === 0) {
    return {
      outcome: "UNKNOWN",
      templateId: null,
      overlayClauses: [],
      forbidFirst80Rewrite: false,
      summary: "Unknown — this is not a recognized research phrase.",
    };
  }

  const q = parsed.normalized;
  const hasNcaab = /\bncaab\b/.test(q);
  const hasP5 = /\bp5\b/.test(q);
  const hasQ3 = /\bq3\b/.test(q) || parsed.clauses.some((c) => c.period === "Q3");
  const first80 =
    parsed.clauses.some((c) => c.ordinal === 1 && c.cents === 80) || /\bfirst\s*80\b/.test(q);
  const laterOrdinal =
    parsed.clauses.some((c) => (c.ordinal ?? 1) >= 2) ||
    /\bsecond\s*80\b/.test(q) ||
    /\bnth\s*80\b/.test(q) ||
    /\bsecond\s*75\b/.test(q);
  const extraFamilies = parsed.clauses.filter(
    (c) =>
      c.constructibility === "NOT_CONSTRUCTIBLE" ||
      c.constructibility === "REGISTERED" ||
      ["BOUNCE_TO", "RECOVER_TO", "REVERSAL", "DROP_TO", "CROSS", "PRICE_STATE"].includes(
        c.familyId,
      ),
  );

  const overlayClauses: IntentClause[] = [];
  if (laterOrdinal) {
    const c = parsed.clauses.find((x) => (x.ordinal ?? 1) >= 2);
    const label = /\bsecond\s*75\b/.test(q)
      ? "SECOND75"
      : /\bnth\s*80\b/.test(q)
        ? "NTH80"
        : c?.displayName || "SECOND80";
    overlayClauses.push(clauseFor(c?.expressionId || label, "population", label));
  }
  for (const c of extraFamilies) {
    if (overlayClauses.some((o) => o.id === c.expressionId)) continue;
    overlayClauses.push(clauseFor(c.expressionId, familyFor(c.familyId), c.displayName));
  }
  if (/\bwnba\b/.test(q)) overlayClauses.push(clauseFor("wnba", "sport", "WNBA"));
  if (/\bq4\b/.test(q)) overlayClauses.push(clauseFor("Q4", "when", "Q4"));
  if (/\bot\b/.test(q)) overlayClauses.push(clauseFor("OT", "when", "OT"));

  const forbidFirst80Rewrite = laterOrdinal || overlayClauses.some((c) => c.family === "population");

  let templateId: DefineSearchResult["templateId"] = null;
  if (!forbidFirst80Rewrite) {
    if (hasNcaab && (first80 || hasP5)) templateId = "NCAAB_FIRST80_P5";
    else if (first80 && (hasQ3 || !hasNcaab)) templateId = "FIRST80_Q3";
  }

  const statuses = parsed.clauses.map((c) => c.constructibility);
  const outcome = decideOutcome(statuses, overlayClauses.length > 0, templateId);

  return {
    outcome,
    templateId,
    overlayClauses,
    forbidFirst80Rewrite,
    summary: outcomeSummary(outcome, templateId, overlayClauses),
  };
}

function familyFor(familyId: string): IntentClause["family"] {
  if (familyId === "BOUNCE_TO" || familyId === "RECOVER_TO" || familyId === "REVERSAL") {
    return "after";
  }
  if (familyId === "DROP_TO") return "prior";
  if (familyId === "PERIOD") return "when";
  if (familyId === "TERMINAL") return "terminal";
  return "event";
}

function decideOutcome(
  statuses: ConstructibilityStatus[],
  hasOverlay: boolean,
  templateId: string | null,
): SearchOutcome {
  if (hasOverlay && !templateId) return "RECOGNIZED";
  if (hasOverlay && templateId) return "PARTIALLY_AVAILABLE";
  if (templateId && statuses.every((s) => s === "IMPLEMENTED" || s === "CONFIGURABLE")) {
    return "RUNNABLE";
  }
  if (templateId) return "PARTIALLY_AVAILABLE";
  if (statuses.some((s) => s === "NOT_CONSTRUCTIBLE" || s === "REGISTERED")) return "RECOGNIZED";
  return "UNKNOWN";
}

function outcomeSummary(
  outcome: SearchOutcome,
  templateId: string | null,
  overlay: IntentClause[],
): string {
  if (outcome === "RUNNABLE") {
    return `Runnable — ${templateId} can be loaded from the backend lock.`;
  }
  if (outcome === "PARTIALLY_AVAILABLE") {
    return `Partially available — a lock can load, but ${overlay.map((c) => c.label).join(", ") || "requested conditions"} are not constructible.`;
  }
  if (outcome === "RECOGNIZED") {
    return `Recognized — not constructible. ${overlay.map((c) => c.label).join(", ") || "This structure"} will not be rewritten to FIRST80.`;
  }
  return "Unknown phrase.";
}
