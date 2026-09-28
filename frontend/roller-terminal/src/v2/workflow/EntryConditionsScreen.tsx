import { useState } from "react";
import { catalogByKind, catalogItem } from "../catalog/availabilityCatalog";
import { GRID_CENTS } from "../vocabulary/normalize";
import Bubble, { AvailabilityNote } from "./Bubble";
import {
  duplicateEntry,
  isOneTradePerGame,
  newConditionId,
  setEntryConditions,
  setOneTradePerGame,
  setTeFilters,
} from "./draft";
import {
  MLB_INNINGS,
  NBA_4MIN,
  NBA_PERIODS,
  NCAAB_10MIN,
  NCAAB_5MIN,
  NCAAB_PERIODS,
  TENNIS_GAMES,
  TENNIS_SETS,
  chipSelectedIn,
  commitWindows,
  toggleWindow,
  windowsFromEntry,
  type PeriodChip,
} from "./periodPartitions";
import { entrySummary } from "./questionFromDraft";
import { isBaseballFamily, isTennisFamily } from "./sportFamily";
import type {
  EntryCondition,
  EntryFamily,
  TeAbsDiff,
  TeFilters,
  TeRunners,
  TeScoreSide,
  TeTennisEventState,
  TeTennisLeadFilter,
  TeTennisPointScore,
  TeTennisServe,
  WorkflowDraft,
} from "./types";

const ENTRY_GROUPS: Array<{ title: string; ids: EntryFamily[] }> = [
  { title: "TOUCH", ids: ["first_touch", "second_touch", "third_touch", "fourth_touch", "nth_touch"] },
  { title: "CROSSING", ids: ["cross", "break"] },
  { title: "REVERSAL", ids: ["reversion", "bounce", "recovery"] },
  { title: "STATE", ids: ["above", "below"] },
  { title: "EXTREMUM", ids: ["maximum_touch", "minimum_touch"] },
];

const DIRECTION_FAMS = new Set(["cross", "break", "reversion", "bounce", "recovery"]);

type Props = {
  draft: WorkflowDraft;
  onChange: (next: WorkflowDraft) => void;
  onBack: () => void;
  onEnter: () => void;
};

function blankEntry(family: EntryFamily): EntryCondition {
  return { id: newConditionId("entry"), family };
}

const TENNIS_POINT_SCORES: Array<{ id: TeTennisPointScore; label: string }> = [
  { id: "0-0", label: "0–0" },
  { id: "15-0", label: "15–0" },
  { id: "30-0", label: "30–0" },
  { id: "40-0", label: "40–0" },
  { id: "15-15", label: "15–15" },
  { id: "30-30", label: "30–30" },
  { id: "40-40", label: "40–40" },
  { id: "DEUCE", label: "Deuce" },
  { id: "ADVANTAGE", label: "Advantage" },
];

const TENNIS_SERVE: Array<{ id: TeTennisServe; label: string }> = [
  { id: "serving", label: "YES serving" },
  { id: "returning", label: "YES returning" },
];

const TENNIS_EVENT_STATES: Array<{ id: TeTennisEventState; label: string }> = [
  { id: "break_point", label: "Break point" },
  { id: "set_point", label: "Set point" },
  { id: "match_point", label: "Match point" },
  { id: "tiebreak", label: "Tiebreak" },
];

const TENNIS_PBP_NOTE =
  "Tennis PBP is sequence-only (pit_joinable = false). Point-level state covers roughly 6% of tennis markets and is not point-in-time joinable.";

