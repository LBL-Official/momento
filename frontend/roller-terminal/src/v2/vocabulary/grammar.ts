/**
 * Compositional phenomenon grammar.
 *
 * SEARCH ≠ COMPILER. RECOGNIZED ≠ CONSTRUCTIBLE.
 * Families are finite. Price/ordinal parameters are not new concepts.
 */

import { GRID_CENTS, isKnownCents, normalizeSearchText } from "./normalize";
import type { ConstructibilityStatus, ParsedClause, ParsedPhenomenon } from "./types";

export const ORDINALS: Record<string, number> = {
  first: 1,
  initial: 1,
  "1st": 1,
  second: 2,
  "2nd": 2,
  third: 3,
  "3rd": 3,
  fourth: 4,
  "4th": 4,
  fifth: 5,
  "5th": 5,
  sixth: 6,
  "6th": 6,
  seventh: 7,
  "7th": 7,
  eighth: 8,
  "8th": 8,
  ninth: 9,
  "9th": 9,
  tenth: 10,
  "10th": 10,
};

export const ORDINAL_NAMES = [
  "",
  "FIRST",
  "SECOND",
  "THIRD",
  "FOURTH",
  "FIFTH",
  "SIXTH",
  "SEVENTH",
  "EIGHTH",
  "NINTH",
  "TENTH",
] as const;

const TOUCH_EVENT = "(?:touch|touches|touched|hit|hits|reach|reaches|reached|print|printed|occurrence|visit)";

const GENERIC_NOT_FILL = [
  "an executed trade / fill",
  "guaranteed available liquidity",
  "a stop-loss fill",
  "profitability or edge",
];

function centsE4(cents: number): number {
  return cents * 100;
}

function expressionOrdinal(ordinal: number, cents: number): string {
  return `${ORDINAL_NAMES[ordinal] ?? "NTH"}${cents}`;
}

export function resolveOrdinalTouch(
  ordinal: number,
  cents: number,
): Pick<
  ParsedClause,
  | "constructibility"
  | "compilerBindable"
  | "populationLocked"
  | "bindsToImplemented"
  | "whatItMeans"
  | "whatItDoesNotMean"
> {
  if (ordinal === 1 && cents === 80) {
    return {
      constructibility: "IMPLEMENTED",
      compilerBindable: true,
      populationLocked: true,
      bindsToImplemented: ["FIRST80", "FIRST_PRICE_TOUCH"],
      whatItMeans:
        "FIRST80 — first authoritative qualifying touch at 80¢ on the tradable close path (price_e4=8000).",
      whatItDoesNotMean: [
        ...GENERIC_NOT_FILL,
        "any first touch at a different price (FIRST75 / FIRST83 are not locked)",
        "terminal YES / a win",
      ],
    };
  }
  if (ordinal === 1 && cents === 83) {
    return {
      constructibility: "NOT_CONSTRUCTIBLE",
      compilerBindable: true,
      populationLocked: false,
      bindsToImplemented: ["FIRST_PRICE_TOUCH"],
      whatItMeans:
        "FIRST83 — compiler can bind FIRST_PRICE_TOUCH @ 8300. No frozen FIRST83 population in Phases 0–6.",
      whatItDoesNotMean: ["a locked FIRST80 substitute", ...GENERIC_NOT_FILL],
    };
  }
  if (ordinal === 1 && isKnownCents(cents)) {
    return {
      constructibility: "CONFIGURABLE",
      compilerBindable: true,
      populationLocked: false,
      bindsToImplemented: ["FIRST_PRICE_TOUCH"],
      whatItMeans: `FIRST_PRICE_TOUCH at ${cents}¢ (price_e4=${centsE4(cents)}). Compiler can bind an explicit price. No locked population except FIRST80.`,
      whatItDoesNotMean: [
        "a frozen FIRST80-style warehouse lock at this price",
        ...GENERIC_NOT_FILL,
      ],
    };
  }
  return {
    constructibility: "NOT_CONSTRUCTIBLE",
    compilerBindable: false,
    populationLocked: false,
    bindsToImplemented: ["ORDINAL_TOUCH"],
    whatItMeans: `${ORDINAL_NAMES[ordinal] ?? "NTH"} touch at ${cents}¢ is a recognized ordinal×level expression. No nth-touch producer exists.`,
    whatItDoesNotMean: [
      "an implemented population",
      "FIRST80 unless ordinal is first and level is 80¢",
      ...GENERIC_NOT_FILL,
    ],
  };
}

