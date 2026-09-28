/**
 * Compact STAX form → ROLLER WorkflowDraft.
 *
 * STAX may construct a ROLLER-compatible specification. It must not
 * reinterpret, mutate, or bypass compile / measurement semantics.
 * This module only writes the same draft the full Entry / Exit screens use.
 */

import { catalogItem } from "../v2/catalog/availabilityCatalog";
import { emptyIntent } from "../v2/define/recognizedIntent";
import { newConditionId } from "../v2/workflow/draft";
import { dateRangeForSelections } from "../v2/workflow/seasonDates";
import type {
  EntryFamily,
  ExitCondition,
  ExitFamily,
  WorkflowDraft,
  WorkflowUniverse,
} from "../v2/workflow/types";
import type { CanonicalUniverse, StaxMember } from "./types";

export const NATIVE_LEAGUES = ["NBA", "NCAAB"] as const;
export const NATIVE_ENTRY_FAMILIES = ["first_touch", "cross"] as const;
export const NATIVE_TERMINALS = ["yes", "no", "both"] as const;
export const DEFAULT_NATIVE_SEASON = "2025-26";

export type NativeLeague = (typeof NATIVE_LEAGUES)[number];
export type NativeEntryFamily = (typeof NATIVE_ENTRY_FAMILIES)[number];
export type NativeTerminal = (typeof NATIVE_TERMINALS)[number];

export type NativeStrategyForm = {
  name: string;
  league: NativeLeague;
  season: string;
  entryFamily: NativeEntryFamily;
  entryCents: number;
  pathCents: number | null;
  lossCents: number | null;
  terminal: NativeTerminal;
};

export function sportsForLock(locked: CanonicalUniverse): string[] {
  const fromLeagues = (locked.league_set || [])
    .map((id) => catalogItem(id, "league")?.sports?.[0])
    .filter((x): x is string => Boolean(x));
  if (fromLeagues.length) return [...new Set(fromLeagues)];
  if (locked.sport_family === "baseball") return ["baseball"];
  if (locked.sport_family === "tennis") return ["tennis"];
  if (locked.sport_family === "basketball") return ["basketball"];
  return [];
}

export function universeFromLock(locked: CanonicalUniverse): WorkflowUniverse {
  const leagues = [...(locked.league_set || [])];
  const seasons = [...(locked.seasons || [])];
  const range = dateRangeForSelections(leagues, seasons);
  const sports = sportsForLock(locked);
  return {
    sports,
    leagues,
    seasons,
    dateFrom: locked.date_from || range.dateFrom,
    dateTo: locked.date_to || range.dateTo,
    markets: ["kalshi"],
    marketData: ["candles"],
    dataSources: [],
  };
}

export function basketballUniverse(league: NativeLeague, season: string): WorkflowUniverse {
  const leagues = [league];
  const seasons = [season];
  const range = dateRangeForSelections(leagues, seasons);
  return {
    sports: ["basketball"],
    leagues,
    seasons,
    dateFrom: range.dateFrom,
    dateTo: range.dateTo,
    markets: ["kalshi"],
    marketData: ["candles"],
    dataSources: [],
  };
}

function lockedLeague(locked: CanonicalUniverse | null): NativeLeague | null {
  const id = locked?.league_set?.[0];
  if (id === "NBA" || id === "NCAAB") return id;
  return null;
}

export function defaultNativeForm(locked: CanonicalUniverse | null): NativeStrategyForm {
  return {
    name: "",
    league: lockedLeague(locked) || "NBA",
    season: locked?.seasons?.[0] || DEFAULT_NATIVE_SEASON,
    entryFamily: "first_touch",
    entryCents: 75,
    pathCents: 85,
    lossCents: 35,
    terminal: "both",
  };
}

export function entryFamilyToken(family?: string): string {
  if (family === "first_touch") return "First";
  if (family === "second_touch") return "Second";
  if (family === "third_touch") return "Third";
  if (family === "fourth_touch") return "Fourth";
  if (family === "nth_touch") return "Nth";
  if (family === "cross") return "Cross";
  if (!family) return "Entry";
  return family.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()).replace(/\s+/g, "");
}

