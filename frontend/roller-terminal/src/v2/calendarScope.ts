/**
 * Season / month / week universe options for Lab + Builder.
 * Values are written onto population_binding; Phase 0–6 locked routes do not
 * apply calendar filters to membership (FIRST80 / NCAAB stay frozen).
 */

export const SEASONS_BY_LEAGUE: Record<string, string[]> = {
  NBA: ["2025-2026", "2026-2027"],
  WNBA: ["2025", "2026"],
  NCAAB: ["2025-2026", "2026-2027"],
};

/** Months spanned by a warehouse season key for chip generation. */
export function monthsForSeason(season: string, leagueHint?: string): string[] {
  // WNBA single-year seasons
  if (/^\d{4}$/.test(season)) {
    const y = Number(season);
    return ["05", "06", "07", "08", "09", "10"].map((m) => `${y}-${m}`);
  }
  // NBA / NCAAB style YYYY-YYYY
  const m = /^(\d{4})-(\d{4})$/.exec(season);
  if (!m) return [];
  const y0 = Number(m[1]);
  const y1 = Number(m[2]);
  const out: string[] = [];
  for (const mm of ["10", "11", "12"]) out.push(`${y0}-${mm}`);
  for (const mm of ["01", "02", "03", "04", "05", "06"]) out.push(`${y1}-${mm}`);
  void leagueHint;
  return out;
}

function isoWeekString(d: Date): string {
  // ISO week date (UTC)
  const date = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()));
  const day = date.getUTCDay() || 7;
  date.setUTCDate(date.getUTCDate() + 4 - day);
  const yearStart = new Date(Date.UTC(date.getUTCFullYear(), 0, 1));
  const week = Math.ceil(((date.getTime() - yearStart.getTime()) / 86400000 + 1) / 7);
  return `${date.getUTCFullYear()}-W${String(week).padStart(2, "0")}`;
}

/** ISO weeks that intersect the given YYYY-MM months. */
export function weeksForMonths(months: string[]): string[] {
  const weeks = new Set<string>();
  for (const ym of months) {
    const m = /^(\d{4})-(\d{2})$/.exec(ym);
    if (!m) continue;
    const y = Number(m[1]);
    const mo = Number(m[2]) - 1;
    const start = new Date(Date.UTC(y, mo, 1));
    const end = new Date(Date.UTC(y, mo + 1, 0));
    for (let t = start.getTime(); t <= end.getTime(); t += 7 * 86400000) {
      weeks.add(isoWeekString(new Date(t)));
    }
    weeks.add(isoWeekString(end));
  }
  return [...weeks].sort();
}

export function availableSeasons(leagues: string[]): string[] {
  const out = new Set<string>();
  const list = leagues.length ? leagues : Object.keys(SEASONS_BY_LEAGUE);
  for (const league of list) {
    for (const s of SEASONS_BY_LEAGUE[league] || []) out.add(s);
  }
  return [...out].sort();
}

export function availableMonths(seasons: string[], leagues: string[]): string[] {
  const out = new Set<string>();
  const league = leagues[0];
  for (const s of seasons) {
    for (const m of monthsForSeason(s, league)) out.add(m);
  }
  return [...out].sort();
}

export function toggleInList(list: string[], value: string): string[] {
  return list.includes(value) ? list.filter((x) => x !== value) : [...list, value].sort();
}

export function hasCalendarScope(pop: Record<string, unknown>): boolean {
  return (
    (Array.isArray(pop.seasons) && pop.seasons.length > 0) ||
    (Array.isArray(pop.season_months) && pop.season_months.length > 0) ||
    (Array.isArray(pop.season_weeks) && pop.season_weeks.length > 0)
  );
}