export function resolveEverOrDrop(cents: number): Pick<
  ParsedClause,
  | "constructibility"
  | "compilerBindable"
  | "populationLocked"
  | "bindsToImplemented"
  | "whatItMeans"
  | "whatItDoesNotMean"
> {
  if (cents === 40) {
    return {
      constructibility: "IMPLEMENTED",
      compilerBindable: true,
      populationLocked: false,
      bindsToImplemented: ["T40", "STOP_T40"],
      whatItMeans:
        "T40 — later tradable close ≤ 40¢ (EVER_CLOSE_LE / barrier_survival_v1). Path condition, not a fill.",
      whatItDoesNotMean: [
        "an executed stop-loss at 40¢",
        "terminal NO",
        "wick-only stop (wick is secondary)",
        "edge",
      ],
    };
  }
  return {
    constructibility: "NOT_CONSTRUCTIBLE",
    compilerBindable: false,
    populationLocked: false,
    bindsToImplemented: ["EVER_TOUCH"],
    whatItMeans: `Ever / drop-to ${cents}¢ is recognized path language. Generic barrier DSL beyond T40 is ABSENT.`,
    whatItDoesNotMean: ["an implemented T40 substitute at this level", ...GENERIC_NOT_FILL],
  };
}

export function resolveNever(cents: number | undefined): Pick<
  ParsedClause,
  | "constructibility"
  | "compilerBindable"
  | "populationLocked"
  | "bindsToImplemented"
  | "whatItMeans"
  | "whatItDoesNotMean"
> {
  if (cents === 40) {
    return {
      constructibility: "IMPLEMENTED",
      compilerBindable: true,
      populationLocked: false,
      bindsToImplemented: ["SURVIVE", "STOP_T40", "T40"],
      whatItMeans: "SURVIVE / NEVER_CLOSE_LE at 40¢. Absence of later close ≤ 40. SURVIVE ≠ TERMINAL YES.",
      whatItDoesNotMean: ["Kalshi settlement YES", "a win", "edge"],
    };
  }
  if (cents == null) {
    return {
      constructibility: "CONFIGURABLE",
      compilerBindable: true,
      populationLocked: false,
      bindsToImplemented: ["SURVIVE"],
      whatItMeans: "SURVIVE requires explicit stop_price_e4. Compiler leaves magnitude unresolved without it.",
      whatItDoesNotMean: ["terminal YES", "edge"],
    };
  }
  return {
    constructibility: "NOT_CONSTRUCTIBLE",
    compilerBindable: false,
    populationLocked: false,
    bindsToImplemented: ["SURVIVE"],
    whatItMeans: `Never-touch ${cents}¢ is recognized. Only the 40¢ barrier is an implemented path producer.`,
    whatItDoesNotMean: ["an implemented survival lock at this level", "terminal YES"],
  };
}

function resolveBounceRecover(
  kind: "BOUNCE_TO" | "RECOVER_TO",
  cents: number | undefined,
): Pick<
  ParsedClause,
  | "constructibility"
  | "compilerBindable"
  | "populationLocked"
  | "bindsToImplemented"
  | "whatItMeans"
  | "whatItDoesNotMean"
> {
  const label = kind === "BOUNCE_TO" ? "Bounce" : "Recovery";
  return {
    constructibility: "NOT_CONSTRUCTIBLE",
    compilerBindable: false,
    populationLocked: false,
    bindsToImplemented: [kind, "WHAT_HAPPENED_NEXT"],
    whatItMeans: cents
      ? `${label} to ${cents}¢ is a recognized destination family. No bounce/recovery producer is bound in Phases 0–6.`
      : `${label} without a destination is recognized direction-only language. Not constructible.`,
    whatItDoesNotMean: [
      "T40",
      "a guaranteed rebound after FIRST80",
      "edge or mean-reversion alpha",
      ...GENERIC_NOT_FILL,
    ],
  };
}

