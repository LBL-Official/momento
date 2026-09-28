import { useMemo, useState } from "react";
import type { Spec } from "../../researchTypes";
import { defineBlocks, QUICK_START, type ChipHonesty, type DefineChip } from "./defineCatalog";
import { canOfferValidate, composeQuestion } from "./questionComposer";
import { interpretDefineSearch } from "./searchBridge";
import {
  clearFamily,
  emptyIntent,
  upsertClause,
  type IntentFamily,
  type RecognizedIntent,
} from "./recognizedIntent";
import { isChipSelected } from "./chipSelection";

type Props = {
  spec: Spec;
  intent: RecognizedIntent;
  onIntentChange: (intent: RecognizedIntent) => void;
  onLoadTemplate: (templateId: string) => void;
  onValidate: () => void;
  onOpenAdvanced: () => void;
  showAdvanced: boolean;
  validateBusy?: boolean;
};

const HONESTY_MARK: Record<ChipHonesty, string> = {
  required: "●",
  optional: "○",
  implied: "◌",
  recognized: "◇",
};

const FAMILY_BY_BLOCK: Record<string, IntentFamily> = {
  sport: "sport",
  population: "population",
  season: "season",
  event: "event",
  when: "when",
  prior: "prior",
  after: "after",
  terminal: "terminal",
};

export default function DefineQuestionnaire({
  spec,
  intent,
  onIntentChange,
  onLoadTemplate,
  onValidate,
  onOpenAdvanced,
  showAdvanced,
  validateBusy,
}: Props) {
  const [query, setQuery] = useState("");
  const [searchNote, setSearchNote] = useState<string | null>(null);
  const blocks = useMemo(() => defineBlocks(spec, intent), [spec, intent]);
  const question = useMemo(() => composeQuestion(spec, intent), [spec, intent]);
  const canValidate = canOfferValidate(spec);

  const applySearch = () => {
    const found = interpretDefineSearch(query);
    setSearchNote(`${found.outcome} — ${found.summary}`);
    if (found.templateId && !found.forbidFirst80Rewrite) {
      onLoadTemplate(found.templateId);
    }
    if (found.overlayClauses.length) {
      let next = found.templateId && !found.forbidFirst80Rewrite ? emptyIntent() : intent;
      for (const c of found.overlayClauses) next = upsertClause(next, c);
      onIntentChange(next);
    } else if (found.templateId && !found.forbidFirst80Rewrite) {
      onIntentChange(emptyIntent());
    }
  };

  const onChip = (blockId: string, chip: DefineChip) => {
    if (chip.templateId) {
      onLoadTemplate(chip.templateId);
      onIntentChange(emptyIntent());
      return;
    }
    if (chip.id === "frozen") {
      onIntentChange({ ...intent, selectedSeason: null });
      return;
    }
    if (chip.id === "2023-24" || chip.id === "2024-25") {
      onIntentChange({ ...intent, selectedSeason: chip.id });
      return;
    }
    if (chip.id === "nba" || chip.id === "ncaab") {
      onIntentChange(clearFamily(intent, "sport"));
      return;
    }
    if (chip.id === "NONE" || chip.id === "T40" || chip.id === "lock-event" || chip.id === "Q3" || chip.id === "P5") {
      const family = FAMILY_BY_BLOCK[blockId];
      onIntentChange(clearFamily(intent, family));
      return;
    }
    if (chip.id === "YES" || chip.id === "NO" || chip.id === "FIRST80") {
      return;
    }
    if (chip.recognized || chip.honesty === "recognized") {
      const family = FAMILY_BY_BLOCK[blockId] ?? "search";
      onIntentChange(
        upsertClause(intent, {
          id: chip.id,
          family,
          label: chip.label,
          constructible: false,
        }),
      );
    }
  };

  return (
    <div className="ws-define">
      <header className="ws-define-head">
        <p className="v2-kicker">Step 1 · Define</p>
        <h1 className="v2-page-title">Ask a research question</h1>
        <p className="v2-lede">
          Select a locked population or compose from the vocabulary. Language is not
          constructibility. Roller will not rewrite an unavailable question into FIRST80.
        </p>
      </header>

      <section className="ws-quick-start" aria-label="Quick Start">
        <p className="v2-kicker">Quick Start</p>
        <div className="ws-quick-row">
          {QUICK_START.map((q) => (
            <button
              key={q.id}
              type="button"
              className="ws-quick-card"
              onClick={() => {
                onLoadTemplate(q.templateId);
                onIntentChange(emptyIntent());
                setSearchNote(null);
              }}
            >
              <strong>{q.label}</strong>
              <span className="muted">{q.sub}</span>
            </button>
          ))}
        </div>
        <div className="ws-define-search">
          <label className="v2-kicker" htmlFor="define-search">
            Or explore a research question
          </label>
          <div className="ws-define-search-row">
            <input
              id="define-search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") applySearch();
              }}
              placeholder="SECOND80, bounce, NCAAB FIRST80 P5…"
            />
            <button type="button" className="btn-secondary" onClick={applySearch}>
              Search
            </button>
          </div>
          {searchNote ? <p className="muted small">{searchNote}</p> : null}
        </div>
      </section>

      <ol className="ws-define-q">
        {blocks.map((block) => (
          <li key={block.id} className="ws-define-block">
            <h2>
              <span className="ws-honesty" title={block.honesty}>
                {HONESTY_MARK[block.honesty]}
              </span>{" "}
              {block.n}. {block.title}
            </h2>
            <p className="muted small">{block.hint}</p>
            {block.id === "event" && !intent.customizeUnlocked ? (
              <button
                type="button"
                className="v2-text-link"
                onClick={() => onIntentChange({ ...intent, customizeUnlocked: true })}
              >
                Customize event (overlay only — does not upgrade constructibility)
              </button>
            ) : null}
            {(block.id !== "event" || intent.customizeUnlocked || block.chips.some((c) => c.honesty === "implied")) && (
              <div className="ws-chip-row" role="group" aria-label={block.title}>
                {block.chips
                  .filter((c) => block.id !== "event" || intent.customizeUnlocked || c.honesty === "implied")
                  .map((chip) => {
                    const selected = isChipSelected(chip.id, spec, intent);
                    const lockedImplied = chip.honesty === "implied" && !intent.customizeUnlocked;
                    return (
                      <button
                        key={chip.id}
                        type="button"
                        className={`ws-bubble ${selected ? "on" : ""} ${chip.honesty}`}
                        disabled={lockedImplied && chip.honesty === "implied" && !chip.recognized}
                        onClick={() => onChip(block.id, chip)}
                      >
                        <span className="ws-honesty">{HONESTY_MARK[chip.honesty]}</span> {chip.label}
                      </button>
                    );
                  })}
              </div>
            )}
          </li>
        ))}
      </ol>

      <p className="ws-honesty-legend muted small">
        ● required · ○ optional · ◌ implied by population · ◇ recognized — not constructible
      </p>

      <button type="button" className="v2-text-link ws-advanced-link" onClick={onOpenAdvanced}>
        {showAdvanced ? "Hide advanced details" : "Advanced details (A–I builder)"}
      </button>

      <footer className="ws-define-footer">
        <div>
          <p className="v2-kicker">Your research question</p>
          <p className="ws-question">{question}</p>
        </div>
        <button
          type="button"
          className="btn-primary ws-step-primary"
          disabled={!canValidate || validateBusy}
          onClick={onValidate}
        >
          {validateBusy ? "Validating…" : "Validate research"}
        </button>
      </footer>
    </div>
  );
}
