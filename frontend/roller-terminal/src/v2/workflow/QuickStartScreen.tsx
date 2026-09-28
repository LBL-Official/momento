import { catalogByKind } from "../catalog/availabilityCatalog";
import { toggleIn, updateUniverse } from "./draft";
import Bubble, { AvailabilityNote } from "./Bubble";
import { universeSummaryLines } from "./questionFromDraft";
import { dateRangeForSelections } from "./seasonDates";
import {
  clearIncompatiblePeriods,
  clearIncompatibleTeState,
  familyOf,
  selectSportFamily,
  type SportFamily,
} from "./sportFamily";
import type { WorkflowDraft } from "./types";

type Props = {
  draft: WorkflowDraft;
  onChange: (next: WorkflowDraft) => void;
  onEnter: () => void;
};

/** A numbered stage of the universe specification. Stages are ordered along a
 *  single vertical axis so the screen reads as an instrument being configured
 *  rather than as a settings page. */
function Stage({
  index,
  title,
  lede,
  layout = "grid",
  children,
}: {
  index: string;
  title: string;
  lede?: string;
  /** "grid" lays fields out on the six-column axis; "flow" is a single
   *  full-width block for stages that are not a field matrix. */
  layout?: "grid" | "flow";
  children: React.ReactNode;
}) {
  return (
    <section className="mm-stage">
      <header className="mm-stage-head">
        <span className="mm-stage-index">{index}</span>
        <h2 className="mm-stage-title">{title}</h2>
        <span className="mm-stage-rule" aria-hidden />
      </header>
      {lede ? <p className="mm-stage-lede">{lede}</p> : null}
      <div className={layout === "flow" ? "mm-stage-body is-flow" : "mm-stage-body"}>
        {children}
      </div>
    </section>
  );
}

/** A single specification field. `weight` drives the visual hierarchy:
 *  primary dimensions dominate, tertiary ones stay quiet. */
function Field({
  label,
  weight = "secondary",
  children,
  note,
}: {
  label: string;
  weight?: "primary" | "secondary" | "tertiary";
  children: React.ReactNode;
  note?: React.ReactNode;
}) {
  return (
    <div className={`mm-field is-${weight}`}>
      <h3 className="mm-field-label">{label}</h3>
      <div className="mm-field-control">{children}</div>
      {note}
    </div>
  );
}