function periodGroups(
  leagues: string[],
  baseball: boolean,
  tennis: boolean,
): Array<{ title: string; chips: PeriodChip[] }> {
  if (tennis) {
    return [
      { title: "Set (structural entry window)", chips: TENNIS_SETS },
      { title: "Game window (structural entry window)", chips: TENNIS_GAMES },
    ];
  }
  if (baseball) {
    return [
      { title: "MLB innings (T top / B bottom / I either half)", chips: MLB_INNINGS },
    ];
  }
  const nba = [
    { title: "NBA quarters", chips: NBA_PERIODS },
    { title: "NBA 4-minute windows", chips: NBA_4MIN },
  ];
  const ncaab = [
    { title: "NCAAB halves", chips: NCAAB_PERIODS },
    { title: "NCAAB 10-minute windows", chips: NCAAB_10MIN },
    { title: "NCAAB 5-minute windows", chips: NCAAB_5MIN },
  ];
  const ncaabFirst = leagues.includes("NCAAB") && !leagues.includes("NBA");
  return ncaabFirst ? [...ncaab, ...nba] : [...nba, ...ncaab];
}

function toggleExact(current: number[] | undefined, n: number): number[] | undefined {
  const set = new Set(current ?? []);
  if (set.has(n)) set.delete(n);
  else set.add(n);
  const next = [...set].sort((a, b) => a - b);
  return next.length ? next : undefined;
}

function toggleOuts(current: number[] | undefined, n: number): number[] | undefined {
  return toggleExact(current, n);
}

function toggleInList<T extends string>(current: T[] | undefined, id: T): T[] | undefined {
  const set = new Set(current ?? []);
  if (set.has(id)) set.delete(id);
  else set.add(id);
  const next = [...set];
  return next.length ? next : undefined;
}

function patchTennisLead(
  current: TeTennisLeadFilter | undefined,
  patch: Partial<TeTennisLeadFilter>,
): TeTennisLeadFilter | undefined {
  const next = { ...current, ...patch };
  const empty =
    (next.scoreSide == null || next.scoreSide === "any") &&
    !next.exactDiffs?.length &&
    (next.absDiff == null || next.absDiff === "any") &&
    next.customRange?.min == null &&
    next.customRange?.max == null;
  return empty ? undefined : next;
}

