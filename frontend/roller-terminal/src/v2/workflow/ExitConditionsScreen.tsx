import { useState } from "react";
import { catalogByKind, catalogItem } from "../catalog/availabilityCatalog";
import { GRID_CENTS } from "../vocabulary/normalize";
import Bubble, { AvailabilityNote } from "./Bubble";
import { isCompletePath, newConditionId, setExitConditions } from "./draft";
import { regulationMinutes } from "./periodPartitions";
import { exitSummary } from "./questionFromDraft";
import { isBaseballFamily } from "./sportFamily";
import type { ExitCondition, ExitFamily, ExitOutcome, WorkflowDraft } from "./types";

type Props = {
  draft: WorkflowDraft;
  onChange: (next: WorkflowDraft) => void;
  onBack: () => void;
  onEnter: () => void;
};

function entryRefCents(draft: WorkflowDraft): number | undefined {
  const e = draft.entryConditions[0];
  if (!e) return undefined;
  if (e.priceCents != null) return e.priceCents;
  if (e.priceFrom != null) return e.priceFrom;
  return undefined;
}

function pathLabel(e: ExitCondition): string {
  if (e.kind === "horizon") {
    const fam = catalogItem(e.family, "exit_horizon")?.label ?? e.family.replace(/_/g, " ");
    return e.horizonMinutes != null ? `${fam} +${e.horizonMinutes}m` : fam;
  }
  const fam = catalogItem(e.family, "exit_path")?.label ?? e.family.replace(/_/g, " ");
  return e.priceCents != null ? `${fam.toUpperCase()} ${e.priceCents}¢` : fam.toUpperCase();
}

function minuteChips(game: number, ot: number): Array<{ minutes: number; label: string }> {
  const chips = Array.from({ length: game }, (_, i) => ({ minutes: i + 1, label: `${i + 1}m` }));
  for (let i = 1; i <= ot; i += 1) {
    chips.push({ minutes: game + i, label: `OT+${i}` });
  }
  return chips;
}

function allowedPrice(outcome: ExitOutcome, cents: number, entryRef: number | undefined): boolean {
  if (entryRef == null) return false;
  return outcome === "win" ? cents >= entryRef : cents <= entryRef;
}

export default function ExitConditionsScreen({ draft, onChange, onBack, onEnter }: Props) {
  const paths = catalogByKind("exit_path");
  const baseball = isBaseballFamily(draft.universe);
  const horizons = catalogByKind("exit_horizon").filter((h) =>
    baseball ? !String(h.id).startsWith("horizon_game") : true,
  );
  const clock = regulationMinutes(draft.universe.leagues);
  const minutes = minuteChips(clock.game, clock.ot);
  const entryRef = entryRefCents(draft);
  const commit = (next: ExitCondition[]) => onChange(setExitConditions(draft, next));

  return (
    <div className="ws-flow ws-exit">
      <header className="ws-flow-head">
        <p className="v2-kicker">Exit conditions</p>
        <h1 className="v2-page-title">How does the trade end?</h1>
        <p className="v2-lede">
          Two independent books. The earlier later-bar hit classifies WIN or LOSS. Generic
          same-minute ties are excluded. Base Terminal Efficiency records PIT game/market state
          at entry and classifies the same books with exact-timestamp ties as AMBIGUOUS.{" "}
          <strong>{baseball ? "CANDLE/PRINT PATH ≠ FILL" : "CANDLE PATH ≠ FILL"}</strong>
          {baseball ? " MLB has no 48-minute game clock. Use Reach or Hold." : ""}
        </p>
        <p className="muted small">
          Hold to expiration is a complete WIN/LOSS by itself. It does not use a path percent.
          A ¢ chip is only required if you also want a candle-path observation. Game clock and
          Market clock are not in the question until you pick +N minutes.
        </p>
        {entryRef == null ? (
          <p className="muted small">
            Path ¢ chips stay disabled until an entry price exists. Hold to expiration does not
            wait on that.
          </p>
        ) : (
          <p className="muted small">
            Entry reference {entryRef}¢. Path WIN chips cannot go under it. Path LOSS chips cannot
            go over it. Equality is allowed. Hold ignores this grid.
          </p>
        )}
      </header>

      <div className="ws-exit-books">
        <ExitBook
          outcome="win"
          title="Exit WIN"
          draft={draft}
          paths={paths}
          horizons={horizons.filter((h) => h.id.endsWith("_win"))}
          holdFamily="hold_expiration_win"
          holdNote={
            baseball
              ? "Kalshi settlement YES only from kalshi_markets.result. FIRST80 official W overlay is not joined on MLB last-trade. Missing result is missing, not NO. Not path WIN. Not box score."
              : "Kalshi settlement YES only. Official FIRST80 expiration_result_yes (and the other side of the same event ticker) is joined when canonical kalshi_markets is empty. Not path WIN. Not box score."
          }
          minutes={minutes}
          entryRef={entryRef}
          commit={commit}
        />
        <ExitBook
          outcome="loss"
          title="Exit LOSS"
          draft={draft}
          paths={paths}
          horizons={horizons.filter((h) => h.id.endsWith("_loss"))}
          holdFamily="hold_expiration_loss"
          holdNote={
            baseball
              ? "Kalshi settlement NO only from kalshi_markets.result. FIRST80 official W overlay is not joined on MLB last-trade. Not inferred from the print path."
              : "Kalshi settlement NO only. Official FIRST80 W overlay — not inferred from the candle path."
          }
          minutes={minutes}
          entryRef={entryRef}
          commit={commit}
        />
      </div>

      <footer className="ws-define-footer">
        <div>
          <p className="v2-kicker">Observe</p>
          <p className="ws-question">{exitSummary(draft)}</p>
          <p className="muted small">CANDLE PATH ≠ EXECUTABLE EXIT</p>
        </div>
        <div className="ws-flow-actions">
          <button type="button" className="btn-secondary" onClick={onBack}>
            ← Back
          </button>
          <button type="button" className="btn-primary ws-step-primary" onClick={onEnter}>
            Enter →
          </button>
        </div>
      </footer>
    </div>
  );
}