export default function QuickStartScreen({ draft, onChange, onEnter }: Props) {
  const u = draft.universe;
  const sports = catalogByKind("sport");
  const leagues = catalogByKind("league").filter(
    (l) => !l.sports?.length || l.sports.some((s) => u.sports.includes(s)) || u.sports.length === 0,
  );
  const seasons = catalogByKind("season");
  const markets = catalogByKind("market");
  const marketData = catalogByKind("market_data");
  const pbp = catalogByKind("pbp");

  const applyFamily = (id: string) => {
    const fam = familyOf(id) as SportFamily;
    const nextU = selectSportFamily(u, id);
    const seasons =
      (fam === "baseball" || fam === "tennis") && !nextU.seasons.length
        ? ["2025-26"]
        : nextU.seasons;
    const prevFill = dateRangeForSelections(u.leagues, u.seasons);
    const wasAutofill = u.dateFrom === prevFill.dateFrom && u.dateTo === prevFill.dateTo;
    const marketData = nextU.marketData;
    const markets = nextU.markets.length ? nextU.markets : ["kalshi"];
    onChange({
      ...updateUniverse(draft, {
        sports: nextU.sports,
        leagues: nextU.leagues,
        seasons,
        markets,
        marketData,
        ...(wasAutofill || !u.dateFrom
          ? { dateFrom: undefined, dateTo: undefined }
          : {}),
      }),
      entryConditions: draft.entryConditions.map((e) => clearIncompatiblePeriods(e, fam)),
      teFilters: clearIncompatibleTeState(draft.teFilters, fam),
    });
  };

  const setList = (key: "sports" | "leagues" | "seasons" | "markets" | "marketData" | "dataSources", id: string) => {
    if (key === "sports" || key === "leagues") {
      applyFamily(id);
      return;
    }
    if (key === "seasons") {
      const next = toggleIn(u.seasons, id);
      const prevFill = dateRangeForSelections(u.leagues, u.seasons);
      const wasAutofill = u.dateFrom === prevFill.dateFrom && u.dateTo === prevFill.dateTo;
      onChange(
        updateUniverse(draft, {
          seasons: next,
          ...(wasAutofill || !u.dateFrom
            ? { dateFrom: undefined, dateTo: undefined }
            : {}),
        }),
      );
      return;
    }
    if (key === "marketData") {
      if (id === "tick" || id === "l2") return;
      const mlbDesk = u.leagues.length === 1 && u.leagues[0] === "MLB" && u.sports.includes("baseball");
      const tennisDesk =
        u.sports.includes("tennis") &&
        u.leagues.length === 1 &&
        (u.leagues[0] === "ATP" || u.leagues[0] === "WTA");
      if (id === "last_trade") {
        if (!mlbDesk && !tennisDesk) return;
        const next = toggleIn(u.marketData.filter((x) => x !== "candles"), "last_trade");
        onChange(updateUniverse(draft, { marketData: next.length ? next : ["last_trade"] }));
        return;
      }
      if (id === "candles") {
        const next = toggleIn(u.marketData.filter((x) => x !== "last_trade"), "candles");
        onChange(updateUniverse(draft, { marketData: next.length ? next : ["candles"] }));
        return;
      }
    }
    onChange(updateUniverse(draft, { [key]: toggleIn(u[key], id) }));
  };

  const nbaOnly = u.leagues.length === 1 && u.leagues[0] === "NBA" && u.sports.includes("basketball");
  const ncaabOnly = u.leagues.length === 1 && u.leagues[0] === "NCAAB" && u.sports.includes("basketball");
  const mlbOnly = u.leagues.length === 1 && u.leagues[0] === "MLB" && u.sports.includes("baseball");
  const atpOnly = u.leagues.length === 1 && u.leagues[0] === "ATP" && u.sports.includes("tennis");
  const wtaOnly = u.leagues.length === 1 && u.leagues[0] === "WTA" && u.sports.includes("tennis");
  const canEnter = nbaOnly || ncaabOnly || mlbOnly || atpOnly || wtaOnly;
  const seasonFill = dateRangeForSelections(u.leagues, u.seasons);
  const polymarketOn = u.markets.includes("polymarket");
  const tennisOn = u.sports.includes("tennis");
  const baseballOn = u.sports.includes("baseball") || u.leagues.includes("MLB");

  const resolved = universeSummaryLines(draft);

  return (
    <div className="ws-flow ws-quickstart">
      {/* ── Momento Systems identity — the signature of the instrument ── */}
      <section className="mm-identity" aria-label="Momento Systems ROLLER Research Terminal">
        <img
          className="mm-identity-owl"
          src="/brand/momento-owl.png"
          alt="Momento Systems"
          decoding="async"
        />
        <p className="mm-identity-org">
          Momento Systems <span className="mm-identity-suffix">LLC</span>
        </p>
        <h1 className="mm-identity-product">Roller</h1>
        <p className="mm-identity-role">Research Terminal</p>
        <p className="mm-identity-lede">Empirical market research infrastructure</p>
      </section>

      {/* ── 01 · Population ─────────────────────────────────────────── */}
      <Stage
        index="01"
        title="Research universe"
        lede="Build the universe in which the research object will exist."
      >
        <Field label="Sport" weight="primary">
          <div className="ws-chip-row">
            {sports.map((item) => (
              <Bubble
                key={item.id}
                item={item}
                selected={u.sports.includes(item.id)}
                onToggle={() => setList("sports", item.id)}
              />
            ))}
          </div>
        </Field>

        <Field label="League" weight="primary">
          <div className="ws-chip-row">
            {leagues.map((item) => (
              <Bubble
                key={item.id}
                item={item}
                selected={u.leagues.includes(item.id)}
                onToggle={() => setList("leagues", item.id)}
              />
            ))}
          </div>
        </Field>

        <Field
          label="Season"
          weight="tertiary"
          note={
            <p className="muted small">
              Blank = full selected season. UI seasons are never written onto a lock spec.
            </p>
          }
        >
          <div className="ws-chip-row">
            {seasons.map((item) => (
              <Bubble
                key={item.id}
                item={item}
                selected={u.seasons.includes(item.id)}
                onToggle={() => setList("seasons", item.id)}
              />
            ))}
          </div>
        </Field>
      </Stage>

      {/* ── 02 · Observation ────────────────────────────────────────── */}
      <Stage
        index="02"
        title="Observation"
        lede="Choose what ROLLER is allowed to observe. Availability is a system state, not a preference."
      >
        <Field
          label="Market"
          weight="primary"
          note={
            polymarketOn ? (
              <AvailabilityNote
                availability="OPERATION_REQUIRED"
                note="Last-trade 1-minute history is not tradable top-of-book. Kalshi cannot be substituted automatically."
              />
            ) : undefined
          }
        >
          <div className="ws-chip-row">
            {markets.map((item) => (
              <Bubble
                key={item.id}
                item={item}
                selected={u.markets.includes(item.id)}
                onToggle={() => setList("markets", item.id)}
              />
            ))}
          </div>
        </Field>

        <Field
          label="Market observation"
          weight="secondary"
          note={
            baseballOn ? (
              <p className="muted small">
                Candles (yes bid / yes ask) are the MLB default. LAST TRADE ≠ YES BID.
                Last trade remains selectable. Tick and L2 stay DATA_REQUIRED.
                CANDLE/PRINT PATH ≠ FILL.
              </p>
            ) : tennisOn ? (
              <p className="muted small">
                Tennis uses native Kalshi candles with genuine yes_bid. LAST TRADE ≠ YES BID.
                CANDLE/PRINT PATH ≠ FILL.
              </p>
            ) : undefined
          }
        >
          <div className="ws-chip-row">
            {marketData.map((item) => {
              return (
                <Bubble
                  key={item.id}
                  item={item}
                  selected={u.marketData.includes(item.id)}
                  disabled={item.id === "tick" || item.id === "l2"}
                  onToggle={() => setList("marketData", item.id)}
                />
              );
            })}
          </div>
        </Field>

        <Field label="Game state" weight="secondary">
          <div className="ws-chip-row">
            {pbp.map((item) => (
              <Bubble
                key={item.id}
                item={item}
                selected={u.dataSources.includes(item.id)}
                onToggle={() => setList("dataSources", item.id)}
              />
            ))}
          </div>
        </Field>

        {tennisOn ? (
          <p className="muted small">
            Tennis is a first-class research family. SEQUENCE-ONLY PBP is not a PIT snap.
            LAST TRADE ≠ YES BID. CANDLE PATH ≠ FILL.
          </p>
        ) : null}
      </Stage>

      {/* ── 03 · Interval ───────────────────────────────────────────── */}
      <Stage
        index="03"
        title="Interval"
        lede="The observation window applied to the selected calendar."
        layout="flow"
      >
        <div className="mm-interval">
          <label className="mm-interval-end">
            <span className="mm-interval-key">From</span>
            <input
              type="date"
              value={u.dateFrom ?? ""}
              onChange={(e) =>
                onChange(updateUniverse(draft, { dateFrom: e.target.value || undefined }))
              }
            />
          </label>
          <span className="mm-interval-span" aria-hidden />
          <label className="mm-interval-end">
            <span className="mm-interval-key">To</span>
            <input
              type="date"
              value={u.dateTo ?? ""}
              onChange={(e) =>
                onChange(updateUniverse(draft, { dateTo: e.target.value || undefined }))
              }
            />
          </label>
        </div>
        {u.dateFrom || u.dateTo ? (
          <p className="mm-interval-calendar">
            <span className="mm-interval-calendar-k">Calendar</span>
            {seasonFill.source ?? "Custom date filter on the selected seasons."}
          </p>
        ) : null}
        <p className="muted small">
          Blank dates measure the full selected season. Type a From/To only when you want a custom
          window. Season chips do not write a silent date filter. A typed window is the window that
          runs.
        </p>
      </Stage>

      {/* ── 04 · Resolved ───────────────────────────────────────────── */}
      <Stage
        index="04"
        title="Resolved universe"
        lede="The specification ROLLER will carry forward."
        layout="flow"
      >
        <dl className="ws-universe-dl mm-resolved">
          {resolved.map((row) => (
            <div key={row.k}>
              <dt>{row.k}</dt>
              <dd>{row.v}</dd>
            </div>
          ))}
        </dl>
      </Stage>

      <div className="mm-commit">
        <button type="button" className="mm-action ws-step-primary" disabled={!canEnter} onClick={onEnter}>
          Enter research
          <span className="mm-action-glyph" aria-hidden>
            →
          </span>
        </button>
        {!canEnter ? (
          <p className="mm-commit-hint">Select Basketball · NBA, Basketball · NCAAB, Baseball · MLB, or Tennis · exactly one of ATP / WTA. Mixed ATP+WTA stays unavailable.</p>
        ) : null}
      </div>

      <div className="mm-footplate">
        <span className="mm-footplate-org">
          <img className="mm-footplate-mark" src="/brand/momento-m-mark.png" alt="" aria-hidden />
          Momento Systems LLC · ROLLER Research Terminal
        </span>
        <span className="mm-footplate-terms">
          <span>Internal research infrastructure</span>
          <span>Not an execution system</span>
          <span>Measurement ≠ Edge</span>
          <span>Candle path ≠ Fill</span>
        </span>
      </div>
    </div>
  );
}
