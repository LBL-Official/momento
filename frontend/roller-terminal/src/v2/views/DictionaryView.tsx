import { useEffect, useMemo, useState } from "react";
import { apiFetch } from "../../api/base";
import StatusBadge, { toneForStatus } from "../../components/StatusBadge";
import { QUERY_WRITING_GUIDE } from "../docsContent";
import {
  breakdownFor,
  buildDiscoveryIndex,
  CONCEPT_BY_ID,
  FIELD_BY_ID,
  OPERATOR_FAMILIES,
  parsePhenomenon,
  searchDiscovery,
  type CanonicalConcept,
  type DataField,
  type ParsedClause,
  type VocabFile,
} from "../vocabulary";

type Props = {
  onOpenTemplate?: (templateId: string) => void;
};

type Selected =
  | { kind: "concept"; id: string }
  | { kind: "clause"; clause: ParsedClause }
  | { kind: "field"; id: string };

function statusTone(s: string) {
  return toneForStatus(s);
}

export default function DictionaryView({ onOpenTemplate }: Props) {
  const [vocab, setVocab] = useState<VocabFile | null>(null);
  const [q, setQ] = useState("");
  const [selected, setSelected] = useState<Selected | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      apiFetch("/vocabulary").then(async (r) => (r.ok ? r.json() : null)),
      fetch("/data/research_vocabulary_v0.json").then(async (r) => (r.ok ? r.json() : null)),
    ])
      .then(([api, file]) => {
        if (cancelled) return;
        setVocab((api as VocabFile) || (file as VocabFile) || null);
      })
      .catch((e) => {
        if (!cancelled) setErr(e instanceof Error ? e.message : String(e));
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const index = useMemo(() => buildDiscoveryIndex(vocab), [vocab]);
  const grouped = useMemo(() => searchDiscovery(index, q), [index, q]);
  const parsed = useMemo(() => parsePhenomenon(q), [q]);

  const selectedConcept: CanonicalConcept | null =
    selected?.kind === "concept" ? (CONCEPT_BY_ID[selected.id] ?? null) : null;
  const selectedField: DataField | null =
    selected?.kind === "field" ? (FIELD_BY_ID[selected.id] ?? null) : null;
  const selectedClause = selected?.kind === "clause" ? selected.clause : null;
  const clauseConcept = selectedClause
    ? (CONCEPT_BY_ID[selectedClause.expressionId] ?? CONCEPT_BY_ID[selectedClause.familyId] ?? null)
    : null;

  return (
    <div className="v2-dictionary">
      <header className="v2-view-header">
        <h1 className="v2-page-title">Data Dictionary</h1>
        <p className="v2-lede">
          Compositional phenomenon vocabulary. Search discovers families and parameters. Recognition
          is not compilation, and compilation is not execution.
        </p>
      </header>

      <div className="v2-dict-layout">
        <div className="v2-dict-list">
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder='Try: "first price reaches 80 in Q3 then drops to 40"'
            aria-label="Search vocabulary"
          />
          {err ? <div className="error">{err}</div> : null}

          {q.trim() && parsed.recognized ? (
            <div className="v2-recog">
              <div className="v2-kicker">Recognized structure</div>
              <ol className="v2-seq">
                {parsed.clauses.map((c) => (
                  <li key={`${c.expressionId}-${c.matchedPhrase}`}>
                    <button
                      type="button"
                      className="v2-seq-step"
                      onClick={() => setSelected({ kind: "clause", clause: c })}
                    >
                      <span className="v2-dict-title">{c.displayName}</span>
                      <StatusBadge label={c.constructibility} tone={statusTone(c.constructibility)} />
                    </button>
                  </li>
                ))}
              </ol>
              <p className="evidence">{parsed.sequenceNote}</p>
              <p className="muted">
                Sequence status: {parsed.sequenceConstructibility}. SEARCH ≠ COMPILER. TOUCH ≠ CROSS ≠
                STATE.
              </p>
            </div>
          ) : null}

          {grouped.unknown ? (
            <p className="muted">UNKNOWN — no canonical ROLLER mapping for this phrase.</p>
          ) : null}

          {grouped.groups.map((g) => (
            <div key={g.id} className="v2-phenomena-group">
              <div className="v2-kicker">{g.label}</div>
              <ul>
                {g.hits.map((h) => (
                  <li key={`${g.id}-${h.id}`}>
                    <button
                      type="button"
                      className={
                        (selected?.kind === "concept" && selected.id === h.concept?.id) ||
                        (selected?.kind === "field" && selected.id === h.field?.id)
                          ? "v2-dict-row on"
                          : "v2-dict-row"
                      }
                      onClick={() => {
                        if (h.field) setSelected({ kind: "field", id: h.field.id });
                        else if (h.concept) setSelected({ kind: "concept", id: h.concept.id });
                      }}
                    >
                      <span className="v2-kicker">
                        {h.field ? "field" : h.concept?.conceptType}
                        {h.concept ? ` · ${h.concept.constructibility}` : ""}
                      </span>
                      <span className="v2-dict-title">{h.concept?.displayName ?? h.field?.displayName}</span>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="v2-dict-detail research-object">
          {!selected && !q.trim() ? (
            <EmptyGuide />
          ) : selectedClause ? (
            <ClauseDetail
              clause={selectedClause}
              concept={clauseConcept}
              onOpenTemplate={onOpenTemplate}
              onOpenConcept={(id) => setSelected({ kind: "concept", id })}
            />
          ) : selectedField ? (
            <FieldDetail field={selectedField} onOpenConcept={(id) => setSelected({ kind: "concept", id })} />
          ) : selectedConcept ? (
            <ConceptDetail
              concept={selectedConcept}
              aliases={index.phrases.filter((p) => p.canonicalId === selectedConcept.id).slice(0, 24)}
              onOpenTemplate={onOpenTemplate}
              onOpenConcept={(id) => setSelected({ kind: "concept", id })}
            />
          ) : (
            <EmptyGuide />
          )}
        </div>
      </div>
    </div>
  );
}

function EmptyGuide() {
  return (
    <div>
      <h2>Phenomenon grammar</h2>
      <p>
        ROLLER understands families, not a flat synonym list. A query can name an operator and fill
        parameters. That does not create a new population.
      </p>
      <div className="v2-query-cat">
        <div className="v2-kicker">Families</div>
        <div className="evidence">{OPERATOR_FAMILIES.map((f) => f.id).join(" · ")}</div>
      </div>
      <div className="v2-query-cat">
        <div className="v2-kicker">Grammar</div>
        <div className="evidence">
          [ORDINAL] [TOUCH] [LEVEL] · [DROP|BOUNCE|RECOVER] TO [LEVEL] · [EVER|NEVER] [LEVEL] · EVENT →
          EVENT → TERMINAL
        </div>
      </div>
      <h2>{QUERY_WRITING_GUIDE.title}</h2>
      <p>{QUERY_WRITING_GUIDE.intro}</p>
      {QUERY_WRITING_GUIDE.categories.map((c) => (
        <div key={c.name} className="v2-query-cat">
          <div className="v2-kicker">{c.name}</div>
          <div className="evidence">{c.words.join(" · ")}</div>
        </div>
      ))}
      <h3>Examples</h3>
      <ul>
        {[
          ...QUERY_WRITING_GUIDE.examples,
          "second touch of 80",
          "first 80 then drops to 40 then bounces to 70",
          "forty cent barrier",
        ].map((ex) => (
          <li key={ex} className="evidence">
            {ex}
          </li>
        ))}
      </ul>
    </div>
  );
}

function ClauseDetail({
  clause,
  concept,
  onOpenTemplate,
  onOpenConcept,
}: {
  clause: ParsedClause;
  concept: CanonicalConcept | null;
  onOpenTemplate?: (id: string) => void;
  onOpenConcept: (id: string) => void;
}) {
  return (
    <div>
      <div className="v2-kicker">
        {clause.familyId} · parameterized expression
      </div>
      <h2>{clause.displayName}</h2>
      <StatusBadge label={clause.constructibility} tone={statusTone(clause.constructibility)} />
      <p>{clause.whatItMeans}</p>
      <h3>Parameters</h3>
      <p className="evidence">
        {[
          clause.ordinal != null ? `ordinal=${clause.ordinal}` : null,
          clause.cents != null ? `level=${clause.cents}¢ (e4=${clause.cents * 100})` : null,
          clause.direction ? `direction=${clause.direction}` : null,
          clause.relation ? `relation=${clause.relation}` : null,
          clause.period ? `period=${clause.period}` : null,
          clause.terminal ? `terminal=${clause.terminal}` : null,
          clause.horizonMinutes != null ? `horizon=${clause.horizonMinutes}m` : null,
        ]
          .filter(Boolean)
          .join(" · ")}
      </p>
      <h3>What it does not mean</h3>
      <ul>
        {clause.whatItDoesNotMean.map((x) => (
          <li key={x}>{x}</li>
        ))}
      </ul>
      <h3>Compiler vs search</h3>
      <p className="evidence">
        compilerBindable={String(clause.compilerBindable)} · populationLocked=
        {String(clause.populationLocked)} · SEARCH DISCOVERABILITY ≠ COMPILER ACCEPTANCE
      </p>
      {concept ? (
        <>
          <h3>Canonical family / instance</h3>
          <button type="button" className="v2-text-link" onClick={() => onOpenConcept(concept.id)}>
            {concept.displayName} →
          </button>
        </>
      ) : null}
      {clause.bindsToImplemented.length ? (
        <>
          <h3>Related implemented bindings</h3>
          <p className="evidence">{clause.bindsToImplemented.join(" · ")}</p>
        </>
      ) : null}
      {concept?.templates.length ? (
        <>
          <h3>Available research objects</h3>
          <div className="v2-home-links">
            {concept.templates.map((tid) => (
              <button key={tid} type="button" className="v2-text-link" onClick={() => onOpenTemplate?.(tid)}>
                {tid} →
              </button>
            ))}
          </div>
        </>
      ) : null}
    </div>
  );
}

function ConceptDetail({
  concept,
  aliases,
  onOpenTemplate,
  onOpenConcept,
}: {
  concept: CanonicalConcept;
  aliases: { phrase: string; compilerAccepted: boolean }[];
  onOpenTemplate?: (id: string) => void;
  onOpenConcept: (id: string) => void;
}) {
  const bd = breakdownFor(concept.id);
  return (
    <div>
      <div className="v2-kicker">
        {concept.conceptType} · {concept.category}
      </div>
      <h2>{concept.displayName}</h2>
      <StatusBadge label={concept.constructibility} tone={statusTone(concept.constructibility)} />
      <h3>What is this?</h3>
      <p>{concept.definition}</p>
      <h3>What does it mean?</h3>
      <p>{concept.whatItMeans}</p>
      <h3>What it does not mean</h3>
      <ul>
        {concept.whatItDoesNotMean.map((x) => (
          <li key={x}>{x}</li>
        ))}
      </ul>
      <h3>Is it implemented?</h3>
      <p className="evidence">
        {concept.constructibility}
        {concept.compilerConcept ? " · compiler concept" : " · search family / instance — not automatically compiler-accepted"}
      </p>
      <h3>What can I do with it?</h3>
      <p>{concept.whatYouCanDo}</p>
      <h3>What data supports it?</h3>
      <p className="evidence">{concept.whatDataSupports}</p>
      <p className="muted">{concept.authoritativeSource}</p>
      {concept.compatiblePopulations.length ? (
        <>
          <h3>Populations</h3>
          <p className="evidence">{concept.compatiblePopulations.join(" · ")}</p>
        </>
      ) : null}
      {concept.knownMeasurements.length ? (
        <>
          <h3>Measurements</h3>
          <p className="evidence">{concept.knownMeasurements.join(" · ")}</p>
        </>
      ) : null}
      {concept.knownFields.length ? (
        <>
          <h3>Fields</h3>
          <p className="evidence">{concept.knownFields.join(" · ")}</p>
        </>
      ) : null}
      {bd ? (
        <>
          <h3>Available breakdowns</h3>
          {bd.axes.map((axis) => (
            <div key={axis.id} className="v2-query-cat">
              <div className="v2-kicker">{axis.label}</div>
              <ul>
                {axis.values.map((v) => (
                  <li key={v.id} className="evidence">
                    {v.label} · {v.availability}
                    {v.note ? ` — ${v.note}` : ""}
                    {v.relatedConcept ? (
                      <>
                        {" "}
                        <button
                          type="button"
                          className="v2-text-link"
                          onClick={() => onOpenConcept(v.relatedConcept!)}
                        >
                          {v.relatedConcept}
                        </button>
                      </>
                    ) : null}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </>
      ) : null}
      {concept.relatedConcepts.length ? (
        <>
          <h3>Related concepts</h3>
          <div className="v2-home-links">
            {concept.relatedConcepts.map((id) => (
              <button key={id} type="button" className="v2-text-link" onClick={() => onOpenConcept(id)}>
                {id} →
              </button>
            ))}
          </div>
        </>
      ) : null}
      {concept.templates.length ? (
        <>
          <h3>Available research objects</h3>
          <div className="v2-home-links">
            {concept.templates.map((tid) => (
              <button key={tid} type="button" className="v2-text-link" onClick={() => onOpenTemplate?.(tid)}>
                {tid} →
              </button>
            ))}
          </div>
        </>
      ) : null}
      {aliases.length ? (
        <>
          <h3>Search phrases</h3>
          <p className="evidence">
            {aliases
              .map((a) => (a.compilerAccepted ? `${a.phrase} ✓compiler` : a.phrase))
              .join(" · ")}
          </p>
        </>
      ) : null}
    </div>
  );
}

function FieldDetail({
  field,
  onOpenConcept,
}: {
  field: DataField;
  onOpenConcept: (id: string) => void;
}) {
  return (
    <div>
      <div className="v2-kicker">data field · {field.valueType}</div>
      <h2>{field.displayName}</h2>
      <StatusBadge label={field.constructibility} tone={statusTone(field.constructibility)} />
      <p>{field.description}</p>
      <h3>Canonical field</h3>
      <p className="evidence">{field.canonicalField}</p>
      {field.knownValues.length ? (
        <>
          <h3>Known values</h3>
          <ul>
            {field.knownValues.map((v) => (
              <li key={v.value} className="evidence">
                {v.value} · {v.availability}
                {v.note ? ` — ${v.note}` : ""}
              </li>
            ))}
          </ul>
        </>
      ) : (
        <p className="muted">No enumerated values claimed beyond the field type.</p>
      )}
      <h3>Aliases</h3>
      <p className="evidence">{field.aliases.join(" · ")}</p>
      <p className="muted">{field.authoritativeSource}</p>
      {field.relatedConcepts.length ? (
        <>
          <h3>Related concepts</h3>
          <div className="v2-home-links">
            {field.relatedConcepts.map((id) => (
              <button key={id} type="button" className="v2-text-link" onClick={() => onOpenConcept(id)}>
                {id} →
              </button>
            ))}
          </div>
        </>
      ) : null}
    </div>
  );
}
