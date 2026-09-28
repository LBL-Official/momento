/** Discoverability types. SEARCH ≠ COMPILER. ALIAS ≠ NEW CAPABILITY. */

export type ConstructibilityStatus =
  | "IMPLEMENTED"
  | "CONFIGURABLE"
  | "REGISTERED"
  | "NOT_CONSTRUCTIBLE"
  | "UNKNOWN";

export type ConceptType =
  | "population"
  | "anchor"
  | "condition"
  | "measurement"
  | "path event"
  | "terminal outcome"
  | "structural axis"
  | "data field"
  | "sport"
  | "time bucket"
  | "information"
  | "research language"
  | "evidence";

export type VocabularyCategory =
  | "population"
  | "price_threshold"
  | "path"
  | "terminal"
  | "time"
  | "sport"
  | "measurement"
  | "mathematics"
  | "point_in_time"
  | "evidence"
  | "other";

export type PhraseSource = "canonical" | "documented" | "alias" | "notation" | "morphology";

export type AxisAvailability = "AVAILABLE_NOW" | "REGISTERED_NOT_CONSTRUCTIBLE" | "NOT_CURRENTLY_KNOWN";

export type CanonicalConcept = {
  id: string;
  displayName: string;
  conceptType: ConceptType;
  category: VocabularyCategory;
  definition: string;
  whatItMeans: string;
  whatItDoesNotMean: string[];
  constructibility: ConstructibilityStatus;
  authoritativeSource: string;
  relatedConcepts: string[];
  compatiblePopulations: string[];
  knownMeasurements: string[];
  templates: string[];
  knownFields: string[];
  /** True only when this id is a compiler concept or documented synonym target. */
  compilerConcept: boolean;
  whatYouCanDo: string;
  whatDataSupports: string;
};

export type VocabularyPhrase = {
  phrase: string;
  canonicalId: string;
  category: VocabularyCategory;
  source: PhraseSource;
  /** True only for phrases the deterministic compiler actually accepts. */
  compilerAccepted: boolean;
};

export type DataField = {
  id: string;
  displayName: string;
  canonicalField: string;
  description: string;
  valueType: "categorical" | "boolean" | "e4_integer" | "timestamp" | "identifier" | "seconds" | "integer";
  knownValues: { value: string; note?: string; availability: AxisAvailability }[];
  relatedPopulations: string[];
  relatedConcepts: string[];
  constructibility: ConstructibilityStatus;
  aliases: string[];
  authoritativeSource: string;
};

export type BreakdownValue = {
  id: string;
  label: string;
  availability: AxisAvailability;
  note?: string;
  relatedConcept?: string;
};

export type BreakdownAxis = {
  id: string;
  label: string;
  values: BreakdownValue[];
};

export type ConceptBreakdown = {
  conceptId: string;
  axes: BreakdownAxis[];
};

export type RecognizedConcept = {
  id: string;
  displayName: string;
  matchedPhrase: string;
  constructibility: ConstructibilityStatus;
  compilerAccepted: boolean;
};

export type SearchHitKind =
  | "exact_concept"
  | "exact_alias"
  | "field_value"
  | "prefix_token"
  | "related"
  | "registered";

export type SearchHit = {
  id: string;
  kind: SearchHitKind;
  score: number;
  matchedPhrase?: string;
  concept?: CanonicalConcept;
  field?: DataField;
};

export type SearchGroupId =
  | "exact"
  | "related"
  | "fields"
  | "measurements"
  | "breakdowns"
  | "aliases"
  | "registered";

export type SearchGroup = {
  id: SearchGroupId;
  label: string;
  hits: SearchHit[];
};

export type GroupedSearch = {
  query: string;
  normalized: string;
  recognized: RecognizedConcept[];
  unknown: boolean;
  groups: SearchGroup[];
  hits: SearchHit[];
};

export type VocabFile = {
  concepts?: {
    concept: string;
    synonyms?: string[];
    definition_note?: string;
    must_not_equate?: string[];
    binds_to?: unknown;
    unresolved_if_ambiguous?: boolean;
  }[];
};

export type OperatorFamilyId =
  | "ORDINAL_TOUCH"
  | "DROP_TO"
  | "BOUNCE_TO"
  | "RECOVER_TO"
  | "REVERSAL"
  | "CROSS"
  | "PRICE_STATE"
  | "EVER_TOUCH"
  | "NEVER_TOUCH"
  | "SEQUENCE"
  | "TIME_HORIZON"
  | "TERMINAL"
  | "PERIOD";

export type ParsedClause = {
  familyId: OperatorFamilyId;
  expressionId: string;
  displayName: string;
  ordinal?: number;
  event?: string;
  direction?: "UP" | "DOWN";
  relation?: "ABOVE" | "BELOW" | "AT" | "GE" | "LE";
  cents?: number;
  period?: string;
  terminal?: "YES" | "NO";
  horizonMinutes?: number;
  matchedPhrase: string;
  constructibility: ConstructibilityStatus;
  compilerBindable: boolean;
  populationLocked: boolean;
  bindsToImplemented: string[];
  whatItMeans: string;
  whatItDoesNotMean: string[];
};

export type ParsedPhenomenon = {
  query: string;
  normalized: string;
  clauses: ParsedClause[];
  sequence: string[];
  sequenceConstructibility: ConstructibilityStatus;
  sequenceNote: string;
  recognized: boolean;
};

export type CoverageReport = {
  canonicalConcepts: number;
  operatorFamilies: number;
  searchablePhrases: number;
  compilerAcceptedPhrases: number;
  searchOnlyPhrases: number;
  fields: number;
  byCategory: Record<VocabularyCategory, number>;
  implementedConcepts: number;
  configurableConcepts: number;
  registeredConcepts: number;
  notConstructibleConcepts: number;
};