type BookProps = {
  outcome: ExitOutcome;
  title: string;
  draft: WorkflowDraft;
  paths: ReturnType<typeof catalogByKind>;
  horizons: ReturnType<typeof catalogByKind>;
  holdFamily: ExitFamily;
  holdNote: string;
  minutes: Array<{ minutes: number; label: string }>;
  entryRef: number | undefined;
  commit: (next: ExitCondition[]) => void;
};

function ExitBook({
  outcome,
  title,
  draft,
  paths,
  horizons,
  holdFamily,
  holdNote,
  minutes,
  entryRef,
  commit,
}: BookProps) {
  const book = draft.exitConditions.filter((e) => e.outcome === outcome);
  const path = book.find((e) => e.kind === "path" && !e.sequential);
  const sequential = book.filter((e) => e.kind === "path" && e.sequential);
  const horizon = book.find((e) => e.kind === "horizon");
  const [pendingClock, setPendingClock] = useState<ExitFamily | null>(null);
  const [pendingPath, setPendingPath] = useState<ExitFamily | null>(null);
  const hold = book.find((e) => e.kind === "terminal");
  const sequence = [path, ...sequential].filter(Boolean) as ExitCondition[];
  const clockFamily = horizon?.family ?? pendingClock;
  const pathFamily = path?.family ?? pendingPath;

  const replaceBook = (nextBook: ExitCondition[]) => {
    commit([
      ...draft.exitConditions.filter((e) => e.outcome != null && e.outcome !== outcome),
      ...nextBook,
    ]);
  };

  const upsertPath = (patch: Partial<ExitCondition> & { family: ExitFamily }) => {
    const rest = book.filter((e) => !(e.kind === "path" && !e.sequential));
    const existing = path;
    replaceBook([
      ...rest,
      {
        id: existing?.id ?? newConditionId("exit"),
        kind: "path",
        sequential: false,
        outcome,
        ...existing,
        ...patch,
      },
    ]);
  };

  const addSequential = () => {
    replaceBook([
      ...book,
      {
        id: newConditionId("exit"),
        kind: "path",
        family: "recover",
        priceCents: outcome === "win" ? Math.max(entryRef ?? 80, 80) : Math.min(entryRef ?? 80, 80),
        sequential: true,
        outcome,
      },
    ]);
  };

  const setHorizon = (family: ExitFamily, extra?: Partial<ExitCondition>) => {
    if (extra == null && clockFamily === family) {
      setPendingClock(null);
      replaceBook(book.filter((e) => e.kind !== "horizon"));
      return;
    }
    const kind = family.startsWith("horizon_game") ? "game" : "market";
    const mins =
      extra && "horizonMinutes" in extra ? extra.horizonMinutes : horizon?.horizonMinutes;
    const rest = book.filter((e) => e.kind !== "horizon");
    if (mins == null || mins < 1) {
      setPendingClock(family);
      replaceBook(rest);
      return;
    }
    setPendingClock(family);
    replaceBook([
      ...rest,
      {
        id: horizon?.id ?? newConditionId("exit"),
        kind: "horizon",
        family,
        horizonKind: kind,
        horizonMinutes: mins,
        outcome,
      },
    ]);
  };

  const toggleHold = () => {
    setPendingPath(null);
    if (hold) {
      replaceBook(book.filter((e) => e.kind !== "terminal"));
      return;
    }
    replaceBook([
      ...book.filter((e) => e.kind !== "terminal" && isCompletePath(e)),
      { id: newConditionId("exit"), kind: "terminal", family: holdFamily, outcome },
    ]);
  };

  const togglePathFamily = (family: ExitFamily) => {
    if (path?.family === family) {
      setPendingPath(null);
      replaceBook(book.filter((e) => !(e.kind === "path" && !e.sequential)));
      return;
    }
    if (path?.priceCents != null && allowedPrice(outcome, path.priceCents, entryRef)) {
      upsertPath({ family, priceCents: path.priceCents, sequential: false });
      setPendingPath(null);
      return;
    }
    setPendingPath(family);
  };

  return (
    <section className={`ws-flow-block ws-exit-book ws-exit-book-${outcome}`}>
      <h2>{title}</h2>
      <p className="muted small">
        Terminal Efficiency book · first later hit · exact-timestamp ties stay AMBIGUOUS on the
        TE layer
      </p>

      <h3 className="v2-kicker">Hold to expiration</h3>
      <p className="muted small">{holdNote}</p>
      <div className="ws-chip-row">
        <Bubble
          item={{
            id: holdFamily,
            label: outcome === "win" ? "Hold to expiration · WIN" : "Hold to expiration · LOSS",
            kind: "exit_terminal",
            availability: "IMPLEMENTED",
            note: holdNote,
          }}
          selected={Boolean(hold)}
          onToggle={toggleHold}
        />
      </div>

      <h3 className="v2-kicker">Path (optional percent)</h3>
      <p className="muted small">
        Only if you want a candle-path {outcome.toUpperCase()}. Hold above does not need a ¢.
      </p>
      <div className="ws-chip-row">
        {paths.map((item) => (
          <Bubble
            key={item.id}
            item={item}
            selected={pathFamily === item.id}
            onToggle={() => togglePathFamily(item.id as ExitFamily)}
          />
        ))}
      </div>
      {path && catalogItem(path.family, "exit_path")?.availability !== "IMPLEMENTED" ? (
        <AvailabilityNote
          availability={catalogItem(path.family, "exit_path")?.availability ?? "OPERATION_REQUIRED"}
          note={catalogItem(path.family, "exit_path")?.note}
        />
      ) : null}
      {!hold ? (
        <>
          <h3 className="v2-kicker">Path price</h3>
          <div className="ws-chip-row ws-price-grid">
            {GRID_CENTS.map((c) => {
              const ok = allowedPrice(outcome, c, entryRef);
              return (
                <button
                  key={c}
                  type="button"
                  className={`ws-bubble ${path && path.priceCents === c ? "on" : ""}`}
                  disabled={!ok}
                  onClick={() => {
                    if (!ok) return;
                    upsertPath({
                      family: pathFamily ?? (outcome === "loss" ? "drop_to" : "reach"),
                      priceCents: c,
                      sequential: false,
                    });
                    setPendingPath(null);
                  }}
                >
                  {String(c).padStart(2, "0")}¢
                </button>
              );
            })}
          </div>
        </>
      ) : null}

      <div className="ws-sequence">
        <p className="v2-kicker">Requested order</p>
        <p className="ws-sequence-line">
          {sequence.length ? sequence.map(pathLabel).join(" → ") : "No path on this side"}
        </p>
        {sequential.map((s) => (
          <div key={s.id} className="ws-layer-card">
            <span>THEN {pathLabel(s)}</span>
            <button
              type="button"
              className="v2-text-link"
              onClick={() => replaceBook(book.filter((e) => e.id !== s.id))}
            >
              Remove
            </button>
          </div>
        ))}
        <button type="button" className="btn-secondary" onClick={addSequential}>
          + Then observe another path
        </button>
      </div>

      <h3 className="v2-kicker">Clock</h3>
      <div className="ws-chip-row">
        {horizons.map((item) => (
          <Bubble
            key={item.id}
            item={item}
            selected={clockFamily === item.id}
            onToggle={() => setHorizon(item.id as ExitFamily)}
          />
        ))}
      </div>
      {clockFamily ? (
        <>
          <p className="muted small">
            {horizon?.horizonMinutes != null
              ? `Included: +${horizon.horizonMinutes}m. Click the minute again to remove the clock from the question.`
              : "Pick +N minutes to include this clock. Leaving without a minute leaves it out of the question — Confirm can still run."}
          </p>
          <div className="ws-chip-row ws-price-grid">
            {minutes.map((m) => (
              <button
                key={m.minutes}
                type="button"
                className={`ws-bubble ${horizon?.horizonMinutes === m.minutes ? "on" : ""}`}
                onClick={() =>
                  setHorizon(clockFamily, {
                    horizonMinutes: horizon?.horizonMinutes === m.minutes ? undefined : m.minutes,
                  })
                }
              >
                {m.label}
              </button>
            ))}
          </div>
        </>
      ) : null}
    </section>
  );
}