function sequenceStatus(clauses: ParsedClause[]): { status: ConstructibilityStatus; note: string } {
  if (!clauses.length) {
    return { status: "UNKNOWN", note: "No phenomenon clauses recognized." };
  }
  const ids = new Set(clauses.map((c) => c.expressionId));
  const extra = clauses.filter(
    (c) =>
      !["FIRST80", "T40", "DROP40", "EVER40", "STOP_T40", "SURVIVE", "NEVER40", "TERMINAL_YES", "TERMINAL_NO"].includes(
        c.expressionId,
      ) &&
      c.familyId !== "PERIOD" &&
      c.familyId !== "TIME_HORIZON",
  );
  const hasFirst80 = ids.has("FIRST80");
  const hasT40 = ids.has("T40") || ids.has("DROP40") || ids.has("EVER40") || ids.has("STOP_T40");
  const onlyAuthoritativePath =
    extra.length === 0 &&
    hasFirst80 &&
    clauses.every(
      (c) =>
        c.constructibility === "IMPLEMENTED" ||
        c.familyId === "PERIOD" ||
        c.familyId === "TIME_HORIZON",
    );

  if (onlyAuthoritativePath && hasFirst80 && (hasT40 || ids.has("TERMINAL_YES") || ids.has("TERMINAL_NO") || clauses.length === 1)) {
    const q3 = clauses.some((c) => c.period === "Q3" || c.expressionId === "PERIOD_Q3");
    return {
      status: "IMPLEMENTED",
      note: q3
        ? "Matches the locked FIRST80_Q3 shape (FIRST80 + optional T40 + optional terminal). Validate before RUN."
        : "FIRST80 path/terminal pairing is implemented on locked populations. Quarter slices other than Q3 are structural.",
    };
  }
  if (clauses.some((c) => c.constructibility === "NOT_CONSTRUCTIBLE")) {
    return {
      status: "NOT_CONSTRUCTIBLE",
      note: "Structure recognized. At least one clause has no authoritative producer. Not a runnable research object.",
    };
  }
  if (clauses.some((c) => c.constructibility === "REGISTERED" || c.constructibility === "CONFIGURABLE")) {
    return {
      status: "CONFIGURABLE",
      note: "Structure recognized. Remaining parameters or producers are not a locked executable route.",
    };
  }
  return {
    status: "REGISTERED",
    note: "Structure recognized. SEARCH ≠ COMPILER. Do not treat this as executed research.",
  };
}

type SpanMatch = { start: number; end: number; clause: ParsedClause };

function occupy(occupied: Array<[number, number]>, start: number, end: number): boolean {
  for (const [a, b] of occupied) {
    if (start < b && end > a) return true;
  }
  occupied.push([start, end]);
  return false;
}

function clause(
  partial: Omit<ParsedClause, "constructibility" | "compilerBindable" | "populationLocked" | "bindsToImplemented" | "whatItMeans" | "whatItDoesNotMean"> &
    Partial<
      Pick<
        ParsedClause,
        | "constructibility"
        | "compilerBindable"
        | "populationLocked"
        | "bindsToImplemented"
        | "whatItMeans"
        | "whatItDoesNotMean"
      >
    >,
  resolved?: ReturnType<typeof resolveOrdinalTouch>,
): ParsedClause {
  const r = resolved ?? {
    constructibility: partial.constructibility ?? "REGISTERED",
    compilerBindable: partial.compilerBindable ?? false,
    populationLocked: partial.populationLocked ?? false,
    bindsToImplemented: partial.bindsToImplemented ?? [],
    whatItMeans: partial.whatItMeans ?? partial.displayName,
    whatItDoesNotMean: partial.whatItDoesNotMean ?? GENERIC_NOT_FILL,
  };
  return { ...partial, ...r };
}

function parseCents(raw: string): number | undefined {
  const n = Number.parseInt(raw, 10);
  if (!Number.isFinite(n) || n < 1 || n > 99) return undefined;
  return n;
}

function collectRegex(normalized: string, re: RegExp, build: (m: RegExpExecArray) => ParsedClause | null): SpanMatch[] {
  const out: SpanMatch[] = [];
  const copy = new RegExp(re.source, re.flags.includes("g") ? re.flags : `${re.flags}g`);
  let m: RegExpExecArray | null;
  while ((m = copy.exec(normalized))) {
    const c = build(m);
    if (c) out.push({ start: m.index, end: m.index + m[0].length, clause: c });
  }
  return out;
}

