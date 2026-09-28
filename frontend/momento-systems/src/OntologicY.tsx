import { useEffect, useState } from "react";
import { Desk } from "./Desk";

type WindowRow = {
  label?: string;
  count?: number;
  requested?: number;
  game_ids?: string[];
  dates?: string[];
  long_gap?: boolean;
  cross_season?: boolean;
};

type Feature = {
  status?: string;
  missing?: string[];
  derived?: Array<{ name: string; value: string; formula: string; label: string }>;
};

type Game = {
  nba_game_id?: string;
  internal_game_id?: string | null;
  identity_status?: string;
  away?: string;
  home?: string;
  away_name?: string | null;
  home_name?: string | null;
  start_utc?: string | null;
  status?: string;
  season_type?: string;
  period?: number | string | null;
  clock?: string | null;
  away_score?: number | string | null;
  home_score?: number | string | null;
  model_status?: string;
  moneyline?: string;
  spread?: string;
  total?: string;
  quarters?: string;
  home_windows?: { windows?: Record<string, WindowRow> };
  away_windows?: { windows?: Record<string, WindowRow> };
  home_features?: Record<string, Feature>;
  away_features?: Record<string, Feature>;
  prediction_generated_at?: string | null;
};

type Model = {
  model_status?: string;
  model_id?: string;
  reasons?: string[];
  learner?: string;
  feature_set_version?: string;
  joblib_unpickled?: boolean;
  trained_in_process?: boolean;
};

type Market = { market: string; period: string; status: string };

type Board = {
  snapshot_id?: string | null;
  retrieved_at?: string;
  schedule_status?: string;
  log_status?: string;
  earliest_preseason_game_returned?: string | null;
  schedule_completeness?: string;
  five_second_source?: string;
  cadence_reason?: string;
  effective_cadence_seconds?: number;
  prediction_generated_at?: string | null;
  feature_snapshot_at?: string | null;
  source_time?: string;
  last_poll_at?: string | null;
  last_successful_retrieval_at?: string | null;
  last_state_change_at?: string | null;
  model?: Model;
  markets?: Market[];
  games?: Game[];
};

const VIEWS = ["all", "live", "upcoming", "completed"] as const;

function scoreText(game: Game): string {
  if (game.status === "upcoming" || (game.away_score == null && game.home_score == null)) return "—";
  return `${game.away_score ?? "—"}–${game.home_score ?? "—"}`;
}

function WindowList({ title, body }: { title: string; body?: { windows?: Record<string, WindowRow> } }) {
  const windows = body?.windows ?? {};
  const types = Object.keys(windows);
  if (!types.length) return <p className="muted">{title}: no completed games of a single season type before tipoff.</p>;
  return (
    <div>
      <p>{title}</p>
      {types.map((seasonType) => {
        const row = windows[seasonType];
        return (
          <p key={seasonType} className="muted">
            {seasonType} {row.count}/{row.requested} · descriptive only
            {row.long_gap ? " · long offseason gap" : ""}
            {row.cross_season ? " · crosses seasons" : ""}
          </p>
        );
      })}
    </div>
  );
}

