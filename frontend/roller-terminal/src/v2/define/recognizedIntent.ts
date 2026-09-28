/**
 * Overlay for recognized-but-unavailable human selections.
 * Never writes fake path_conditions or population bindings.
 * Spec remains the only constructible object.
 */

export type IntentFamily =
  | "sport"
  | "population"
  | "season"
  | "event"
  | "when"
  | "prior"
  | "after"
  | "terminal"
  | "search";

export type IntentClause = {
  id: string;
  family: IntentFamily;
  label: string;
  /** Always false — constructible selections live on research_spec. */
  constructible: false;
};

export type RecognizedIntent = {
  clauses: IntentClause[];
  customizeUnlocked: boolean;
  /** Display-only. Must not be written onto a locked template. */
  selectedSeason: string | null;
};

export function emptyIntent(): RecognizedIntent {
  return { clauses: [], customizeUnlocked: false, selectedSeason: null };
}

export function intentBlocksRun(intent: RecognizedIntent): boolean {
  return intent.clauses.length > 0 || Boolean(intent.selectedSeason);
}

export function upsertClause(intent: RecognizedIntent, clause: IntentClause): RecognizedIntent {
  const rest = intent.clauses.filter((c) => c.family !== clause.family || c.id !== clause.id);
  const withoutFamily = rest.filter((c) => c.family !== clause.family);
  return { ...intent, clauses: [...withoutFamily, clause] };
}

export function clearFamily(intent: RecognizedIntent, family: IntentFamily): RecognizedIntent {
  return { ...intent, clauses: intent.clauses.filter((c) => c.family !== family) };
}

export function hasClause(intent: RecognizedIntent, id: string): boolean {
  return intent.clauses.some((c) => c.id === id);
}
