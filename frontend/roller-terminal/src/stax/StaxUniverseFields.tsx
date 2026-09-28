import { catalogByKind } from "../v2/catalog/availabilityCatalog";
import Bubble from "../v2/workflow/Bubble";
import { toggleIn, updateUniverse } from "../v2/workflow/draft";
import { dateRangeForSelections } from "../v2/workflow/seasonDates";
import {
  clearIncompatiblePeriods,
  clearIncompatibleTeState,
  familyOf,
  selectSportFamily,
  type SportFamily,
} from "../v2/workflow/sportFamily";
import type { WorkflowDraft } from "../v2/workflow/types";

type Props = {
  draft: WorkflowDraft;
  locked?: boolean;
  onChange: (next: WorkflowDraft) => void;
};

export default function StaxUniverseFields({ draft, locked, onChange }: Props) {
  const u = draft.universe;
  const sports = catalogByKind("sport");
  const leagues = catalogByKind("league").filter(
    (l) => !l.sports?.length || l.sports.some((s) => u.sports.includes(s)) || u.sports.length === 0,
  );
  const seasons = catalogByKind("season");
  const markets = catalogByKind("market");
  const marketData = catalogByKind("market_data");
  const pbp = catalogByKind("pbp");
  const baseballOn = u.sports.includes("baseball") || u.leagues.includes("MLB");
  const tennisOn = u.sports.includes("tennis");

  const applyFamily = (id: string) => {
    const fam = familyOf(id) as SportFamily;
    const nextU = selectSportFamily(u, id);
    const nextSeasons =
      (fam === "baseball" || fam === "tennis") && !nextU.seasons.length ? ["2025-26"] : nextU.seasons;
    const range = dateRangeForSelections(nextU.leagues, nextSeasons);
    onChange({
      ...updateUniverse(draft, {
        sports: nextU.sports,
        leagues: nextU.leagues,
        seasons: nextSeasons,
        markets: nextU.markets.length ? nextU.markets : ["kalshi"],
        marketData: nextU.marketData,
        dateFrom: range.dateFrom,
        dateTo: range.dateTo,
      }),
      entryConditions: draft.entryConditions.map((e) => clearIncompatiblePeriods(e, fam)),
      teFilters: clearIncompatibleTeState(draft.teFilters, fam),
    });
  };

  const setList = (key: "sports" | "leagues" | "seasons" | "markets" | "marketData" | "dataSources", id: string) => {
    if (locked) return;
    if (key === "sports" || key === "leagues") {
      applyFamily(id);
      return;
    }
    if (key === "seasons") {
      const next = toggleIn(u.seasons, id);
      const range = dateRangeForSelections(u.leagues, next);
      onChange(updateUniverse(draft, { seasons: next, dateFrom: range.dateFrom, dateTo: range.dateTo }));
      return;
    }
    if (key === "marketData") {
      if (id === "tick" || id === "l2") return;
      if (id === "last_trade") {
        onChange(updateUniverse(draft, { marketData: toggleIn(u.marketData.filter((x) => x !== "candles"), "last_trade") }));
        return;
      }
      if (id === "candles") {
        onChange(updateUniverse(draft, { marketData: toggleIn(u.marketData.filter((x) => x !== "last_trade"), "candles") }));
        return;
      }
    }
    onChange(updateUniverse(draft, { [key]: toggleIn(u[key], id) }));
  };

  return (
    <div className="stax-universe-fields">
      <div className="stax-field-row">
        <span>Sport</span>
        <div className="ws-chip-row">
          {sports.map((item) => (
            <Bubble key={item.id} item={item} selected={u.sports.includes(item.id)} onToggle={() => setList("sports", item.id)} />
          ))}
        </div>
      </div>
      <div className="stax-field-row">
        <span>League</span>
        <div className="ws-chip-row">
          {leagues.map((item) => (
            <Bubble key={item.id} item={item} selected={u.leagues.includes(item.id)} onToggle={() => setList("leagues", item.id)} />
          ))}
        </div>
      </div>
      <div className="stax-field-row">
        <span>Season</span>
        <div className="ws-chip-row">
          {seasons.map((item) => (
            <Bubble key={item.id} item={item} selected={u.seasons.includes(item.id)} onToggle={() => setList("seasons", item.id)} />
          ))}
        </div>
      </div>
      <div className="stax-field-row">
        <span>Market</span>
        <div className="ws-chip-row">
          {markets.map((item) => (
            <Bubble key={item.id} item={item} selected={u.markets.includes(item.id)} onToggle={() => setList("markets", item.id)} />
          ))}
        </div>
      </div>
      <div className="stax-field-row">
        <span>Market data</span>
        <div className="ws-chip-row">
          {marketData.map((item) => (
            <Bubble
              key={item.id}
              item={item}
              selected={u.marketData.includes(item.id)}
              disabled={item.id === "tick" || item.id === "l2"}
              onToggle={() => setList("marketData", item.id)}
            />
          ))}
        </div>
      </div>
      <div className="stax-field-row">
        <span>Game data</span>
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
      </div>
      <div className="stax-field-row">
        <span>Timeframe</span>
        <div className="stax-date-row">
          <input
            type="date"
            value={u.dateFrom ?? ""}
            disabled={locked}
            onChange={(e) => onChange(updateUniverse(draft, { dateFrom: e.target.value || undefined }))}
          />
          <span className="muted">→</span>
          <input
            type="date"
            value={u.dateTo ?? ""}
            disabled={locked}
            onChange={(e) => onChange(updateUniverse(draft, { dateTo: e.target.value || undefined }))}
          />
        </div>
      </div>
      {tennisOn ? (
        <p className="muted small">
          Tennis match-winner · tradable yes_bid. SEQUENCE-ONLY PBP is not a PIT snap.
        </p>
      ) : null}
      {baseballOn ? <p className="muted small">LAST TRADE ≠ YES BID. CANDLE/PRINT PATH ≠ FILL.</p> : null}
    </div>
  );
}
