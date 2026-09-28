import { useEffect, useState } from "react";
import { Desk } from "./Desk";

type Side = {
  side: string;
  line?: string | null;
  american: number | string | null;
  raw_display_percent?: string;
  display_percent?: string;
  source_updated_at?: string | null;
  last_quote_change_at?: string | null;
};

type Market = {
  status?: string;
  market_family?: string;
  period?: string;
  settlement?: string;
  line?: string | null;
  main?: boolean;
  overround_points?: string | null;
  conditional_on_no_push?: boolean;
  push_probability?: string | null;
  normalized?: Side[];
};

type Bucket = {
  label: string;
  display_percent?: string;
  unbounded_below?: boolean;
  unbounded_above?: boolean;
};

type Partition = {
  status?: string;
  reason?: string | null;
  buckets?: Bucket[];
  assumptions?: string;
};

type Outcome = {
  market_family?: string;
  market_name?: string | null;
  period?: string;
  participant?: string | null;
  side?: string;
  line?: string | null;
  american?: string | null;
  source_decimal?: string | null;
  decimal_odds?: string | null;
  decimal_discrepancy?: string | null;
  status?: string;
  no_vig_status?: string | null;
  observed_at?: string | null;
  last_seen_at?: string | null;
  source_updated_at?: string | null;
};

type EventCoverage = {
  status?: string;
  groups_discovered?: string[];
  groups_fetched?: string[];
  markets_parsed?: number;
  unmapped_count?: number;
  failures?: string[];
};

type Game = {
  id: string;
  matchup: string;
  start_utc?: string | null;
  status?: string;
  score?: string | null;
  period?: number | string | null;
  clock?: string | null;
  bookmaker?: string | null;
  source_label?: string;
  mapping?: string;
  internal_game_id?: string | null;
  canonical_mapping?: string;
  moneyline?: Market | null;
  main_spread?: Market | null;
  main_total?: Market | null;
  coverage?: string;
  provider_event_id?: string;
  nba_start_utc?: string | null;
  wager_cutoff?: string | null;
  last_seen_at?: string | null;
  outcomes?: Outcome[];
  specialty_outcomes?: Outcome[];
  event_coverage?: EventCoverage | null;
  freshness?: {
    source_time_label?: string;
    source_quote_age?: string;
    observation_age_seconds?: number | null;
    last_quote_change_at?: string | null;
    last_seen_at?: string | null;
    retrieved_at?: string;
    stale?: boolean;
  };
  markets?: Market[];
  history?: Array<{ status?: string; market_family?: string; line?: string | null; side?: string }>;
  margin_partition?: Partition;
  total_partition?: Partition;
  quarters?: Record<string, Partition>;
  coherence?: string[];
  empty_state?: string | null;
  nba?: { nba_game_id?: string; season_type?: string } | null;
};

type Board = {
  snapshot_id?: string;
  retrieved_at?: string;
  method?: string;
  source_label?: string;
  mode?: string;
  cadence_label?: string;
  preseason_start?: string | null;
  preseason_start_source?: string;
  canonical_source?: string;
  games?: Game[];
  empty_state?: string | null;
};

type Health = {
  provider_configured?: boolean;
  live_connectivity?: string;
  five_second_book_freshness?: string;
  cadence_label?: string;
  lease_owner?: string | null;
  last_successful_poll_at?: string | null;
  snapshot_id?: string;
  empty_state?: string | null;
  nba_probe?: { status?: string; preseason_start?: string | null; season?: string; detail?: string | null } | null;
  source_freshness_measured?: boolean;
};

const EMPTY_COPY: Record<string, string> = {
  NO_CREDENTIALS: "No sportsbook credential is configured. The board is a labeled FIXTURE.",
  PRESEASON_NOT_LISTED: "The Odds API has not listed basketball_nba_preseason. A scheduled game stays on the board with no price.",
  WILLIAM_HILL_ABSENT: "William Hill did not return odds for this event. Another book is not substituted.",
  NO_POSTED_ODDS: "No posted odds for this game.",
  UNMATCHED: "This quote did not match one NBA game on team id, home/away, and start.",
  AMBIGUOUS: "More than one NBA game matches this quote. No link was invented.",
  INCOMPLETE: "The complementary pair is incomplete.",
  SUSPENDED: "The posted market is suspended. It stays in history and is off the active board.",
  INCONSISTENT_LADDER: "The ladder is inconsistent. The derived partition is suppressed.",
  SOURCE_UNAVAILABLE: "William Hill is not in the entitled feed.",
  COLLECTION_BLOCKED: "BetOnline refused the public page. The last stored board is unchanged.",
  COLLECTION_FAILED: "BetOnline collection failed. The last stored board is unchanged.",
  TIMESTAMP_SKEW: "The two sides are too far apart in provider time.",
};