export default function EntryConditionsScreen({ draft, onChange, onBack, onEnter }: Props) {
  const families = catalogByKind("entry");
  const [activeId, setActiveId] = useState<string | null>(
    draft.entryConditions[0]?.id ?? null,
  );
  const [pendingAdd, setPendingAdd] = useState(draft.entryConditions.length === 0);
  const [andHelp, setAndHelp] = useState(false);
  const conditions = draft.entryConditions;
  const active = conditions.find((c) => c.id === activeId) ?? null;
  const rangeOn = active?.priceFrom != null || active?.priceTo != null;
  const staticOn = active?.priceCents != null;
  const baseball = isBaseballFamily(draft.universe);
  const tennis = isTennisFamily(draft.universe);
  const groups = periodGroups(draft.universe.leagues, baseball, tennis);
  const te = draft.teFilters ?? {};
  const patchTe = (patch: TeFilters) => onChange(setTeFilters(draft, { ...te, ...patch }));

  const commit = (next: EntryCondition[]) => {
    onChange(setEntryConditions(draft, next));
  };

  const patchActive = (patch: Partial<EntryCondition>) => {
    if (!active) return;
    commit(conditions.map((c) => (c.id === active.id ? { ...c, ...patch } : c)));
  };

  const touchPatch = (family: EntryFamily): Partial<EntryCondition> => {
    if (family === "first_touch") return { family, touchN: 1 };
    if (family === "second_touch") return { family, touchN: 2 };
    if (family === "third_touch") return { family, touchN: 3 };
    if (family === "fourth_touch") return { family, touchN: 4 };
    if (family === "nth_touch") return { family, touchN: "N" };
    return { family };
  };

  const selectFamily = (family: EntryFamily) => {
    if (!active || pendingAdd) {
      const created = { ...blankEntry(family), ...touchPatch(family) };
      commit([...conditions, created]);
      setActiveId(created.id);
      setPendingAdd(false);
      return;
    }
    patchActive(touchPatch(family));
  };

  const addCondition = () => {
    setPendingAdd(true);
    setActiveId(null);
  };

  const selectTouchN = (n: number | "N") => {
    if (n === "N") {
      patchActive({ family: "nth_touch", touchN: "N" });
      return;
    }
    const fam =
      n === 1 ? "first_touch" : n === 2 ? "second_touch" : n === 3 ? "third_touch" : n === 4 ? "fourth_touch" : "nth_touch";
    patchActive({ family: fam, touchN: n, touchNValue: n === 5 ? 5 : undefined });
  };

  const togglePeriod = (chip: PeriodChip) => {
    if (!active) return;
    patchActive(commitWindows(toggleWindow(windowsFromEntry(active), chip)));
  };

  return (
    <div className="ws-flow ws-entry">
      <header className="ws-flow-head">
        <p className="v2-kicker">Entry conditions</p>
        <h1 className="v2-page-title">What event defines the beginning of your research path?</h1>
      </header>

      <div className="ws-entry-workspace">
      <div className="ws-entry-builder">
      <section className="ws-flow-block">
        <h2>Touch / event type</h2>
        {ENTRY_GROUPS.map((group) => (
          <div key={group.title} className="ws-entry-group">
            <h3 className="v2-kicker">{group.title}</h3>
            <div className="ws-chip-row">
              {group.ids.map((id) => {
                const item = families.find((f) => f.id === id);
                if (!item) return null;
                return (
                  <Bubble
                    key={item.id}
                    item={item}
                    selected={!pendingAdd && active?.family === item.id}
                    onToggle={() => selectFamily(item.id as EntryFamily)}
                  />
                );
              })}
            </div>
          </div>
        ))}
        {pendingAdd ? (
          <p className="muted small">Select the event type to add. Nothing is pre-filled.</p>
        ) : null}
        {active && !pendingAdd ? (
          <AvailabilityNote
            availability={catalogItem(active.family, "entry")?.availability ?? "COMING_SOON"}
            note={catalogItem(active.family, "entry")?.note}
          />
        ) : null}
      </section>

      {active && !pendingAdd ? (
        <section className="ws-flow-block">
          <h2>Price</h2>
          <p className="muted small">
            Choose a static trigger or a From–To band. Not both. ROLLER does not assume a fill at the
            trigger. First Touch records the observed close on the crossing bar.
          </p>
          <div className={`ws-chip-row ws-price-grid ${rangeOn ? "is-locked" : ""}`}>
            {GRID_CENTS.map((c) => (
              <button
                key={c}
                type="button"
                className={`ws-bubble ${active.priceCents === c ? "on" : ""}`}
                disabled={rangeOn}
                onClick={() =>
                  patchActive(
                    active.priceCents === c
                      ? { priceCents: undefined, maxEntryCents: undefined }
                      : {
                          priceCents: c,
                          priceFrom: undefined,
                          priceTo: undefined,
                          maxEntryCents:
                            active.maxEntryCents != null && active.maxEntryCents < c
                              ? undefined
                              : active.maxEntryCents,
                        },
                  )
                }
              >
                {String(c).padStart(2, "0")}¢
              </button>
            ))}
          </div>
          <div className={`ws-date-row ${staticOn ? "is-locked" : ""}`}>
            <label>
              From
              <select
                value={active.priceFrom ?? ""}
                disabled={staticOn}
                onChange={(e) =>
                  patchActive({
                    priceFrom: e.target.value ? Number(e.target.value) : undefined,
                    priceCents: undefined,
                    maxEntryCents: undefined,
                  })
                }
              >
                <option value="">—</option>
                {GRID_CENTS.map((c) => (
                  <option key={c} value={c}>
                    {c}¢
                  </option>
                ))}
              </select>
            </label>
            <label>
              To
              <select
                value={active.priceTo ?? ""}
                disabled={staticOn}
                onChange={(e) =>
                  patchActive({
                    priceTo: e.target.value ? Number(e.target.value) : undefined,
                    priceCents: undefined,
                    maxEntryCents: undefined,
                  })
                }
              >
                <option value="">—</option>
                {GRID_CENTS.map((c) => (
                  <option key={c} value={c}>
                    {c}¢
                  </option>
                ))}
              </select>
            </label>
          </div>
          {staticOn ? (
            <>
              <div className="ws-date-row">
                <label>
                  Accept through
                  <select
                    value={active.maxEntryCents ?? ""}
                    onChange={(e) =>
                      patchActive({
                        maxEntryCents: e.target.value ? Number(e.target.value) : undefined,
                      })
                    }
                  >
                    <option value="">No ceiling — take the observed close</option>
                    {Array.from(
                      { length: 96 - (active.priceCents ?? 5) },
                      (_, i) => (active.priceCents ?? 5) + i,
                    ).map((c) => (
                      <option key={c} value={c}>
                        {c}¢
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              <p className="muted small">
                If the trigger is 80¢ and accept through is 89¢, a jump from 79¢ to 81¢ is taken at
                81¢. A jump from 79¢ to 94¢ is a First Touch at 94¢, not an 80¢ fill, and is not
                taken. A later 80-cross on the same market is not a first touch.
              </p>
            </>
          ) : null}
        </section>
      ) : null}

      <section className="ws-flow-block">
        <h2>Exposure</h2>
        <p className="muted small">
          First Touch is the first crossing on that market. One trade per game keeps only the
          earliest of those across both sides of the game.
        </p>
        <div className="ws-chip-row">
          <button
            type="button"
            className={`ws-bubble ${isOneTradePerGame(draft) ? "on" : ""}`}
            onClick={() => onChange(setOneTradePerGame(draft, !isOneTradePerGame(draft)))}
          >
            One trade per game
          </button>
        </div>
      </section>

      {active && !pendingAdd ? (
        <section className="ws-flow-block">
          <h2>Touch</h2>
          <div className="ws-chip-row">
            {[1, 2, 3, 4, 5, "N"].map((n) => (
              <button
                key={String(n)}
                type="button"
                className={`ws-bubble ${
                  n === "N"
                    ? active.family === "nth_touch"
                    : (n === 1 && active.family === "first_touch") ||
                        (n === 2 && active.family === "second_touch") ||
                        (n === 3 && active.family === "third_touch") ||
                        (n === 4 && active.family === "fourth_touch") ||
                        active.touchN === n
                      ? "on"
                      : ""
                }`}
                onClick={() => selectTouchN(n as number | "N")}
              >
                {n}
              </button>
            ))}
          </div>
          {active.touchN === "N" ? (
            <label>
              N =
              <input
                type="number"
                min={1}
                value={active.touchNValue ?? ""}
                onChange={(e) =>
                  patchActive({
                    touchNValue: e.target.value ? Number(e.target.value) : undefined,
                  })
                }
              />
            </label>
          ) : null}
        </section>
      ) : null}

      {active && !pendingAdd ? (
        <section className="ws-flow-block">
          <h2>{tennis ? "Set / game window" : baseball ? "Inning / half" : "Game period"}</h2>
          <p className="muted small">
            {tennis
              ? "Optional structural entry windows. Set and game chips are OR within each group. Multiple groups AND. Custom game range is an alternative to preset game windows."
              : baseball
                ? "Optional. T7 is top of the 7th, B7 bottom, I7 either half. T7 OR B7 means the PIT snap is top or bottom of the 7th — not a basketball clock window. Multiple chips are OR."
                : "Optional. NBA quarters and NCAAB halves / 10-minute / 5-minute windows are all selectable. Multiple windows are OR — the game-level touch must fall in any selected window, not all of them. Two entry conditions stay AND. Click a chip again to remove it. Period is a filter after the game-level nth touch, not a new ordinal inside the window."}
          </p>
          {!baseball && !tennis && !draft.universe.leagues.includes("NCAAB") ? (
            <p className="muted small">
              H1 / 1st 10 apply to NCAAB clocks. Add NCAAB on Quick Start or those chips match
              nothing on an NBA-only universe.
            </p>
          ) : null}
          {groups.map((group) => (
            <div key={group.title} className="ws-period-group">
              <h3 className="ws-period-label">{group.title}</h3>
              <div className="ws-chip-row">
                {group.chips.map((chip) => (
                  <button
                    key={chip.id}
                    type="button"
                    className={`ws-bubble ${
                      chipSelectedIn(chip, windowsFromEntry(active)) ? "on" : ""
                    }`}
                    onClick={() => togglePeriod(chip)}
                  >
                    {chip.label}
                  </button>
                ))}
              </div>
            </div>
          ))}
          {tennis ? (
            <>
              <h3 className="v2-kicker">Custom game range</h3>
              <div className="ws-date-row">
                <label>
                  From game
                  <input
                    type="number"
                    min={1}
                    value={active.gameFrom ?? ""}
                    onChange={(e) =>
                      patchActive({
                        gameFrom: e.target.value ? Number(e.target.value) : undefined,
                      })
                    }
                  />
                </label>
                <label>
                  To game
                  <input
                    type="number"
                    min={1}
                    value={active.gameTo ?? ""}
                    onChange={(e) =>
                      patchActive({
                        gameTo: e.target.value ? Number(e.target.value) : undefined,
                      })
                    }
                  />
                </label>
              </div>
            </>
          ) : null}
          {baseball || tennis ? null : (
            <>
              <h3 className="v2-kicker">Game clock</h3>
              <div className="ws-date-row">
                <label>
                  From
                  <input
                    value={active.clockFrom ?? ""}
                    placeholder="08:00"
                    onChange={(e) => patchActive({ clockFrom: e.target.value || undefined })}
                  />
                </label>
                <label>
                  To
                  <input
                    value={active.clockTo ?? ""}
                    placeholder="04:00"
                    onChange={(e) => patchActive({ clockTo: e.target.value || undefined })}
                  />
                </label>
              </div>
            </>
          )}
        </section>
      ) : null}

      {active && DIRECTION_FAMS.has(active.family) && !pendingAdd && (
        <section className="ws-flow-block">
          <h2>Direction</h2>
          <p className="muted small">
            {active.family === "recovery"
              ? "Standalone Recovery always requires a direction. Equality at P does not invent a side."
              : "Omit for both sides. Up/down restricts the approach."}
          </p>
          <div className="ws-chip-row">
            {(["up", "down"] as const).map((d) => (
              <button
                key={d}
                type="button"
                className={`ws-bubble ${active.direction === d ? "on" : ""}`}
                onClick={() =>
                  patchActive({ direction: active.direction === d ? undefined : d })
                }
              >
                {d}
              </button>
            ))}
          </div>
        </section>
      )}
      </div>

      <aside className="ws-entry-logic">
      <section className="ws-flow-block">
        <h2>
          Live AND logic
          <button
            type="button"
            className="ws-help-icon"
            aria-label="AND logic help"
            aria-expanded={andHelp}
            onClick={() => setAndHelp((v) => !v)}
          >
            ?
          </button>
        </h2>
        {andHelp ? (
          <div className="ws-help-pop">
            <p>AND intersects ticker paths. A AND B is the same as B AND A. Display order is for reading only.</p>
            <p>Example: First Touch 80¢ in Q3 AND First Touch 60¢ — both must occur on the same ticker.</p>
            <p>Period is a filter after the game-level nth touch, not a new ordinal inside a quarter or half.</p>
            <p>Multiple period chips on one condition are OR. Two entry conditions remain AND.</p>
            <p>This list starts empty. Only the condition you select is added.</p>
          </div>
        ) : null}
        <p className="muted small">
          Intersection is on ticker identity. A AND B == B AND A.
        </p>
        {!conditions.length ? (
          <p className="muted">Select an event type to start the sentence.</p>
        ) : (
          <ol className="ws-layer-list">
            {conditions.map((c, i) => (
              <li key={c.id} className={c.id === active?.id && !pendingAdd ? "on" : ""}>
                {i > 0 ? <div className="ws-and">AND</div> : null}
                <div className="ws-layer-card">
                  <button type="button" className="ws-layer-main" onClick={() => { setPendingAdd(false); setActiveId(c.id); }}>
                    {entrySummary({ ...draft, entryConditions: [c] })}
                  </button>
                  <div className="ws-layer-actions">
                    <button type="button" className="v2-text-link" onClick={() => { setPendingAdd(false); setActiveId(c.id); }}>
                      Edit
                    </button>
                    <button
                      type="button"
                      className="v2-text-link"
                      onClick={() => {
                        const copy = duplicateEntry(c);
                        commit([...conditions, copy]);
                        setActiveId(copy.id);
                        setPendingAdd(false);
                      }}
                    >
                      Duplicate
                    </button>
                    <button
                      type="button"
                      className="v2-text-link"
                      onClick={() => {
                        const next = conditions.filter((x) => x.id !== c.id);
                        commit(next);
                        setActiveId(next[next.length - 1]?.id ?? null);
                        setPendingAdd(next.length === 0);
                      }}
                    >
                      Remove
                    </button>
                  </div>
                </div>
              </li>
            ))}
          </ol>
        )}
        <button type="button" className="btn-secondary" onClick={addCondition}>
          + Add condition
        </button>
      </section>
      </aside>
      </div>

      <section className="ws-flow-block ws-te-entry">
        <h2>Base Terminal Efficiency</h2>
        <p className="muted small">
          At the entry bar, ROLLER records game state and market path. Not a model. Not a fill.
          Optional chips below restrict the measured population N. Missing state is excluded, not
          guessed. They do not rewrite Cross / Reach and they are not an exit.
          {tennis
            ? " Tennis point-level filters fail closed on SEQUENCE-ONLY PBP. They do not invent timestamps or join MCP Time to candles."
            : " Missing PIT score is excluded, not guessed."}
        </p>
        {tennis ? (
          <>
            <p className="muted small">{TENNIS_PBP_NOTE}</p>
            <h3 className="v2-kicker">POINT STATE (OR)</h3>
            <div className="ws-chip-row">
              {TENNIS_POINT_SCORES.map(({ id, label }) => (
                <button
                  key={id}
                  type="button"
                  className={`ws-bubble ${(te.tennisPointScores ?? []).includes(id) ? "on" : ""}`}
                  onClick={() =>
                    patchTe({ tennisPointScores: toggleInList(te.tennisPointScores, id) })
                  }
                >
                  {label}
                </button>
              ))}
            </div>
            <h3 className="v2-kicker">SERVE (OR)</h3>
            <div className="ws-chip-row">
              {TENNIS_SERVE.map(({ id, label }) => (
                <button
                  key={id}
                  type="button"
                  className={`ws-bubble ${(te.tennisServe ?? []).includes(id) ? "on" : ""}`}
                  onClick={() => patchTe({ tennisServe: toggleInList(te.tennisServe, id) })}
                >
                  {label}
                </button>
              ))}
            </div>
            <h3 className="v2-kicker">EVENT STATE (OR)</h3>
            <div className="ws-chip-row">
              {TENNIS_EVENT_STATES.map(({ id, label }) => (
                <button
                  key={id}
                  type="button"
                  className={`ws-bubble ${(te.tennisEventStates ?? []).includes(id) ? "on" : ""}`}
                  onClick={() =>
                    patchTe({ tennisEventStates: toggleInList(te.tennisEventStates, id) })
                  }
                >
                  {label}
                </button>
              ))}
            </div>
            {(
              [
                ["tennisSetLead", "SET LEAD", "Set score — games won in current set"],
                ["tennisGameLead", "GAME LEAD", "Game score — points within current game"],
                ["tennisPointLead", "POINT LEAD", "Point differential within current rally context"],
              ] as Array<[keyof TeFilters, string, string]>
            ).map(([key, title, lede]) => {
              const lead = te[key] as TeTennisLeadFilter | undefined;
              return (
                <div key={key} className="ws-period-group">
                  <h3 className="v2-kicker">{title}</h3>
                  <p className="muted small">{lede}</p>
                  <div className="ws-chip-row">
                    {(
                      [
                        ["any", "Any"],
                        ["leading", "Leading"],
                        ["tied", "Tied"],
                        ["trailing", "Trailing"],
                      ] as Array<[TeScoreSide, string]>
                    ).map(([id, label]) => (
                      <button
                        key={id}
                        type="button"
                        className={`ws-bubble ${(lead?.scoreSide ?? "any") === id ? "on" : ""}`}
                        onClick={() =>
                          patchTe({
                            [key]: patchTennisLead(lead, { scoreSide: id }),
                          } as Partial<TeFilters>)
                        }
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                  <div className="ws-chip-row">
                    {[1, 2, 3, 4].map((n) => (
                      <button
                        key={n}
                        type="button"
                        className={`ws-bubble ${(lead?.exactDiffs ?? []).includes(n) ? "on" : ""}`}
                        onClick={() =>
                          patchTe({
                            [key]: patchTennisLead(lead, {
                              exactDiffs: toggleExact(lead?.exactDiffs, n),
                            }),
                          } as Partial<TeFilters>)
                        }
                      >
                        {n}
                      </button>
                    ))}
                  </div>
                  <div className="ws-chip-row">
                    {(
                      [
                        ["any", "Any"],
                        ["1_5", "1–5"],
                        ["6_10", "6–10"],
                        ["11_plus", "11+"],
                      ] as Array<[TeAbsDiff, string]>
                    ).map(([id, label]) => (
                      <button
                        key={id}
                        type="button"
                        className={`ws-bubble ${(lead?.absDiff ?? "any") === id ? "on" : ""}`}
                        onClick={() =>
                          patchTe({
                            [key]: patchTennisLead(lead, { absDiff: id }),
                          } as Partial<TeFilters>)
                        }
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                </div>
              );
            })}
          </>
        ) : (
          <>
            <h3 className="v2-kicker">SCORE STATE</h3>
            <div className="ws-chip-row">
              {(
                [
                  ["any", "Any score"],
                  ["leading", "Leading"],
                  ["tied", "Tied"],
                  ["trailing", "Trailing"],
                ] as Array<[TeScoreSide, string]>
              ).map(([id, label]) => (
                <button
                  key={id}
                  type="button"
                  className={`ws-bubble ${(te.scoreSide ?? "any") === id ? "on" : ""}`}
                  onClick={() => patchTe({ scoreSide: id })}
                >
                  {label}
                </button>
              ))}
            </div>
            <h3 className="v2-kicker">LEAD · exact (OR)</h3>
            <p className="muted small">
              Score side AND magnitude. Exact ∪ preset ∪ custom is OR. Leading exact 1 and 2 means +1
              or +2. Trailing exact 2 means −2. Tied is only 0.
              {baseball ? " MLB point_differential is YES runs − opponent runs." : ""}
            </p>
            <div className="ws-chip-row">
              {[1, 2, 3, 4].map((n) => (
                <button
                  key={n}
                  type="button"
                  className={`ws-bubble ${(te.exactDiffs ?? []).includes(n) ? "on" : ""}`}
                  onClick={() => patchTe({ exactDiffs: toggleExact(te.exactDiffs, n) })}
                >
                  {n}
                </button>
              ))}
            </div>
            <h3 className="v2-kicker">RANGE</h3>
            <div className="ws-chip-row">
              {(
                [
                  ["any", "Any"],
                  ["1_5", "1–5"],
                  ["6_10", "6–10"],
                  ["11_plus", "11+"],
                ] as Array<[TeAbsDiff, string]>
              ).map(([id, label]) => (
                <button
                  key={id}
                  type="button"
                  className={`ws-bubble ${(te.absDiff ?? "any") === id ? "on" : ""}`}
                  onClick={() => patchTe({ absDiff: id })}
                >
                  {label}
                </button>
              ))}
            </div>
            <h3 className="v2-kicker">CUSTOM</h3>
            <div className="ws-date-row">
              <label>
                Min
                <input
                  type="number"
                  min={0}
                  value={te.customRange?.min ?? ""}
                  onChange={(e) =>
                    patchTe({
                      customRange: {
                        ...te.customRange,
                        min: e.target.value ? Number(e.target.value) : undefined,
                      },
                    })
                  }
                />
              </label>
              <label>
                Max
                <input
                  type="number"
                  min={0}
                  value={te.customRange?.max ?? ""}
                  onChange={(e) =>
                    patchTe({
                      customRange: {
                        ...te.customRange,
                        max: e.target.value ? Number(e.target.value) : undefined,
                      },
                    })
                  }
                />
              </label>
            </div>
          </>
        )}
        {baseball ? (
          <>
            <h3 className="v2-kicker">MLB STATE</h3>
            <p className="muted small">
              Top/Bottom is the scoreboard half. YES batting is contract-relative: home YES in the
              bottom or away YES in the top. Missing outs / count / runners fail closed.
            </p>
            <div className="ws-chip-row">
              {(["any", "top", "bottom"] as const).map((id) => (
                <button
                  key={id}
                  type="button"
                  className={`ws-bubble ${(te.half ?? "any") === id ? "on" : ""}`}
                  onClick={() => patchTe({ half: id })}
                >
                  {id === "any" ? "Either half" : id === "top" ? "Top" : "Bottom"}
                </button>
              ))}
            </div>
            <div className="ws-chip-row">
              {(["any", "batting", "pitching"] as const).map((id) => (
                <button
                  key={id}
                  type="button"
                  className={`ws-bubble ${(te.yesBatting ?? "any") === id ? "on" : ""}`}
                  onClick={() => patchTe({ yesBatting: id })}
                >
                  {id === "any" ? "YES either" : id === "batting" ? "YES batting" : "YES pitching"}
                </button>
              ))}
            </div>
            <div className="ws-chip-row">
              {[0, 1, 2].map((n) => (
                <button
                  key={n}
                  type="button"
                  className={`ws-bubble ${(te.outs ?? []).includes(n) ? "on" : ""}`}
                  onClick={() => patchTe({ outs: toggleOuts(te.outs, n) })}
                >
                  {n} out{n === 1 ? "" : "s"}
                </button>
              ))}
            </div>
            <div className="ws-chip-row">
              {["any", "0-0", "3-2", "pitcher_ahead", "hitter_ahead", "even"].map((id) => (
                <button
                  key={id}
                  type="button"
                  className={`ws-bubble ${(te.count ?? "any") === id ? "on" : ""}`}
                  onClick={() => patchTe({ count: id })}
                >
                  {id}
                </button>
              ))}
            </div>
            <div className="ws-chip-row">
              {(
                [
                  "any",
                  "empty",
                  "1st",
                  "2nd",
                  "3rd",
                  "1st+2nd",
                  "1st+3rd",
                  "2nd+3rd",
                  "loaded",
                  "risp",
                  "any_on",
                ] as TeRunners[]
              ).map((id) => (
                <button
                  key={id}
                  type="button"
                  className={`ws-bubble ${(te.runners ?? "any") === id ? "on" : ""}`}
                  onClick={() => patchTe({ runners: id })}
                >
                  {id === "risp" ? "RISP" : id}
                </button>
              ))}
            </div>
          </>
        ) : null}
      </section>

      <footer className="ws-define-footer">
        <div>
          <p className="v2-kicker">Entry condition</p>
          <p className="ws-question">{entrySummary(draft)}</p>
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
