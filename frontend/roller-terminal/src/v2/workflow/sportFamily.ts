/**
 * Sport-family helpers. Clicking Baseball/MLB, Tennis/ATP/WTA, or NBA/NCAAB switches family
 * in memory — no location.reload().
 */

import type { TeFilters } from "./types";

export const FAMILY_BASKETBALL = "basketball";
export const FAMILY_BASEBALL = "baseball";
export const FAMILY_TENNIS = "tennis";

const BASKETBALL_SPORTS = new Set(["basketball", "NBA", "WNBA", "NCAAB"]);
const BASEBALL_SPORTS = new Set(["baseball", "MLB"]);
const TENNIS_SPORTS = new Set(["tennis", "ATP", "WTA"]);
const BASKETBALL_PERIOD = /^(Q|H|OT|P5)/;
const BASEBALL_PERIOD = /^(T|B|I)\d|^T[BX]$|^B[BX]$/;
const TENNIS_PERIOD = /^S[1-5]$|^G\d|^G10\+$/;

export type SportFamily =
  | typeof FAMILY_BASKETBALL
  | typeof FAMILY_BASEBALL
  | typeof FAMILY_TENNIS
  | "unknown";

export type FamilyUniverse = {
  sports: string[];
  leagues: string[];
  seasons: string[];
  dateFrom?: string;
  dateTo?: string;
  markets: string[];
  marketData: string[];
  dataSources: string[];
};

export type Periodish = {
  period?: string;
  clockFrom?: string;
  clockTo?: string;
  periodWindows?: Array<{ period?: string; clockFrom?: string; clockTo?: string }>;
  gameFrom?: number;
  gameTo?: number;
};

export function familyOf(id: string): SportFamily {
  if (BASKETBALL_SPORTS.has(id)) return FAMILY_BASKETBALL;
  if (BASEBALL_SPORTS.has(id)) return FAMILY_BASEBALL;
  if (TENNIS_SPORTS.has(id)) return FAMILY_TENNIS;
  return "unknown";
}

export function isBasketballFamily(universe: { sports: string[]; leagues: string[] }): boolean {
  return [...universe.sports, ...universe.leagues].some((x) => familyOf(x) === FAMILY_BASKETBALL);
}

export function isBaseballFamily(universe: { sports: string[]; leagues: string[] }): boolean {
  return [...universe.sports, ...universe.leagues].some((x) => familyOf(x) === FAMILY_BASEBALL);
}

export function isTennisFamily(universe: { sports: string[]; leagues: string[] }): boolean {
  return [...universe.sports, ...universe.leagues].some((x) => familyOf(x) === FAMILY_TENNIS);
}

export function mixedClockFamilies(universe: { sports: string[]; leagues: string[] }): boolean {
  const fams = new Set(
    [...universe.sports, ...universe.leagues].map(familyOf).filter((f) => f !== "unknown"),
  );
  return fams.size > 1;
}

function isBasketballPeriod(period?: string): boolean {
  return Boolean(period && BASKETBALL_PERIOD.test(period));
}

function isBaseballPeriod(period?: string): boolean {
  return Boolean(period && BASEBALL_PERIOD.test(period));
}

function isTennisPeriod(period?: string): boolean {
  return Boolean(period && TENNIS_PERIOD.test(period));
}

function periodIncompatibleWithFamily(period?: string, nextFamily?: SportFamily): boolean {
  if (!period) return false;
  if (nextFamily === FAMILY_BASKETBALL) {
    return isBaseballPeriod(period) || isTennisPeriod(period);
  }
  if (nextFamily === FAMILY_BASEBALL) {
    return isBasketballPeriod(period) || isTennisPeriod(period);
  }
  if (nextFamily === FAMILY_TENNIS) {
    return isBasketballPeriod(period) || isBaseballPeriod(period);
  }
  return false;
}