export function parsePhenomenon(query: string): ParsedPhenomenon {
  const normalized = normalizeSearchText(query);
  if (!normalized) {
    return {
      query,
      normalized,
      clauses: [],
      sequence: [],
      sequenceConstructibility: "UNKNOWN",
      sequenceNote: "Empty query.",
      recognized: false,
    };
  }

  const candidates: SpanMatch[] = [];

  // Second-time return (before generic recover/return).
  candidates.push(
    ...collectRegex(
      normalized,
      /\b(?:returns|return|back)\s+to\s+(\d{1,2})(?:\s*cents?)?\s+for\s+the\s+second\s+time\b/g,
      (m) => {
        const cents = parseCents(m[1]);
        if (cents == null || !isKnownCents(cents)) return null;
        return clause(
          {
            familyId: "ORDINAL_TOUCH",
            expressionId: expressionOrdinal(2, cents),
            displayName: `SECOND${cents}`,
            ordinal: 2,
            event: "TOUCH",
            cents,
            matchedPhrase: m[0],
          },
          resolveOrdinalTouch(2, cents),
        );
      },
    ),
  );

  // Ordinal + optional event + level
  candidates.push(
    ...collectRegex(
      normalized,
      new RegExp(
        `\\b(first|initial|1st|second|2nd|third|3rd|fourth|4th|fifth|5th|sixth|6th|seventh|7th|eighth|8th|ninth|9th|tenth|10th)\\s+(?:time\\s+)?(?:the\\s+)?(?:price\\s+)?(?:${TOUCH_EVENT}\\s+)?(?:of\\s+|at\\s+|to\\s+)?(\\d{1,2})(?:\\s*cents?)?\\b`,
        "g",
      ),
      (m) => {
        const ordinal = ORDINALS[m[1]];
        const cents = parseCents(m[2]);
        if (!ordinal || cents == null || !isKnownCents(cents)) return null;
        return clause(
          {
            familyId: "ORDINAL_TOUCH",
            expressionId: expressionOrdinal(ordinal, cents),
            displayName: expressionOrdinal(ordinal, cents),
            ordinal,
            event: "TOUCH",
            cents,
            matchedPhrase: m[0],
          },
          resolveOrdinalTouch(ordinal, cents),
        );
      },
    ),
  );

  // "price first hits N" / "when it first reaches N"
  candidates.push(
    ...collectRegex(
      normalized,
      new RegExp(
        `\\b(?:when\\s+)?(?:the\\s+)?(?:it\\s+|price\\s+)?first\\s+${TOUCH_EVENT}\\s+(\\d{1,2})(?:\\s*cents?)?\\b`,
        "g",
      ),
      (m) => {
        const cents = parseCents(m[1]);
        if (cents == null || !isKnownCents(cents)) return null;
        return clause(
          {
            familyId: "ORDINAL_TOUCH",
            expressionId: expressionOrdinal(1, cents),
            displayName: expressionOrdinal(1, cents),
            ordinal: 1,
            event: "TOUCH",
            cents,
            matchedPhrase: m[0],
          },
          resolveOrdinalTouch(1, cents),
        );
      },
    ),
  );

  // Unprefixed touch/hit/reach N — event, not automatically FIRST unless 80¢ (implemented instance).
  candidates.push(
    ...collectRegex(
      normalized,
      new RegExp(`\\b${TOUCH_EVENT}\\s+(?:of\\s+|at\\s+)?(\\d{1,2})(?:\\s*cents?)?\\b`, "g"),
      (m) => {
        const cents = parseCents(m[1]);
        if (cents == null || !isKnownCents(cents)) return null;
        if (cents === 80) {
          return clause(
            {
              familyId: "ORDINAL_TOUCH",
              expressionId: "FIRST80",
              displayName: "FIRST80",
              ordinal: 1,
              event: "TOUCH",
              cents,
              matchedPhrase: m[0],
            },
            {
              ...resolveOrdinalTouch(1, 80),
              whatItMeans:
                "80¢ touch language. Ordinal was not stated; FIRST80 is the implemented 80¢ population — not proof this path is the first touch.",
            },
          );
        }
        if (cents === 40) {
          return clause(
            {
              familyId: "EVER_TOUCH",
              expressionId: "T40",
              displayName: "T40",
              event: "TOUCH",
              cents,
              matchedPhrase: m[0],
            },
            resolveEverOrDrop(40),
          );
        }
        return clause(
          {
            familyId: "ORDINAL_TOUCH",
            expressionId: `TOUCH${cents}`,
            displayName: `TOUCH ${cents}¢`,
            event: "TOUCH",
            cents,
            matchedPhrase: m[0],
          },
          {
            constructibility: "REGISTERED",
            compilerBindable: false,
            populationLocked: false,
            bindsToImplemented: ["FIRST_PRICE_TOUCH"],
            whatItMeans: `Unprefixed touch at ${cents}¢. Not FIRST80. No locked population.`,
            whatItDoesNotMean: ["FIRST80", "a fill"],
          },
        );
      },
    ),
  );

  // Compact T40 / T 40 as ever-touch (not "first")
  candidates.push(
    ...collectRegex(normalized, /\bt\s+(40|80)\b/g, (m) => {
      const cents = parseCents(m[1]);
      if (cents == null) return null;
      const r = resolveEverOrDrop(cents);
      return clause(
        {
          familyId: "EVER_TOUCH",
          expressionId: `T${cents}`,
          displayName: `T${cents}`,
          event: "EVER_TOUCH",
          cents,
          matchedPhrase: m[0],
        },
        r,
      );
    }),
  );

  candidates.push(
    ...collectRegex(
      normalized,
      /\b(?:ever|e)\s+(?:reaches|hits|touches|reach|hit|touch)?\s*(\d{1,2})(?:\s*cents?)?\b/g,
      (m) => {
        const cents = parseCents(m[1]);
        if (cents == null || !isKnownCents(cents)) return null;
        return clause(
          {
            familyId: "EVER_TOUCH",
            expressionId: cents === 40 ? "T40" : `EVER${cents}`,
            displayName: cents === 40 ? "T40" : `EVER${cents}`,
            event: "EVER_TOUCH",
            cents,
            matchedPhrase: m[0],
          },
          resolveEverOrDrop(cents),
        );
      },
    ),
  );

  candidates.push(
    ...collectRegex(
      normalized,
      /\b(?:never\s+(?:reaches|hits|touches|falls\s+to|reach|hit|touch)|does\s+not\s+hit|survives\s+above|stays\s+above|never\s+falls\s+to)\s*(\d{1,2})?(?:\s*cents?)?\b/g,
      (m) => {
        const cents = m[1] ? parseCents(m[1]) : undefined;
        const r = resolveNever(cents);
        const id = cents === 40 ? "NEVER40" : cents != null ? `NEVER${cents}` : "SURVIVE";
        return clause(
          {
            familyId: "NEVER_TOUCH",
            expressionId: id,
            displayName: id,
            event: "NEVER_TOUCH",
            cents,
            matchedPhrase: m[0],
          },
          r,
        );
      },
    ),
  );

  candidates.push(
    ...collectRegex(
      normalized,
      /\b(?:drops?|dropped|falls?|fell|declines?|sells\s+off|moves\s+down|drops\s+back|reaches\s+on\s+the\s+downside)\s+(?:to\s+|back\s+to\s+)?(\d{1,2})(?:\s*cents?)?\b/g,
      (m) => {
        const cents = parseCents(m[1]);
        if (cents == null || !isKnownCents(cents)) return null;
        const r = resolveEverOrDrop(cents);
        return clause(
          {
            familyId: "DROP_TO",
            expressionId: cents === 40 ? "T40" : `DROP${cents}`,
            displayName: cents === 40 ? "DROP40 → T40" : `DROP${cents}`,
            direction: "DOWN",
            event: "DROP",
            cents,
            matchedPhrase: m[0],
          },
          r,
        );
      },
    ),
  );

  candidates.push(
    ...collectRegex(
      normalized,
      /\b(?:bounces?|rebounds?|rallies|rally)\s+(?:to\s+|back\s+to\s+)?(\d{1,2})(?:\s*cents?)?\b/g,
      (m) => {
        const cents = parseCents(m[1]);
        if (cents == null || !isKnownCents(cents)) return null;
        return clause(
          {
            familyId: "BOUNCE_TO",
            expressionId: `BOUNCE${cents}`,
            displayName: `BOUNCE${cents}`,
            direction: "UP",
            event: "BOUNCE",
            cents,
            matchedPhrase: m[0],
          },
          resolveBounceRecover("BOUNCE_TO", cents),
        );
      },
    ),
  );

  candidates.push(
    ...collectRegex(
      normalized,
      /\b(?:recovers?|claws\s+back|gets\s+back|moves\s+back|regains?|climbs\s+back|returns)\s+(?:to\s+|back\s+to\s+)?(\d{1,2})(?:\s*cents?)?\b/g,
      (m) => {
        const cents = parseCents(m[1]);
        if (cents == null || !isKnownCents(cents)) return null;
        return clause(
          {
            familyId: "RECOVER_TO",
            expressionId: `RECOVER${cents}`,
            displayName: `RECOVER${cents}`,
            direction: "UP",
            event: "RECOVER",
            cents,
            matchedPhrase: m[0],
          },
          resolveBounceRecover("RECOVER_TO", cents),
        );
      },
    ),
  );

  candidates.push(
    ...collectRegex(
      normalized,
      /\b(?:crosses|breaks|breaches|gets\s+through|falls\s+through|loses)\s+(?:above|below|from\s+below|from\s+above)?\s*(\d{1,2})(?:\s*cents?)?\b/g,
      (m) => {
        const cents = parseCents(m[1]);
        if (cents == null || !isKnownCents(cents)) return null;
        const phrase = m[0];
        const down = /below|from above|falls through|loses/.test(phrase);
        return clause({
          familyId: "CROSS",
          expressionId: `CROSS${down ? "DOWN" : "UP"}${cents}`,
          displayName: `CROSS ${down ? "DOWN" : "UP"} ${cents}¢`,
          direction: down ? "DOWN" : "UP",
          event: "CROSS",
          cents,
          matchedPhrase: phrase,
          constructibility: "NOT_CONSTRUCTIBLE",
          compilerBindable: false,
          populationLocked: false,
          bindsToImplemented: ["CROSS", "FIRST_PRICE_TOUCH"],
          whatItMeans: `Directional cross at ${cents}¢. TOUCH ≠ CROSS ≠ STATE. No distinct cross producer is bound.`,
          whatItDoesNotMean: ["FIRST80 unless this is a first 80¢ touch", "a fill", "edge"],
        });
      },
    ),
  );

  candidates.push(
    ...collectRegex(
      normalized,
      /\b(above|below|over|under|at\s+least|no\s+more\s+than|greater\s+than|less\s+than)\s+(\d{1,2})(?:\s*cents?)?\b/g,
      (m) => {
        const cents = parseCents(m[2]);
        if (cents == null || !isKnownCents(cents)) return null;
        const relRaw = m[1].replace(/\s+/g, "_");
        const down = /below|under|no_more|less/.test(relRaw);
        const relation = /at_least|greater/.test(relRaw) ? "GE" : /no_more|less/.test(relRaw) ? "LE" : down ? "BELOW" : "ABOVE";
        return clause({
          familyId: "PRICE_STATE",
          expressionId: `STATE_${relation}${cents}`,
          displayName: `${relation} ${cents}¢`,
          relation,
          cents,
          matchedPhrase: m[0],
          constructibility: "NOT_CONSTRUCTIBLE",
          compilerBindable: false,
          populationLocked: false,
          bindsToImplemented: ["PRICE_STATE"],
          whatItMeans: `State condition ${relation} ${cents}¢. A state is not a touch event.`,
          whatItDoesNotMean: ["FIRST80 / a touch", "a cross", "T40 unless this is ever-close ≤ 40"],
        });
      },
    ),
  );

  // Bare "forty cent barrier" / "80 cent threshold" after other matches
  candidates.push(
    ...collectRegex(
      normalized,
      /\b(\d{1,2})\s*(?:cents?)?\s*(?:barrier|threshold|level)\b/g,
      (m) => {
        const cents = parseCents(m[1]);
        if (cents == null || !isKnownCents(cents)) return null;
        if (cents === 40) {
          return clause(
            {
              familyId: "EVER_TOUCH",
              expressionId: "T40",
              displayName: "T40",
              cents,
              event: "EVER_TOUCH",
              matchedPhrase: m[0],
            },
            resolveEverOrDrop(40),
          );
        }
        if (cents === 80) {
          return clause(
            {
              familyId: "ORDINAL_TOUCH",
              expressionId: "FIRST80",
              displayName: "FIRST80",
              ordinal: 1,
              cents,
              event: "TOUCH",
              matchedPhrase: m[0],
            },
            resolveOrdinalTouch(1, 80),
          );
        }
        return clause({
          familyId: "ORDINAL_TOUCH",
          expressionId: `LEVEL${cents}`,
          displayName: `${cents}¢ level`,
          cents,
          matchedPhrase: m[0],
          constructibility: "REGISTERED",
          compilerBindable: false,
          populationLocked: false,
          bindsToImplemented: ["PRICE_E4"],
          whatItMeans: `${cents}¢ is a recognized 5¢-grid price level (price_e4=${centsE4(cents)}). Not a population.`,
          whatItDoesNotMean: ["80% implied probability", "a locked FIRST/T population at this level"],
        });
      },
    ),
  );

  // Periods
  const periods: Array<[RegExp, string]> = [
    [/\b(?:q\s*1|first\s+quarter|1st\s+quarter|quarter\s+1)\b/g, "Q1"],
    [/\b(?:q\s*2|second\s+quarter|2nd\s+quarter|quarter\s+2)\b/g, "Q2"],
    [/\b(?:q\s*3|third\s+quarter|3rd\s+quarter|quarter\s+3)\b/g, "Q3"],
    [/\b(?:q\s*4|fourth\s+quarter|4th\s+quarter|quarter\s+4)\b/g, "Q4"],
    [/\bh\s*1\s*2\b/g, "H1_2"],
    [/\bh\s*2\s*1\b/g, "H2_1"],
    [/\bh\s*1\s*1\b/g, "H1_1"],
    [/\bh\s*2\s*2\b/g, "H2_2"],
  ];
  for (const [re, value] of periods) {
    candidates.push(
      ...collectRegex(normalized, re, (m) =>
        clause({
          familyId: "PERIOD",
          expressionId: value.startsWith("H") ? `NCAAB_${value}` : `PERIOD_${value}`,
          displayName: value,
          period: value,
          matchedPhrase: m[0],
          constructibility: value === "Q3" || value === "H1_2" || value === "H2_1" ? "IMPLEMENTED" : "CONFIGURABLE",
          compilerBindable: ["Q1", "Q2", "Q3", "Q4", "H1_2", "H2_1"].includes(value),
          populationLocked: value === "Q3",
          bindsToImplemented: [value.startsWith("H") ? `NCAAB_${value}` : `PERIOD_${value}`],
          whatItMeans: `${value} is an authoritative clock / entry_slice value. Q4 ≠ late game.`,
          whatItDoesNotMean: ["late game", "a runnable filter unless bound on a population"],
        }),
      ),
    );
  }

  candidates.push(
    ...collectRegex(
      normalized,
      /\b(?:settles?|settled|resolved|expired|kalshi)\s+(yes|no)\b|\bterminal\s+(yes|no)\b|\b(won|wins|lost|loses)\b|\bw\b/g,
      (m) => {
        const word = (m[1] || m[2] || m[3] || "yes").toLowerCase();
        const yn = word === "no" || word === "lost" || word === "loses" ? "NO" : "YES";
        return clause({
          familyId: "TERMINAL",
          expressionId: yn === "YES" ? "TERMINAL_YES" : "TERMINAL_NO",
          displayName: yn === "YES" ? "TERMINAL YES (W)" : "TERMINAL NO",
          terminal: yn,
          matchedPhrase: m[0],
          constructibility: "IMPLEMENTED",
          compilerBindable: true,
          populationLocked: false,
          bindsToImplemented: [yn === "YES" ? "TERMINAL_YES" : "TERMINAL_NO"],
          whatItMeans: `Kalshi settlement ${yn}. W means terminal YES — not box-score win.`,
          whatItDoesNotMean: ["SURVIVE / ¬T40", "home/away box score", "edge"],
        });
      },
    ),
  );

  candidates.push(
    ...collectRegex(
      normalized,
      /\bwithin\s+(\d{1,2})\s+minutes?\b|\b(one|five|ten)\s+minutes?\s+later\b/g,
      (m) => {
        const named: Record<string, number> = { one: 1, five: 5, ten: 10 };
        const mins = m[1] ? Number.parseInt(m[1], 10) : named[m[2] ?? ""] ?? 0;
        return clause({
          familyId: "TIME_HORIZON",
          expressionId: `HORIZON_${mins}M`,
          displayName: `${mins}m horizon`,
          horizonMinutes: mins,
          matchedPhrase: m[0],
          constructibility: "NOT_CONSTRUCTIBLE",
          compilerBindable: false,
          populationLocked: false,
          bindsToImplemented: ["TIME_HORIZON"],
          whatItMeans: `Time-to-event horizon ${mins}m. No authoritative intra-event duration producer is bound.`,
          whatItDoesNotMean: ["CLOCK_REMAINING (period clock)", "an implemented path timer"],
        });
      },
    ),
  );

  // Direction-only reversals when no destination already claimed
  candidates.push(
    ...collectRegex(
      normalized,
      /\b(?:reverts?\s+up|moves\s+back\s+up|mean\s+reverts?\s+upward|reverts?\s+higher|returns\s+upward)\b/g,
      (m) =>
        clause({
          familyId: "REVERSAL",
          expressionId: "REVERSAL_UP",
          displayName: "REVERSAL UP",
          direction: "UP",
          matchedPhrase: m[0],
          constructibility: "NOT_CONSTRUCTIBLE",
          compilerBindable: false,
          populationLocked: false,
          bindsToImplemented: ["REVERSAL"],
          whatItMeans: "Upward reversion family. Direction without destination. Not a producer.",
          whatItDoesNotMean: ["edge", "mean-reversion alpha", "RECOVER80"],
        }),
    ),
  );
  candidates.push(
    ...collectRegex(
      normalized,
      /\b(?:reverts?\s+down|moves\s+back\s+down|falls\s+back|drops\s+back|reverses?\s+lower|mean\s+reverts?\s+downward|retraces?\s+lower|returns\s+downward)\b/g,
      (m) =>
        clause({
          familyId: "REVERSAL",
          expressionId: "REVERSAL_DOWN",
          displayName: "REVERSAL DOWN",
          direction: "DOWN",
          matchedPhrase: m[0],
          constructibility: "NOT_CONSTRUCTIBLE",
          compilerBindable: false,
          populationLocked: false,
          bindsToImplemented: ["REVERSAL"],
          whatItMeans: "Downward reversion family. Direction without destination. Not a producer.",
          whatItDoesNotMean: ["T40 unless a 40¢ destination is stated", "edge"],
        }),
    ),
  );

  candidates.sort((a, b) => b.end - b.start - (a.end - a.start) || a.start - b.start);
  const occupied: Array<[number, number]> = [];
  const chosen: SpanMatch[] = [];
  for (const c of candidates) {
    if (occupy(occupied, c.start, c.end)) continue;
    chosen.push(c);
  }
  chosen.sort((a, b) => a.start - b.start);

  const clauses: ParsedClause[] = [];
  const seen = new Set<string>();
  for (const c of chosen) {
    if (seen.has(c.clause.expressionId)) continue;
    seen.add(c.clause.expressionId);
    clauses.push(c.clause);
  }

  const seq = sequenceStatus(clauses);
  return {
    query,
    normalized,
    clauses,
    sequence: clauses.map((c) => c.expressionId),
    sequenceConstructibility: seq.status,
    sequenceNote: seq.note,
    recognized: clauses.length > 0,
  };
}

export function listGridLevels(): number[] {
  return [...GRID_CENTS];
}

export function compilerFirstTouchPattern(normalized: string): boolean {
  return (
    /\bfirst(?:\s+time)?(?:\s+the)?\s+price\s+(?:hits|hit|touches|touch|reaches|reached|reach|printed)\b/.test(
      normalized,
    ) ||
    /\bfirst\s+price\s+(?:touch|touches|hit|hits|reach|reaches)\b/.test(normalized) ||
    /\b(?:when\s+)?(?:the\s+)?price\s+first\s+(?:hits|hit|touches|touch|reaches|reached|reach)\b/.test(
      normalized,
    )
  );
}