export function nativeStrategyLabel(form: NativeStrategyForm, locked?: CanonicalUniverse | null): string {
  const league = locked?.league_set?.[0] || form.league;
  const token = `${entryFamilyToken(form.entryFamily)}${form.entryCents}`;
  const left = `${league} ${token}`;
  if (form.pathCents == null) return left;
  if (form.lossCents == null) return `${left} → ${form.pathCents}`;
  return `${left} → ${form.pathCents} / ${form.lossCents}`;
}

function pathAsWin(form: NativeStrategyForm): boolean {
  return form.lossCents != null && form.pathCents != null;
}

export function nativeFormIssues(form: NativeStrategyForm): string[] {
  const issues: string[] = [];
  if (!form.season) issues.push("Season is required");
  if (form.entryCents == null) issues.push("Entry price is required");
  if (form.pathCents == null) issues.push("Path price is required");
  if (pathAsWin(form)) {
    if (form.pathCents != null && form.pathCents < form.entryCents) {
      issues.push("Path (WIN) cannot be under the entry price");
    }
    if (form.lossCents != null && form.lossCents > form.entryCents) {
      issues.push("Loss / stop cannot be over the entry price");
    }
  }
  return issues;
}

function entryCondition(form: NativeStrategyForm) {
  const family = form.entryFamily as EntryFamily;
  return {
    id: newConditionId("entry"),
    family,
    priceCents: form.entryCents,
    ...(family === "first_touch" ? { touchN: 1 as const } : {}),
  };
}

function exitConditions(form: NativeStrategyForm): ExitCondition[] {
  const exits: ExitCondition[] = [];
  if (form.pathCents != null) {
    exits.push({
      id: newConditionId("exit"),
      kind: "path",
      family: "reach" as ExitFamily,
      priceCents: form.pathCents,
      ...(pathAsWin(form) ? { outcome: "win" as const, sequential: false } : {}),
    });
  }
  if (form.lossCents != null) {
    exits.push({
      id: newConditionId("exit"),
      kind: "path",
      family: "reach" as ExitFamily,
      priceCents: form.lossCents,
      outcome: "loss",
      sequential: false,
    });
  }
  exits.push({
    id: newConditionId("exit"),
    kind: "terminal",
    family: form.terminal,
  });
  return exits;
}

/** Build the WorkflowDraft the ROLLER compiler already understands. */
export function draftFromNativeForm(
  form: NativeStrategyForm,
  locked: CanonicalUniverse | null,
): WorkflowDraft {
  return {
    universe: locked ? universeFromLock(locked) : basketballUniverse(form.league, form.season),
    entryConditions: [entryCondition(form)],
    exitConditions: exitConditions(form),
    teFilters: { scoreSide: "any", absDiff: "any" },
    recognizedIntent: emptyIntent(),
    status: "DRAFT",
  };
}

type DraftLike = {
  universe?: { leagues?: string[] };
  entryConditions?: Array<{ family?: string; priceCents?: number }>;
  exitConditions?: Array<{
    kind?: string;
    family?: string;
    priceCents?: number;
    outcome?: string;
  }>;
};

export function nativeStrategyLabelFromDraft(draft: DraftLike | null | undefined): string | null {
  if (!draft) return null;
  const league = draft.universe?.leagues?.[0];
  const entry = draft.entryConditions?.[0];
  if (!league || entry?.priceCents == null) return null;
  const paths = (draft.exitConditions || []).filter((e) => e.kind === "path" && e.priceCents != null);
  const win = paths.find((p) => p.outcome === "win") ?? paths[0];
  const loss = paths.find((p) => p.outcome === "loss" && p !== win);
  const token = `${entryFamilyToken(entry.family)}${entry.priceCents}`;
  if (!win?.priceCents) return `${league} ${token}`;
  if (loss?.priceCents) return `${league} ${token} → ${win.priceCents} / ${loss.priceCents}`;
  return `${league} ${token} → ${win.priceCents}`;
}

export function ledgerLabel(member: StaxMember): string {
  const fromDraft = nativeStrategyLabelFromDraft(member.draft);
  if (fromDraft) return fromDraft;
  const label = member.label?.trim();
  if (label && !label.startsWith("Across ")) return label;
  return member.display_id || member.member_id;
}

export function ledgerStatus(member: StaxMember, runStatus?: string | null): string {
  if (runStatus) return runStatus;
  if (member.status && member.status !== "PENDING") return member.status;
  return "READY";
}
