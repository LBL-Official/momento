/** Deterministic search normalization. No LLM. No fuzzy semantics.
 *  80¢ / 80c / eighty / 0.80 → 80 cents.
 *  80% stays "80 percent" — never auto-collapsed into 80¢.
 */

export const GRID_CENTS = [
  5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95,
] as const;

export const SPECIAL_CENTS = [83] as const;

const NUMBER_WORDS: Array<[RegExp, string]> = [
  [/\bninety[\s-]+five\b/g, "95"],
  [/\bninety\b/g, "90"],
  [/\beighty[\s-]+five\b/g, "85"],
  [/\beighty[\s-]+three\b/g, "83"],
  [/\beighty\b/g, "80"],
  [/\bseventy[\s-]+five\b/g, "75"],
  [/\bseventy\b/g, "70"],
  [/\bsixty[\s-]+five\b/g, "65"],
  [/\bsixty\b/g, "60"],
  [/\bfifty[\s-]+five\b/g, "55"],
  [/\bfifty\b/g, "50"],
  [/\bforty[\s-]+five\b/g, "45"],
  [/\bforty\b/g, "40"],
  [/\bthirty[\s-]+five\b/g, "35"],
  [/\bthirty\b/g, "30"],
  [/\btwenty[\s-]+five\b/g, "25"],
  [/\btwenty\b/g, "20"],
  [/\bfifteen\b/g, "15"],
  [/\bten\b/g, "10"],
  [/\bfive\b/g, "5"],
];

export function isKnownCents(n: number): boolean {
  return (GRID_CENTS as readonly number[]).includes(n) || (SPECIAL_CENTS as readonly number[]).includes(n);
}

function decimalToCents(frac: string): string {
  const n = Number.parseInt(frac, 10);
  return isKnownCents(n) ? `${n} cents` : `.${frac}`;
}

/** Split letter-digit boundaries: first80 → first 80, t40 → t 40, q3 → q 3. */
export function splitAlphaNum(s: string): string {
  return s.replace(/([a-z])(\d)/gi, "$1 $2").replace(/(\d)([a-z])/gi, "$1 $2");
}

export function normalizeSearchText(input: string): string {
  let s = (input ?? "").normalize("NFKC").trim().toLowerCase();
  s = s.replace(/%/g, " percent ");
  s = s.replace(/¢/g, " cents ");
  s = s.replace(/\b(\d{1,2})\s*c\b/g, "$1 cents");
  s = s.replace(/\b0\.(\d{2})\b/g, (_m, frac: string) => decimalToCents(frac));
  s = s.replace(/(?<!\d)\.(\d{2})\b/g, (_m, frac: string) => decimalToCents(frac));
  s = s.replace(/[—–−]/g, " ");
  s = s.replace(/[_/\\]+/g, " ");
  s = s.replace(/[-]+/g, " ");
  s = s.replace(/[^\w\s.]/g, " ");
  for (const [re, repl] of NUMBER_WORDS) {
    s = s.replace(re, repl);
  }
  s = splitAlphaNum(s);
  s = s.replace(/\s+/g, " ").trim();
  return s;
}

export function compactText(normalized: string): string {
  return normalized.replace(/\s+/g, "");
}

export function tokensOf(normalized: string): string[] {
  return normalized.split(/\s+/).filter(Boolean);
}

export function phraseBoundaryMatch(haystack: string, needle: string): boolean {
  if (!needle) return false;
  if (haystack === needle) return true;
  const re = new RegExp(`(?:^|\\s)${escapeRegExp(needle)}(?:\\s|$)`);
  return re.test(haystack);
}

export function escapeRegExp(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

export function morphologicalForms(phrase: string): string[] {
  const raw = phrase.trim();
  if (!raw) return [];
  const forms = new Set<string>();
  const lower = raw.toLowerCase();
  forms.add(raw);
  forms.add(lower);
  const parts = lower.split(/[\s\-_]+/).filter(Boolean);
  if (parts.length > 1) {
    forms.add(parts.join(" "));
    forms.add(parts.join("-"));
    forms.add(parts.join("_"));
    forms.add(parts.join(""));
  } else if (parts.length === 1) {
    forms.add(parts[0]);
    const split = splitAlphaNum(parts[0]).replace(/\s+/g, " ").trim();
    if (split !== parts[0]) forms.add(split);
  }
  return [...forms];
}

export function priceNotationForms(cents: number): string[] {
  return [
    `${cents}`,
    `${cents}c`,
    `${cents}¢`,
    `${cents} cents`,
    `${cents} cent`,
    `${cents}-cent`,
    `${cents}cents`,
    `0.${String(cents).padStart(2, "0")}`,
    `.${String(cents).padStart(2, "0")}`,
  ];
}