export default function OntologicY({ onHome }: { onHome: () => void }) {
  const [board, setBoard] = useState<Board | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState<(typeof VIEWS)[number]>("all");
  const [support, setSupport] = useState<"all" | "unavailable" | "supported">("all");
  const [date, setDate] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      const params = new URLSearchParams();
      if (date) params.set("date", date);
      if (view !== "all") params.set("view", view);
      if (support !== "all") params.set("support", support);
      const query = params.toString();
      try {
        const response = await fetch(`/api/momento/ontologic-y/board${query ? `?${query}` : ""}`, { cache: "no-store" });
        if (!response.ok) throw new Error(`board ${response.status}`);
        const body = (await response.json()) as Board;
        if (!cancelled) {
          setBoard(body);
          setError(null);
        }
      } catch (exc) {
        if (!cancelled) setError((exc as Error).message);
      }
    }
    load();
    const timer = window.setInterval(load, 5000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [date, view, support]);

  const games = board?.games ?? [];
  const selected = games.find((game) => game.nba_game_id === selectedId) ?? null;
  const model = board?.model;

  return (
    <Desk kicker="In House Odds" title="ONTOLOGIC Y" active="bracket" scroll>
      <button type="button" onClick={onHome}>
        Back
      </button>
      <p className="ox-banner">
        Ontologic Y, vanilla in-house baseline, NBA data · XGBoost inference unavailable, analytical breakdown — no
        simulation, execution disabled.
      </p>
      <p className="muted">
        Earliest preseason game returned {board?.earliest_preseason_game_returned ?? "—"}. Schedule completeness{" "}
        {board?.schedule_completeness ?? "UNVERIFIED"}.
      </p>
      <p className="muted">
        Snapshot {board?.snapshot_id ?? "—"} · schedule {board?.schedule_status ?? "—"} · logs {board?.log_status ?? "—"} ·{" "}
        {board?.cadence_reason}
      </p>
      <p className="muted">
        Poll {board?.last_poll_at ?? "—"} · retrieval {board?.last_successful_retrieval_at ?? "—"} · source{" "}
        {board?.source_time ?? "SOURCE_TIME_UNAVAILABLE"} · state change {board?.last_state_change_at ?? "—"} · features{" "}
        {board?.feature_snapshot_at ?? "—"} · prediction {board?.prediction_generated_at ?? "none"}
      </p>
      {error ? <p className="ox-flag">{error}</p> : null}
      <section className="ox-detail">
        <h2>Model</h2>
        <p>
          {model?.model_id ?? "XIB-NBA-V1"} · {model?.model_status ?? "MODEL_INCOMPATIBLE"}
        </p>
        <p className="muted">
          {model?.learner}. Feature set {model?.feature_set_version}. Joblib loaded {String(model?.joblib_unpickled)}. Trained
          here {String(model?.trained_in_process)}.
        </p>
        <ul className="ox-list">
          {(model?.reasons ?? []).map((reason) => (
            <li key={reason}>{reason}</li>
          ))}
        </ul>
      </section>
      <div className="ox-controls">
        {VIEWS.map((item) => (
          <button key={item} type="button" className={view === item ? "is-on" : ""} onClick={() => setView(item)}>
            {item}
          </button>
        ))}
        <button
          type="button"
          className={support === "unavailable" ? "is-on" : ""}
          onClick={() => setSupport(support === "unavailable" ? "all" : "unavailable")}
        >
          unavailable
        </button>
        <button
          type="button"
          className={support === "supported" ? "is-on" : ""}
          onClick={() => setSupport(support === "supported" ? "all" : "supported")}
        >
          supported
        </button>
        <label className="field">
          Date
          <input className="field-input" type="date" value={date} onChange={(event) => setDate(event.target.value)} />
        </label>
      </div>
      <table className="ox-table">
        <thead>
          <tr>
            <th>Matchup</th>
            <th>Start</th>
            <th>State</th>
            <th>Windows</th>
            <th>Model</th>
            <th>Moneyline</th>
            <th>Spread</th>
            <th>Total</th>
          </tr>
        </thead>
        <tbody>
          {games.map((game) => {
            const homeCount = Object.values(game.home_windows?.windows ?? {}).reduce((sum, row) => sum + (row.count ?? 0), 0);
            const awayCount = Object.values(game.away_windows?.windows ?? {}).reduce((sum, row) => sum + (row.count ?? 0), 0);
            return (
              <tr
                key={game.nba_game_id}
                className={selected?.nba_game_id === game.nba_game_id ? "is-on" : ""}
                onClick={() => setSelectedId(game.nba_game_id ?? null)}
              >
                <td>
                  <button type="button" onClick={() => setSelectedId(game.nba_game_id ?? null)}>
                    {game.away} @ {game.home}
                  </button>
                </td>
                <td>{game.start_utc}</td>
                <td>
                  {game.status} {scoreText(game)} {game.period ?? ""} {game.clock ?? ""}
                </td>
                <td>
                  {awayCount}/{homeCount}
                </td>
                <td>{game.model_status}</td>
                <td>{game.moneyline}</td>
                <td>{game.spread}</td>
                <td>{game.total}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {!games.length ? (
        <p className="ox-flag">
          {support === "supported"
            ? "No supported market."
            : board?.schedule_status && board.schedule_status !== "OK"
              ? board.schedule_status
              : "No games in this filter."}
        </p>
      ) : null}
      {selected ? (
        <section className="ox-detail">
          <h2>
            {selected.away_name ?? selected.away} @ {selected.home_name ?? selected.home}
          </h2>
          <p className="muted">
            NBA {selected.nba_game_id} · {selected.identity_status}
            {selected.internal_game_id ? ` · ${selected.internal_game_id}` : ""} · {selected.season_type} · snapshot{" "}
            {board?.snapshot_id}
          </p>
          <p className="muted">
            Score {scoreText(selected)} is display only. Period {selected.period ?? "—"} clock {selected.clock ?? "—"}.
            Prediction time {selected.prediction_generated_at ?? "none"}.
          </p>
          <WindowList title={selected.away ?? "Away"} body={selected.away_windows} />
          <WindowList title={selected.home ?? "Home"} body={selected.home_windows} />
          <p className="muted">Moneyline {selected.moneyline}. Spread {selected.spread}. Total {selected.total}. Quarters {selected.quarters}.</p>
          <table className="ox-table">
            <thead>
              <tr>
                <th>Market</th>
                <th>Period</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {(board?.markets ?? []).map((market) => (
                <tr key={`${market.market}-${market.period}`}>
                  <td>{market.market}</td>
                  <td>{market.period}</td>
                  <td>{market.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      ) : null}
    </Desk>
  );
}
