/**
 * Actual season windows for date autofill.
 * 2025–26 bounds come from warehouse games.game_date min/max.
 * Missing warehouse seasons use the published sport calendar, not a guess
 * from the UI label.
 */

export type SeasonBound = {
  from: string;
  to: string;
  source: string;
};

const NBA: Record<string, SeasonBound> = {
  "2023-24": { from: "2023-10-05", to: "2024-06-17", source: "NBA 2023–24 preseason through Finals" },
  "2024-25": { from: "2024-10-04", to: "2025-06-22", source: "NBA 2024–25 preseason through Finals" },
  "2025-26": { from: "2025-10-10", to: "2026-06-13", source: "warehouse NBA 2025-2026 games.game_date min/max" },
  "2026-27": { from: "2026-10-06", to: "2027-06-20", source: "NBA 2026–27 published calendar window" },
};

const NCAAB: Record<string, SeasonBound> = {
  "2023-24": { from: "2023-11-06", to: "2024-04-08", source: "NCAA 2023–24 opening through championship" },
  "2024-25": { from: "2024-11-04", to: "2025-04-07", source: "NCAA 2024–25 opening through championship" },
  "2025-26": { from: "2025-11-03", to: "2026-04-04", source: "warehouse NCAAB 2025-2026 games.game_date min/max" },
  "2026-27": { from: "2026-11-03", to: "2027-04-06", source: "NCAA 2026–27 published calendar window" },
};

const MLB: Record<string, SeasonBound> = {
  "2025-26": { from: "2025-03-18", to: "2026-09-04", source: "warehouse MLB 2025-2026 games.game_date min/max" },
  "2025-2026": { from: "2025-03-18", to: "2026-09-04", source: "warehouse MLB 2025-2026 games.game_date min/max" },
};

const TENNIS: Record<string, SeasonBound> = {
  "2025-26": {
    from: "2025-06-18",
    to: "2026-09-12",
    source: "Kalshi tennis universe window (ATP+WTA match-winner)",
  },
};

const BY_LEAGUE: Record<string, Record<string, SeasonBound>> = {
  NBA,
  NCAAB,
  MLB,
  ATP: TENNIS,
  WTA: TENNIS,
  WNBA: {
    "2025": { from: "2025-05-16", to: "2025-10-10", source: "WNBA 2025 regular season through Finals" },
  },
};

function normalizeSeasonId(id: string): string {
  const m = id.match(/^(\d{4})-(\d{2,4})$/);
  if (!m) return id;
  const end = m[2].length === 4 ? m[2].slice(2) : m[2];
  return `${m[1]}-${end}`;
}

export function boundsForSeason(league: string, seasonId: string): SeasonBound | undefined {
  const table = BY_LEAGUE[league];
  if (!table) return undefined;
  return table[seasonId] ?? table[normalizeSeasonId(seasonId)];
}

/** Union of selected sport/league season calendars. Earliest start → latest end. */
export function dateRangeForSelections(leagues: string[], seasons: string[]): {
  dateFrom?: string;
  dateTo?: string;
  source?: string;
} {
  if (!seasons.length) return {};
  const useLeagues = leagues.length ? leagues : Object.keys(BY_LEAGUE);
  const hits: SeasonBound[] = [];
  for (const league of useLeagues) {
    for (const season of seasons) {
      const b = boundsForSeason(league, season);
      if (b) hits.push(b);
    }
  }
  if (!hits.length) return {};
  const dateFrom = hits.map((h) => h.from).sort()[0];
  const dateTo = hits.map((h) => h.to).sort().at(-1);
  return {
    dateFrom,
    dateTo,
    source: hits.map((h) => h.source).join("; "),
  };
}