/** Drop period windows from other families when switching. Keep price / touch / exit chips. */
export function clearIncompatiblePeriods<T extends Periodish>(
  entry: T,
  nextFamily: SportFamily,
): T {
  const drop = (period?: string) => periodIncompatibleWithFamily(period, nextFamily);
  const windows = (entry.periodWindows ?? []).filter((w) => !drop(w.period));
  const tennisGameRange =
    nextFamily === FAMILY_TENNIS ? entry : { gameFrom: undefined, gameTo: undefined };
  const clockStripped = drop(entry.period) || nextFamily === FAMILY_TENNIS;
  return {
    ...entry,
    ...tennisGameRange,
    period: drop(entry.period) ? undefined : entry.period,
    clockFrom: drop(entry.period) || clockStripped ? undefined : entry.clockFrom,
    clockTo: drop(entry.period) || clockStripped ? undefined : entry.clockTo,
    periodWindows: windows.length ? windows : undefined,
  };
}

/** Strip tennis-only TE state when leaving tennis; strip basketball/MLB TE when entering tennis. */
export function clearIncompatibleTeState(
  te: TeFilters | undefined,
  nextFamily: SportFamily,
): TeFilters | undefined {
  if (!te) return te;
  const base: TeFilters = { ...te };
  if (nextFamily !== FAMILY_TENNIS) {
    delete base.tennisPointScores;
    delete base.tennisServe;
    delete base.tennisEventStates;
    delete base.tennisSetLead;
    delete base.tennisGameLead;
    delete base.tennisPointLead;
  }
  if (nextFamily === FAMILY_TENNIS) {
    delete base.half;
    delete base.yesBatting;
    delete base.outs;
    delete base.count;
    delete base.runners;
  }
  if (nextFamily !== FAMILY_BASEBALL) {
    delete base.yesBatting;
    delete base.outs;
    delete base.count;
    delete base.runners;
  }
  return base;
}

export function selectSportFamily(universe: FamilyUniverse, id: string): FamilyUniverse {
  const fam = familyOf(id);
  if (fam === FAMILY_BASEBALL) {
    return {
      ...universe,
      sports: ["baseball"],
      leagues: ["MLB"],
      // MLB desk default is TRADABLE_YES_BID (same as NBA). Last-trade remains selectable.
      marketData: ["candles"],
    };
  }
  if (fam === FAMILY_TENNIS) {
    const sports = ["tennis"];
    let leagues = universe.leagues.filter((l) => familyOf(l) === FAMILY_TENNIS);
    if (id === "ATP" || id === "WTA") {
      leagues =
        leagues.includes(id) && universe.sports.includes("tennis")
          ? leagues.filter((l) => l !== id)
          : [...leagues.filter((l) => l !== id), id];
    }
    if (id === "tennis" && !leagues.length) {
      leagues = ["ATP", "WTA"];
    }
    return {
      ...universe,
      sports,
      leagues: leagues.length ? leagues : ["ATP", "WTA"],
      // Tennis native candles carry yes_bid — not MLB last_trade default.
      marketData: ["candles"],
    };
  }
  if (fam === FAMILY_BASKETBALL) {
    const sports = ["basketball"];
    let leagues = universe.leagues.filter((l) => familyOf(l) === FAMILY_BASKETBALL);
    if (id === "NBA" || id === "NCAAB" || id === "WNBA") {
      leagues =
        leagues.includes(id) && universe.sports.includes("basketball")
          ? leagues.filter((l) => l !== id)
          : [...leagues.filter((l) => l !== id), id];
    }
    if (id === "basketball" && !leagues.length) {
      leagues = universe.leagues.filter((l) => familyOf(l) === FAMILY_BASKETBALL);
    }
    const md = universe.marketData;
    const marketData =
      !md.length || (md.length === 1 && md[0] === "last_trade") ? ["candles"] : md;
    return {
      ...universe,
      sports,
      leagues,
      marketData,
    };
  }
  return universe;
}