function localTime(value?: string | null): string {
  if (!value) return "—";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString();
}

function lineText(market?: Market | null): string {
  if (!market || !market.normalized?.length) return "—";
  return market.normalized
    .map((side) => {
      const line = side.line ?? market.line;
      const prefix = line ? ` ${line}` : "";
      return `${side.side}${prefix} ${side.display_percent ?? side.american ?? "—"}`;
    })
    .join(" / ");
}

function Buckets({ partition }: { partition?: Partition }) {
  const buckets = partition?.buckets ?? [];
  if (partition?.status !== "OK" || buckets.length === 0) {
    return <p className="muted">{partition?.status === "SUPPRESSED" ? partition.reason : "UNAVAILABLE"}</p>;
  }
  return (
    <div>
      <svg className="ox-buckets" viewBox="0 0 360 96" role="img" aria-label="Analytical buckets">
        {buckets.map((bucket, index) => {
          const percent = Number((bucket.display_percent || "0").replace("%", ""));
          const width = Math.max(0, (percent / 100) * 250);
          const y = 8 + index * 28;
          return (
            <g key={bucket.label}>
              <rect x="0" y={y} width={width} height="18" fill="#7dce9a" />
              <text x="258" y={y + 13} fill="#e8e6df" fontSize="10">
                {bucket.display_percent}
              </text>
            </g>
          );
        })}
      </svg>
      <ul className="ox-list">
        {buckets.map((bucket) => (
          <li key={bucket.label}>
            {bucket.label}: {bucket.display_percent}
            {bucket.unbounded_below ? " · unbounded below" : ""}
            {bucket.unbounded_above ? " · unbounded above" : ""}
          </li>
        ))}
      </ul>
    </div>
  );
}

