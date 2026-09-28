/** Optional period / clock partitions. Filters, not a new ordinal universe. */

import type { PeriodWindowSel } from "./types";

export type PeriodChip = {
  id: string;
  label: string;
  period?: string;
  clockFrom?: string;
  clockTo?: string;
};

export const NBA_PERIODS: PeriodChip[] = [
  { id: "Q1", label: "Q1", period: "Q1" },
  { id: "Q2", label: "Q2", period: "Q2" },
  { id: "Q3", label: "Q3", period: "Q3" },
  { id: "Q4", label: "Q4", period: "Q4" },
  { id: "OT", label: "OT", period: "OT" },
];

/** NBA 12:00 quarters in 4-minute remaining windows. */
export const NBA_4MIN: PeriodChip[] = ["Q1", "Q2", "Q3", "Q4"].flatMap((q) => [
  { id: `${q}_12_8`, label: `${q} 1st 4`, period: q, clockFrom: "12:00", clockTo: "08:00" },
  { id: `${q}_8_4`, label: `${q} 2nd 4`, period: q, clockFrom: "08:00", clockTo: "04:00" },
  { id: `${q}_4_0`, label: `${q} 3rd 4`, period: q, clockFrom: "04:00", clockTo: "00:00" },
]);

export const NCAAB_PERIODS: PeriodChip[] = [
  { id: "H1", label: "1H", period: "H1" },
  { id: "H2", label: "2H", period: "H2" },
  { id: "OT", label: "OT", period: "OT" },
  { id: "P5", label: "P5", period: "P5" },
];

/** NCAAB 20:00 halves in 10-minute remaining windows (matches H1_1 / H1_2 slices). */
export const NCAAB_10MIN: PeriodChip[] = [
  { id: "H1_1", label: "1H 1st 10", period: "H1_1" },
  { id: "H1_2", label: "1H 2nd 10", period: "H1_2" },
  { id: "H2_1", label: "2H 1st 10", period: "H2_1" },
  { id: "H2_2", label: "2H 2nd 10", period: "H2_2" },
];

export const MLB_INNINGS: PeriodChip[] = [
  ...[1, 2, 3, 4, 5, 6, 7, 8, 9].flatMap((n) => [
    { id: `T${n}`, label: `T${n}`, period: `T${n}` },
    { id: `B${n}`, label: `B${n}`, period: `B${n}` },
  ]),
  { id: "TX", label: "TX", period: "TX" },
  { id: "BX", label: "BX", period: "BX" },
  { id: "I7", label: "I7", period: "I7" },
];

/** Tennis set windows — structural entry, OR within group. */
export const TENNIS_SETS: PeriodChip[] = ["S1", "S2", "S3", "S4", "S5"].map((s) => ({
  id: s,
  label: s,
  period: s,
}));

/** Tennis game windows — structural entry, OR within group. */
export const TENNIS_GAMES: PeriodChip[] = [
  { id: "G1-3", label: "G1–3", period: "G1-3" },
  { id: "G4-6", label: "G4–6", period: "G4-6" },
  { id: "G7-9", label: "G7–9", period: "G7-9" },
  { id: "G10+", label: "G10+", period: "G10+" },
];

export const NCAAB_5MIN: PeriodChip[] = [
  { id: "H1_20_15", label: "1H 1st 5", period: "H1", clockFrom: "20:00", clockTo: "15:00" },
  { id: "H1_15_10", label: "1H 2nd 5", period: "H1", clockFrom: "15:00", clockTo: "10:00" },
  { id: "H1_10_5", label: "1H 3rd 5", period: "H1", clockFrom: "10:00", clockTo: "05:00" },
  { id: "H1_5_0", label: "1H 4th 5", period: "H1", clockFrom: "05:00", clockTo: "00:00" },
  { id: "H2_20_15", label: "2H 1st 5", period: "H2", clockFrom: "20:00", clockTo: "15:00" },
  { id: "H2_15_10", label: "2H 2nd 5", period: "H2", clockFrom: "15:00", clockTo: "10:00" },
  { id: "H2_10_5", label: "2H 3rd 5", period: "H2", clockFrom: "10:00", clockTo: "05:00" },
  { id: "H2_5_0", label: "2H 4th 5", period: "H2", clockFrom: "05:00", clockTo: "00:00" },
];

export function chipMatches(
  chip: PeriodChip,
  period?: string,
  clockFrom?: string,
  clockTo?: string,
): boolean {
  if (chip.period !== period) return false;
  return (chip.clockFrom ?? undefined) === (clockFrom || undefined) && (chip.clockTo ?? undefined) === (clockTo || undefined);
}

export function windowsFromEntry(e: {
  period?: string;
  clockFrom?: string;
  clockTo?: string;
  periodWindows?: PeriodWindowSel[];
}): PeriodWindowSel[] {
  if (e.periodWindows?.length) return e.periodWindows;
  if (e.period || e.clockFrom || e.clockTo) {
    return [{ period: e.period, clockFrom: e.clockFrom, clockTo: e.clockTo }];
  }
  return [];
}

export function chipSelectedIn(chip: PeriodChip, windows: PeriodWindowSel[]): boolean {
  return windows.some((w) => chipMatches(chip, w.period, w.clockFrom, w.clockTo));
}

export function toggleWindow(windows: PeriodWindowSel[], chip: PeriodChip): PeriodWindowSel[] {
  const on = chipSelectedIn(chip, windows);
  if (on) return windows.filter((w) => !chipMatches(chip, w.period, w.clockFrom, w.clockTo));
  return [...windows, { period: chip.period, clockFrom: chip.clockFrom, clockTo: chip.clockTo }];
}

export function commitWindows(next: PeriodWindowSel[]): {
  period?: string;
  clockFrom?: string;
  clockTo?: string;
  periodWindows?: PeriodWindowSel[];
} {
  if (!next.length) {
    return { period: undefined, clockFrom: undefined, clockTo: undefined, periodWindows: undefined };
  }
  if (next.length === 1) {
    return {
      period: next[0].period,
      clockFrom: next[0].clockFrom,
      clockTo: next[0].clockTo,
      periodWindows: undefined,
    };
  }
  return { period: undefined, clockFrom: undefined, clockTo: undefined, periodWindows: next };
}

export function regulationMinutes(leagues: string[]): { game: number; ot: number } {
  if (leagues.includes("NCAAB") && !leagues.includes("NBA")) return { game: 40, ot: 5 };
  return { game: 48, ot: 5 };
}
