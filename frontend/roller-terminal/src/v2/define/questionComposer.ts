/**
 * Human question from research_spec + recognizedIntent overlay.
 * Never invents a third research-object model. Never rewrites SECOND80 to FIRST80.
 */

import { asObj, type Spec } from "../../researchTypes";
import { lockedTemplateKind } from "./defineCatalog";
import { hasClause, type RecognizedIntent } from "./recognizedIntent";

export function composeQuestion(spec: Spec, intent: RecognizedIntent): string {
  const lock = lockedTemplateKind(spec);
  const leagues = Array.isArray(asObj(spec.population_binding).leagues)
    ? (asObj(spec.population_binding).leagues as string[])
    : [];

  const sport = hasClause(intent, "wnba")
    ? "WNBA"
    : lock === "NCAAB_FIRST80_P5" || leagues.includes("NCAAB")
      ? "NCAAB"
      : lock === "FIRST80_Q3" || leagues.includes("NBA")
        ? "NBA"
        : leagues[0] || null;

  const population = overlayOrLockPopulation(spec, intent, lock);
  const when = overlayOrLockWhen(intent, lock);
  const prior = priorPhrase(intent);
  const after = afterPhrase(intent, lock);
  const terminal = "Kalshi YES and NO rates";
  const season = intent.selectedSeason
    ? `season ${intent.selectedSeason} (requested — not applied)`
    : lock
      ? "the frozen membership ledger"
      : null;

  const bits = [
    sport,
    population,
    when,
    season,
    prior,
    after ? `afterward ${after}` : null,
    terminal,
  ].filter(Boolean);

  let text: string;
  if (!population && !intent.clauses.length && !lock) {
    text = "No research question yet. Start with FIRST80 · Q3 or NCAAB FIRST80 · P5, or explore a question.";
  } else {
    text = `In ${bits.slice(0, -1).join(", ")}, what are the ${terminal}?`;
  }

  if (intent.clauses.length || intent.selectedSeason) {
    const labels = [
      ...intent.clauses.map((c) => c.label),
      intent.selectedSeason ? `season ${intent.selectedSeason}` : null,
    ].filter(Boolean);
    text += ` Recognized but not constructible: ${labels.join(", ")}. Roller does not rewrite this to a nearby runnable lock.`;
  }

  return text;
}

function overlayOrLockPopulation(
  spec: Spec,
  intent: RecognizedIntent,
  lock: ReturnType<typeof lockedTemplateKind>,
): string | null {
  if (hasClause(intent, "SECOND80")) return "SECOND80";
  if (hasClause(intent, "NTH80")) return "NTH80";
  if (hasClause(intent, "SECOND75")) return "SECOND75";
  if (hasClause(intent, "FIRST75")) return "FIRST75";
  if (hasClause(intent, "FIRST83")) return "FIRST83";
  if (lock === "FIRST80_Q3") return "FIRST80 · Q3";
  if (lock === "NCAAB_FIRST80_P5") return "NCAAB FIRST80 · P5";
  const name = String(asObj(spec.identity).name || "").trim();
  return name || null;
}

function overlayOrLockWhen(
  intent: RecognizedIntent,
  lock: ReturnType<typeof lockedTemplateKind>,
): string | null {
  if (hasClause(intent, "Q1")) return "Q1";
  if (hasClause(intent, "Q4")) return "Q4";
  if (hasClause(intent, "OT")) return "OT";
  if (lock === "FIRST80_Q3") return "Q3";
  if (lock === "NCAAB_FIRST80_P5") return "P5";
  return null;
}

function priorPhrase(intent: RecognizedIntent): string | null {
  if (hasClause(intent, "reversion")) return "prior reversion";
  if (hasClause(intent, "drop10")) return "prior 10¢ down";
  return null;
}

function afterPhrase(
  intent: RecognizedIntent,
  lock: ReturnType<typeof lockedTemplateKind>,
): string | null {
  if (hasClause(intent, "bounce")) return "bounce";
  if (hasClause(intent, "recover")) return "recover";
  if (hasClause(intent, "rebound15")) return "15¢ rebound";
  if (lock) return "T40";
  return null;
}

export function canOfferValidate(spec: Spec): boolean {
  return lockedTemplateKind(spec) != null || Boolean(String(asObj(spec.identity).name || "").trim());
}