function CoveragePanel({ report }: { report: Record<string, unknown> | null }) {
  if (!report) return null;
  const buckets = (report.buckets ?? {}) as Record<string, { allowance?: number; spent?: number; remaining?: number }>;
  const coverage = (report.coverage ?? {}) as Record<string, Record<string, string>>;
  const costs = (report.illustrative_costs ?? []) as { label?: string; credits?: number; exceeds_october20_allowance?: boolean }[];
  const policy = (report.policy ?? {}) as { name?: string; active?: boolean; detailed_interval_seconds?: number | null };
  return (
    <section className="ox-detail">
      <h2>{String(report.bookmaker) === "betonline" ? "BetOnline collection" : "William Hill coverage"}</h2>
      <p className="muted">
        Shared collector. Book {String(report.bookmaker ?? "williamhill")}. Other books {String(report.other_books ?? "—")}.
        Policy {policy.name ?? "—"} {policy.active ? "active" : "not active"}. Snapshot collection{" "}
        {String(report.snapshot_collection ?? "—")}. Detailed interval {policy.detailed_interval_seconds ?? "not running"}.
        Preseason listed {report.preseason_listed ? "yes" : "no"}. Observed lines {String(report.observed_line_count ?? 0)}.
      </p>
      <p className="muted">{String(report.quoted_versus_modeled ?? "")}</p>
      <table className="ox-table">
        <thead>
          <tr>
            <th>Bucket</th>
            <th>Allowance</th>
            <th>Spent</th>
            <th>Remaining</th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(buckets).map(([name, bucket]) => (
            <tr key={name}>
              <td>{name}</td>
              <td>{bucket.allowance ?? "—"}</td>
              <td>{bucket.spent ?? "—"}</td>
              <td>{bucket.remaining ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {Object.entries(coverage).map(([phase, markets]) => (
        <p key={phase} className="muted">
          {phase}: {Object.values(markets).filter((status) => status === "AVAILABLE").length} available,{" "}
          {Object.values(markets).filter((status) => status !== "AVAILABLE").length} unavailable
        </p>
      ))}
      <ul className="ox-list">
        {costs.map((item) => (
          <li key={item.label}>
            {item.label}: {item.credits} credits{item.exceeds_october20_allowance ? " · exceeds the 20,000 October allowance" : ""}
          </li>
        ))}
      </ul>
    </section>
  );
}

export default function OntologicX({ onHome }: { onHome: () => void }) {
  const [board, setBoard] = useState<Board | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [selected, setSelected] = useState<Game | null>(null);
  const [periodFilter, setPeriodFilter] = useState("all");
  const [familyFilter, setFamilyFilter] = useState("all");
  const [view, setView] = useState("all");
  const [coverage, setCoverage] = useState<Record<string, unknown> | null>(null);
  const [date, setDate] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let stop = false;
    const load = async () => {
      try {
        const params = new URLSearchParams();
        if (date) params.set("date", date);
        if (view !== "all") params.set("view", view);
        const query = params.toString();
        const [boardResponse, healthResponse, coverageResponse] = await Promise.all([
          fetch(`/api/momento/ontologic-x/board${query ? `?${query}` : ""}`, { cache: "no-store" }),
          fetch("/api/momento/ontologic-x/health", { cache: "no-store" }),
          fetch("/api/momento/ontologic-x/coverage", { cache: "no-store" }),
        ]);
        if (!boardResponse.ok) throw new Error(`board ${boardResponse.status}`);
        if (!healthResponse.ok) throw new Error(`health ${healthResponse.status}`);
        const nextBoard = (await boardResponse.json()) as Board;
        const nextHealth = (await healthResponse.json()) as Health;
        const nextCoverage = coverageResponse.ok ? ((await coverageResponse.json()) as Record<string, unknown>) : null;
        if (stop) return;
        setBoard(nextBoard);
        setHealth(nextHealth);
        setCoverage(nextCoverage);
        setError(null);
        setSelected((current) => {
          if (!current) return current;
          return nextBoard.games?.find((game) => game.id === current.id) ?? current;
        });
      } catch (exc) {
        if (!stop) setError(exc instanceof Error ? exc.message : "board unread");
      }
    };
    void load();
    const timer = window.setInterval(() => void load(), 5000);
    return () => {
      stop = true;
      window.clearInterval(timer);
    };
  }, [date, view]);

  async function openGame(game: Game) {
    setPeriodFilter("all");
    setFamilyFilter("all");
    setSelected(game);
    const response = await fetch(`/api/momento/ontologic-x/games/${encodeURIComponent(game.id)}`, { cache: "no-store" });
    if (!response.ok) return;
    setSelected((await response.json()) as Game);
  }

  const games = board?.games ?? [];
  return (
    <Desk kicker="Quad 1 · Fair Odds Modeling" title="Ontologic X" active="bracket" scroll>
      <p className="ox-banner">
        Ontologic X, vanilla sportsbook baseline, proportional no-vig, analytical breakdown — no simulation, execution
        disabled.
      </p>
      <p className="muted">
        {health?.empty_state ? EMPTY_COPY[health.empty_state] : null} Source {board?.source_label ?? "—"}. Cadence{" "}
        {health?.cadence_label ?? "—"}. Live connectivity {health?.live_connectivity ?? "BLOCKED"}. Book freshness{" "}
        {health?.five_second_book_freshness ?? "NOT_CLAIMED"}. Lease {health?.lease_owner ?? "—"}. Snapshot{" "}
        {board?.snapshot_id ?? "—"} retrieved {localTime(board?.retrieved_at)}. Method {board?.method ?? "—"}.
      </p>
      <p className="muted">
        NBA schedule preseason start {board?.preseason_start ?? "—"} ({board?.preseason_start_source ?? "—"}). NBA probe{" "}
        {health?.nba_probe?.status ?? "not run"}
        {health?.nba_probe?.preseason_start ? ` · observed ${health.nba_probe.preseason_start}` : ""}.
      </p>
      {error ? <p className="muted">{error}</p> : null}
      <CoveragePanel report={coverage} />
      <div className="ox-controls">
        <button type="button" onClick={onHome}>
          Bracket
        </button>
        {["all", "live", "upcoming", "completed"].map((item) => (
          <button key={item} type="button" className={view === item ? "is-on" : ""} onClick={() => setView(item)}>
            {item}
          </button>
        ))}
        <label className="field">
          UTC date
          <input className="field-input" type="date" value={date} onChange={(event) => setDate(event.target.value)} />
        </label>
      </div>
      <table className="ox-table">
        <thead>
          <tr>
            <th>Matchup</th>
            <th>Start</th>
            <th>Status</th>
            <th>Score</th>
            <th>Book</th>
            <th>Moneyline</th>
            <th>Spread</th>
            <th>Total</th>
            <th>Coverage</th>
            <th>Freshness</th>
          </tr>
        </thead>
        <tbody>
          {games.map((game) => (
            <tr key={game.id} className={selected?.id === game.id ? "is-on" : ""}>
              <td>
                <button type="button" onClick={() => void openGame(game)}>
                  {game.matchup}
                </button>
              </td>
              <td>{localTime(game.start_utc)}</td>
              <td>{game.status}</td>
              <td>
                {game.score ?? "—"}
                {game.period ? ` · Q${game.period}` : ""}
                {game.clock ? ` ${game.clock}` : ""}
              </td>
              <td>{game.bookmaker ?? "—"}</td>
              <td>{lineText(game.moneyline)}</td>
              <td>{lineText(game.main_spread)}</td>
              <td>{lineText(game.main_total)}</td>
              <td>{game.coverage}</td>
              <td>
                {game.freshness?.observation_age_seconds != null ? `${game.freshness.observation_age_seconds}s observed` : "—"}
                {" · "}
                {game.freshness?.source_quote_age === "KNOWN" ? "source quote age known" : "source quote age unknown"}
                {game.freshness?.stale ? " · stale" : ""}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {games.length === 0 ? (
        <p className="ox-flag">No scheduled game and no William Hill quote is stored.</p>
      ) : null}
      {selected ? (
        <section className="ox-detail">
          <h2>{selected.matchup}</h2>
          <p className="muted">
            NBA {selected.nba?.nba_game_id ?? "—"} · {selected.nba?.season_type ?? "—"} · mapping {selected.mapping} ·
            canonical {selected.canonical_mapping ?? "—"} {selected.internal_game_id ?? ""} · source{" "}
            {selected.source_label} · snapshot {board?.snapshot_id}
          </p>
          {selected.empty_state ? <p className="ox-flag">{EMPTY_COPY[selected.empty_state] ?? selected.empty_state}</p> : null}
          <p className="muted">
            NBA start {localTime(selected.nba_start_utc ?? selected.start_utc)}. Wager cutoff {localTime(selected.wager_cutoff)}.
            Observation age{" "}
            {selected.freshness?.observation_age_seconds != null ? `${selected.freshness.observation_age_seconds}s` : "—"}.
            Source quote age {selected.freshness?.source_quote_age === "KNOWN" ? "known" : "unknown"}.
            {selected.freshness?.stale ? " Stale." : ""}
          </p>
          <p className="muted">
            Coverage {selected.event_coverage?.status ?? selected.coverage ?? "—"}
            {selected.event_coverage
              ? `. Groups fetched ${(selected.event_coverage.groups_fetched ?? []).join(", ") || "none"}. Parsed ${selected.event_coverage.markets_parsed ?? 0}. Unmapped ${selected.event_coverage.unmapped_count ?? 0}. Failures ${(selected.event_coverage.failures ?? []).join(", ") || "none"}.`
              : ""}
          </p>
          <p className="muted">Coherence {(selected.coherence ?? []).join(", ") || "—"}</p>
          <h3>Moneyline</h3>
          {selected.moneyline?.normalized?.length ? (
            <ul className="ox-list">
              {selected.moneyline.normalized.map((side) => (
                <li key={side.side}>
                  {side.side} American {side.american} · raw {side.raw_display_percent} · normalized {side.display_percent} ·
                  source {side.source_updated_at ?? "SOURCE_TIME_UNAVAILABLE"}
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">No normalized moneyline.</p>
          )}
          <p className="muted">Overround {selected.moneyline?.overround_points ?? "—"} points.</p>
          <h3>Markets</h3>
          <table className="ox-table">
            <thead>
              <tr>
                <th>Family</th>
                <th>Period</th>
                <th>Line</th>
                <th>Status</th>
                <th>Settlement</th>
                <th>Normalized</th>
              </tr>
            </thead>
            <tbody>
              {(selected.markets ?? []).map((market, index) => (
                <tr key={`${market.market_family}-${market.line}-${index}`}>
                  <td>{market.market_family}</td>
                  <td>{market.period}</td>
                  <td>{market.line ?? "—"}</td>
                  <td>
                    {market.status}
                    {market.conditional_on_no_push ? ` · push ${market.push_probability}` : ""}
                  </td>
                  <td>{market.settlement}</td>
                  <td>{lineText(market)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <h3>All inspected outcomes</h3>
          <p className="muted">
            <label>
              Period{" "}
              <select value={periodFilter} onChange={(event) => setPeriodFilter(event.target.value)}>
                <option value="all">All</option>
                {[...new Set((selected.outcomes ?? []).map((row) => row.period || "game"))].map((period) => (
                  <option key={period} value={period}>
                    {period}
                  </option>
                ))}
              </select>
            </label>{" "}
            <label>
              Market{" "}
              <select value={familyFilter} onChange={(event) => setFamilyFilter(event.target.value)}>
                <option value="all">All</option>
                {[...new Set((selected.outcomes ?? []).map((row) => row.market_family || "market"))].map((family) => (
                  <option key={family} value={family}>
                    {family}
                  </option>
                ))}
              </select>
            </label>
          </p>
          <table className="ox-table">
            <thead>
              <tr>
                <th>Market</th>
                <th>Period</th>
                <th>Participant</th>
                <th>Side</th>
                <th>Line</th>
                <th>American</th>
                <th>Source decimal</th>
                <th>Status</th>
                <th>Last seen</th>
              </tr>
            </thead>
            <tbody>
              {(selected.outcomes ?? [])
                .filter((row) => periodFilter === "all" || row.period === periodFilter)
                .filter((row) => familyFilter === "all" || row.market_family === familyFilter)
                .map((row, index) => (
                  <tr key={`${row.market_name}-${row.period}-${row.side}-${row.line}-${index}`}>
                    <td>{row.market_name ?? row.market_family}</td>
                    <td>{row.period}</td>
                    <td>{row.participant ?? "—"}</td>
                    <td>{row.side}</td>
                    <td>{row.line ?? "—"}</td>
                    <td>{row.american ?? "—"}</td>
                    <td>
                      {row.source_decimal ?? "—"}
                      {row.decimal_discrepancy ? ` · rounding ${row.decimal_discrepancy}` : ""}
                    </td>
                    <td>{row.status}</td>
                    <td>{localTime(row.last_seen_at)}</td>
                  </tr>
                ))}
            </tbody>
          </table>
          <h3>Player and specialty markets</h3>
          <p className="muted">These are not a substitute for the full-game win probability.</p>
          {(selected.specialty_outcomes ?? []).length ? (
            <table className="ox-table">
              <thead>
                <tr>
                  <th>Market</th>
                  <th>Participant</th>
                  <th>Side</th>
                  <th>Line</th>
                  <th>American</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {(selected.specialty_outcomes ?? []).map((row, index) => (
                  <tr key={`${row.market_name}-${row.participant}-${index}`}>
                    <td>{row.market_name}</td>
                    <td>{row.participant ?? "—"}</td>
                    <td>{row.side}</td>
                    <td>{row.line ?? "—"}</td>
                    <td>{row.american ?? "—"}</td>
                    <td>{row.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="muted">No player or specialty market was in the inspected groups.</p>
          )}
          <h3>Margin partition</h3>
          <Buckets partition={selected.margin_partition} />
          <h3>Total partition</h3>
          <Buckets partition={selected.total_partition} />
          <h3>Quarters</h3>
          <ul className="ox-list">
            {["Q1", "Q2", "Q3", "Q4"].map((quarter) => (
              <li key={quarter}>
                {quarter}: {selected.quarters?.[quarter]?.status ?? "UNAVAILABLE"}
              </li>
            ))}
          </ul>
          {(selected.history ?? []).length ? (
            <p className="muted">
              History holds {(selected.history ?? []).length} inactive quote{(selected.history ?? []).length === 1 ? "" : "s"},
              including suspended and withdrawn prices.
            </p>
          ) : null}
          <p className="muted">{selected.margin_partition?.assumptions}</p>
        </section>
      ) : (
        <p className="muted">Select a game for the analytical breakdown.</p>
      )}
    </Desk>
  );
}
