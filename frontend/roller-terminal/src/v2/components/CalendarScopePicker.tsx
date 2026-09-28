import type { Spec } from "../../researchTypes";
import { asArr, asObj } from "../../researchTypes";
import {
  availableMonths,
  availableSeasons,
  hasCalendarScope,
  toggleInList,
  weeksForMonths,
} from "../calendarScope";

type Props = {
  spec: Spec;
  setSpec: (spec: Spec | ((s: Spec) => Spec)) => void;
  locked: boolean;
};

export default function CalendarScopePicker({ spec, setSpec, locked }: Props) {
  const pop = asObj(spec.population_binding);
  const leagues = asArr(pop.leagues) as string[];
  const seasons = asArr(pop.seasons) as string[];
  const months = asArr(pop.season_months) as string[];
  const weeks = asArr(pop.season_weeks) as string[];

  const seasonOptions = availableSeasons(leagues);
  const monthOptions = availableMonths(seasons, leagues);
  const weekOptions = weeksForMonths(months.length ? months : monthOptions).slice(0, 60);

  const setField = (key: "seasons" | "season_months" | "season_weeks", value: string[]) => {
    setSpec((prev) => {
      const nextPop = { ...asObj(prev.population_binding), [key]: value };
      // Drop weeks outside selected months; drop months outside seasons
      if (key === "seasons") {
        const allowedMonths = availableMonths(value, leagues);
        nextPop.season_months = (asArr(nextPop.season_months) as string[]).filter((m) =>
          allowedMonths.includes(m),
        );
        const allowedWeeks = weeksForMonths(nextPop.season_months as string[]);
        nextPop.season_weeks = (asArr(nextPop.season_weeks) as string[]).filter((w) =>
          allowedWeeks.includes(w),
        );
      }
      if (key === "season_months") {
        const allowedWeeks = weeksForMonths(value);
        nextPop.season_weeks = (asArr(nextPop.season_weeks) as string[]).filter((w) =>
          allowedWeeks.includes(w),
        );
      }
      return { ...prev, population_binding: nextPop };
    });
  };

  const clear = () => {
    setSpec((prev) => ({
      ...prev,
      population_binding: {
        ...asObj(prev.population_binding),
        seasons: [],
        season_months: [],
        season_weeks: [],
      },
    }));
  };

  return (
    <div className="ws-calendar-scope">
      <div className="v2-kicker">Season scope</div>
      <p className="muted small">
        Season / month / week universe filters are recorded on the research_spec. They are{" "}
        <strong>STRUCTURAL</strong> until an authoritative population route applies them — Run stays
        gated while any are set.
      </p>
      {locked ? (
        <p className="notice">
          Locked FIRST80 / NCAAB membership does not accept calendar filters. Clear scope or use a
          blank / configurable study.
        </p>
      ) : null}

      <div className="ws-calendar-block">
        <div className="muted small">Season</div>
        <div className="chip-row">
          {seasonOptions.map((s) => (
            <button
              key={s}
              type="button"
              className={seasons.includes(s) ? "chip on" : "chip"}
              disabled={locked}
              onClick={() => setField("seasons", toggleInList(seasons, s))}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      <div className="ws-calendar-block">
        <div className="muted small">Season month</div>
        {!seasons.length ? (
          <p className="muted small">Select a season first.</p>
        ) : (
          <div className="chip-row">
            {monthOptions.map((m) => (
              <button
                key={m}
                type="button"
                className={months.includes(m) ? "chip on" : "chip"}
                disabled={locked}
                onClick={() => setField("season_months", toggleInList(months, m))}
              >
                {m}
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="ws-calendar-block">
        <div className="muted small">Season week (ISO)</div>
        {!months.length && !seasons.length ? (
          <p className="muted small">Select season months to list weeks.</p>
        ) : (
          <details className="ws-week-details">
            <summary>
              {weeks.length ? `${weeks.length} week(s) selected` : "Choose weeks"} ·{" "}
              {weekOptions.length} available
            </summary>
            <div className="chip-row ws-week-row">
              {weekOptions.map((w) => (
                <button
                  key={w}
                  type="button"
                  className={weeks.includes(w) ? "chip on" : "chip"}
                  disabled={locked}
                  onClick={() => setField("season_weeks", toggleInList(weeks, w))}
                >
                  {w}
                </button>
              ))}
            </div>
          </details>
        )}
      </div>

      {hasCalendarScope(pop) ? (
        <button type="button" className="btn-secondary" onClick={clear}>
          Clear season scope
        </button>
      ) : null}
    </div>
  );
}
