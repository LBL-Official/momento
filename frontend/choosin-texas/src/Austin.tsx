import { useEffect, useMemo, useState } from "react";
import { UniverseError, fetchAustin, fetchAustinMoments, fetchAustinReplay, postAustinHistorical, postAustinQuery } from "./api";
import { text } from "./text";
import type { AustinCoverage, AustinNeighbor, AustinQueryResult, AustinReplay } from "./types";

type FormState = {
  side: string;
  query_mode: string;
  entry_price_cents: string;
  current_price_cents: string;
  home_score_entry: string;
  away_score_entry: string;
  home_score_current: string;
  away_score_current: string;
  entry_quarter: string;
  current_quarter: string;
  entry_seconds_remaining: string;
  current_seconds_remaining: string;
  trade_id: string;
  snapshot_id: string;
};

type GameRow = {
  internal_game_id: string;
  game_date?: string;
  home_team_id?: string;
  away_team_id?: string;
  home_team_name?: string;
  away_team_name?: string;
  in_austin_604?: boolean;
};

const EMPTY: FormState = {
  side: "home",
  query_mode: "POST_80",
  entry_price_cents: "80",
  current_price_cents: "42",
  home_score_entry: "58",
  away_score_entry: "56",
  home_score_current: "71",
  away_score_current: "64",
  entry_quarter: "3",
  current_quarter: "3",
  entry_seconds_remaining: "480",
  current_seconds_remaining: "258",
  trade_id: "",
  snapshot_id: "",
};

function Row({ label, value }: { label: string; value: unknown }) {
  return (
    <div className="row">
      <dt>{label}</dt>
      <dd>{text(value)}</dd>
    </div>
  );
}

function num(raw: string): number | null {
  if (raw.trim() === "") return null;
  const n = Number(raw);
  return Number.isFinite(n) ? n : null;
}

function applyForm(src: Record<string, unknown> | null | undefined): FormState {
  if (!src) return EMPTY;
  return {
    side: String(src.side || "home"),
    query_mode: String(src.query_mode || "POST_80"),
    entry_price_cents: src.entry_price_cents == null ? "" : String(src.entry_price_cents),
    current_price_cents: src.current_price_cents == null ? "" : String(src.current_price_cents),
    home_score_entry: src.home_score_entry == null ? "" : String(src.home_score_entry),
    away_score_entry: src.away_score_entry == null ? "" : String(src.away_score_entry),
    home_score_current: src.home_score_current == null ? "" : String(src.home_score_current),
    away_score_current: src.away_score_current == null ? "" : String(src.away_score_current),
    entry_quarter: src.entry_quarter == null ? "" : String(src.entry_quarter),
    current_quarter: src.current_quarter == null ? "" : String(src.current_quarter),
    entry_seconds_remaining: src.entry_seconds_remaining == null ? "" : String(src.entry_seconds_remaining),
    current_seconds_remaining: src.current_seconds_remaining == null ? "" : String(src.current_seconds_remaining),
    trade_id: src.trade_id == null ? "" : String(src.trade_id),
    snapshot_id: src.snapshot_id == null ? "" : String(src.snapshot_id),
  };
}

export default function Austin() {
  const [dataset, setDataset] = useState<Record<string, unknown> | null>(null);
  const [pca, setPca] = useState<Record<string, unknown> | null>(null);
  const [validation, setValidation] = useState<Record<string, unknown> | null>(null);
  const [hedge, setHedge] = useState<Record<string, unknown> | null>(null);
  const [sizing, setSizing] = useState<Record<string, unknown> | null>(null);
  const [lab, setLab] = useState<Record<string, unknown> | null>(null);
  const [audit, setAudit] = useState<Record<string, unknown> | null>(null);
  const [games, setGames] = useState<GameRow[]>([]);
  const [gameFilter, setGameFilter] = useState("");
  const [gameId, setGameId] = useState("");
  const [momentTs, setMomentTs] = useState("");
  const [marks, setMarks] = useState<{ label: string; timestamp_utc: string; price_cents?: number }[]>([]);
  const [ladder, setLadder] = useState<{ label: string; price?: number; ev?: number | null }[]>([]);
  const [form, setForm] = useState<FormState>(EMPTY);
  const [result, setResult] = useState<AustinQueryResult | null>(null);
  const [replay, setReplay] = useState<AustinReplay | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancel = false;
    Promise.all([
      fetchAustin<Record<string, unknown>>("dataset"),
      fetchAustin<Record<string, unknown>>("pca"),
      fetchAustin<Record<string, unknown>>("validation"),
      fetchAustin<Record<string, unknown>>("hedge"),
      fetchAustin<Record<string, unknown>>("sizing"),
      fetchAustin<Record<string, unknown>>("lab"),
      fetchAustin<Record<string, unknown>>("audit"),
      fetchAustin<Record<string, unknown>>("example"),
      fetchAustin<{ games?: GameRow[] }>("games"),
    ])
      .then(([ds, pc, val, hg, sz, lb, au, ex, gm]) => {
        if (cancel) return;
        setDataset(ds);
        setPca(pc);
        setValidation(val);
        setHedge(hg);
        setSizing(sz);
        setLab(lb);
        setAudit(au);
        const fixtures = (ex.fixtures || {}) as Record<string, Record<string, unknown>>;
        setForm(applyForm((fixtures.post80_42 || ex) as Record<string, unknown>));
        setGames(gm.games || []);
      })
      .catch((err: unknown) => {
        if (!cancel) setError(err instanceof UniverseError ? err.message : String(err));
      });
    return () => {
      cancel = true;
    };
  }, []);

  const coverage = (dataset?.coverage || {}) as AustinCoverage;
  const match = result?.match;
  const neighbors = match?.neighbors || [];
  const cal = (sizing?.calibration || {}) as {
    status?: string;
    reason?: string;
    table?: { band?: string; n?: number; realized_PNL?: number; recommended_band?: number; knn_ev_lo?: number; knn_ev_hi?: number }[];
  };
  const resolution = ((hedge as { resolution?: Record<string, unknown> } | null)?.resolution ||
    coverage) as Record<string, unknown>;

  const filteredGames = useMemo(() => {
    const q = gameFilter.trim().toLowerCase();
    const rows = !q
      ? games
      : games.filter((g) =>
          [g.internal_game_id, g.game_date, g.home_team_id, g.away_team_id, g.home_team_name, g.away_team_name]
            .join(" ")
            .toLowerCase()
            .includes(q),
        );
    return rows.slice(0, 80);
  }, [games, gameFilter]);

  async function onMatch() {
    setBusy(true);
    setError(null);
    setReplay(null);
    try {
      const payload = await postAustinQuery({
        side: form.side,
        query_mode: form.query_mode,
        query_source: "MANUAL",
        entry_price_cents: form.query_mode === "PRE_80" ? null : num(form.entry_price_cents),
        current_price_cents: num(form.current_price_cents),
        home_score_entry: num(form.home_score_entry),
        away_score_entry: num(form.away_score_entry),
        home_score_current: num(form.home_score_current),
        away_score_current: num(form.away_score_current),
        entry_quarter: num(form.entry_quarter),
        current_quarter: num(form.current_quarter),
        entry_seconds_remaining: num(form.entry_seconds_remaining),
        current_seconds_remaining: num(form.current_seconds_remaining),
        trade_id: form.trade_id || null,
        snapshot_id: form.snapshot_id || null,
      });
      setResult(payload);
    } catch (err) {
      setError(err instanceof UniverseError ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function onReplayLadder() {
    if (!gameId || !marks.length) {
      setError("Select a warehouse game with 1m marks first.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const rows: { label: string; price?: number; ev?: number | null }[] = [];
      for (const mark of marks) {
        const payload = await postAustinHistorical({
          internal_game_id: gameId,
          side: form.side,
          query_mode: form.query_mode === "PRE_80" ? "POST_80" : form.query_mode,
          timestamp_utc: mark.timestamp_utc,
        });
        const cents = payload.conditional_ev?.conditional_ev_cents;
        rows.push({
          label: mark.label,
          price: mark.price_cents,
          ev: typeof cents === "number" ? cents : null,
        });
      }
      setLadder(rows);
    } catch (err) {
      setError(err instanceof UniverseError ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function onLoadMoment() {
    if (!gameId) {
      setError("Select a warehouse game first.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const payload = await postAustinHistorical({
        internal_game_id: gameId,
        side: form.side,
        query_mode: form.query_mode,
        timestamp_utc: momentTs || undefined,
        quarter: num(form.current_quarter),
        seconds_remaining: num(form.current_seconds_remaining),
      });
      setResult(payload);
      if (payload.form) setForm(applyForm(payload.form));
    } catch (err) {
      setError(err instanceof UniverseError ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function onNeighbor(row: AustinNeighbor) {
    if (!row.trade_id) return;
    try {
      setReplay(await fetchAustinReplay(row.trade_id));
    } catch (err) {
      setError(err instanceof UniverseError ? err.message : String(err));
    }
  }

  const points = useMemo(() => {
    const raw = (pca?.points as { pc1?: number; pc2?: number; settlement?: string }[]) || [];
    if (!raw.length) return [];
    const xs = raw.map((p) => Number(p.pc1 || 0));
    const ys = raw.map((p) => Number(p.pc2 || 0));
    const minX = Math.min(...xs);
    const maxX = Math.max(...xs);
    const minY = Math.min(...ys);
    const maxY = Math.max(...ys);
    const dx = maxX - minX || 1;
    const dy = maxY - minY || 1;
    return raw.map((p) => ({
      ...p,
      x: ((Number(p.pc1 || 0) - minX) / dx) * 100,
      y: (1 - (Number(p.pc2 || 0) - minY) / dy) * 100,
    }));
  }, [pca]);

  const ev = result?.conditional_ev || {};
  const support = result?.support || {};
  const dist = result?.distribution || {};
  const change = result?.state_change || {};

  return (
    <div>
      {error ? <div className="banner is-bad">{error}</div> : null}
      <div className="page-meta">
        <span className="pill">AUSTIN · CONDITIONAL EV QUERY DESK</span>
        <span className="pill">DATA MODE · HISTORICAL QUERY</span>
        <span className="pill">LIVE FEED · UNAVAILABLE</span>
        <span className="pill">EXECUTION · DISABLED</span>
        <span className="pill">TRAINING N=604 · QUERY GAMES ≠ TRAINING N</span>
        <span className="pill">CANDLE PATH ≠ FILL</span>
        <a className="pill" href="http://127.0.0.1:5191/">
          DRE
        </a>
      </div>
      <div className="stat-row" style={{ marginTop: 18 }}>
        <div className="stat">
          <dt>N trades</dt>
          <dd>{text(coverage.n_trades)}</dd>
        </div>
        <div className="stat">
          <dt>path complete</dt>
          <dd>{text(coverage.n_path_complete)}</dd>
        </div>
        <div className="stat">
          <dt>path partial</dt>
          <dd>{text(coverage.n_path_partial)}</dd>
        </div>
        <div className="stat">
          <dt>path unavailable</dt>
          <dd>{text(coverage.n_path_unavailable)}</dd>
        </div>
        <div className="stat">
          <dt>KNN observations</dt>
          <dd>{text(coverage.n_knn_observations)}</dd>
        </div>
      </div>
      <p className="muted">{text(dataset?.note)}</p>

      <div className="grid">
        <article>
          <h2>Query game</h2>
          <p className="muted">Warehouse NBA games. in_austin_604 is a flag, not a filter.</p>
          <label className="row">
            <dt>filter</dt>
            <dd>
              <input value={gameFilter} onChange={(e) => setGameFilter(e.target.value)} placeholder="MIA, date, id" />
            </dd>
          </label>
          <label className="row">
            <dt>game</dt>
            <dd>
              <select
                value={gameId}
                onChange={(e) => {
                  const next = e.target.value;
                  setGameId(next);
                  setMarks([]);
                  setLadder([]);
                  if (!next) return;
                  fetchAustinMoments(next, form.side)
                    .then((payload) => setMarks(payload.marks || []))
                    .catch((err: unknown) => setError(err instanceof UniverseError ? err.message : String(err)));
                }}
              >
                <option value="">select</option>
                {filteredGames.map((g) => (
                  <option key={g.internal_game_id} value={g.internal_game_id}>
                    {g.game_date} {g.away_team_id}@{g.home_team_id}
                    {g.in_austin_604 ? " · 604" : ""}
                  </option>
                ))}
              </select>
            </dd>
          </label>
          <label className="row">
            <dt>timestamp</dt>
            <dd>
              <input value={momentTs} onChange={(e) => setMomentTs(e.target.value)} placeholder="optional ISO UTC" />
            </dd>
          </label>
          <button type="button" onClick={onLoadMoment} disabled={busy}>
            {busy ? "Loading…" : "Load historical moment"}
          </button>
          {marks.length ? (
            <div>
              <p className="muted">
                Ladder prints:{" "}
                {marks.map((m) => (
                  <button
                    key={m.label}
                    type="button"
                    style={{ marginRight: 6 }}
                    onClick={() => {
                      setMomentTs(m.timestamp_utc);
                      setForm({ ...form, current_price_cents: m.price_cents == null ? form.current_price_cents : String(m.price_cents) });
                    }}
                  >
                    {m.label}¢
                  </button>
                ))}
              </p>
              <button type="button" onClick={onReplayLadder} disabled={busy}>
                Replay price ladder
              </button>
            </div>
          ) : null}
        </article>
        <article>
          <h2>Query state</h2>
          <p className="muted">Same pipeline as historical RawState. Query is not training data.</p>
          <label className="row">
            <dt>mode</dt>
            <dd>
              <select value={form.query_mode} onChange={(e) => setForm({ ...form, query_mode: e.target.value })}>
                <option value="PRE_80">PRE_80</option>
                <option value="INTRA_80">INTRA_80</option>
                <option value="POST_80">POST_80</option>
              </select>
            </dd>
          </label>
          <label className="row">
            <dt>side</dt>
            <dd>
              <select value={form.side} onChange={(e) => setForm({ ...form, side: e.target.value })}>
                <option value="home">home</option>
                <option value="away">away</option>
              </select>
            </dd>
          </label>
          {(
            [
              ["entry_price_cents", "entry ¢"],
              ["current_price_cents", "current ¢"],
              ["home_score_entry", "home @ entry"],
              ["away_score_entry", "away @ entry"],
              ["home_score_current", "home now"],
              ["away_score_current", "away now"],
              ["entry_quarter", "entry quarter"],
              ["current_quarter", "current quarter"],
              ["entry_seconds_remaining", "entry clock s"],
              ["current_seconds_remaining", "current clock s"],
            ] as const
          ).map(([key, label]) => (
            <label className="row" key={key}>
              <dt>{label}</dt>
              <dd>
                <input value={form[key]} onChange={(e) => setForm({ ...form, [key]: e.target.value })} />
              </dd>
            </label>
          ))}
          <p className="muted">Optional lookbacks omitted. Velocity stays UNAVAILABLE.</p>
          <button type="button" onClick={onMatch} disabled={busy}>
            {busy ? "Matching…" : "Match"}
          </button>
        </article>
      </div>

      <article className="wide" style={{ marginTop: 14 }}>
        <h2>Derived travels + availability</h2>
        <dl>
          <Row label="price travel" value={result?.derived?.price_travel} />
          <Row label="score travel" value={result?.derived?.score_travel} />
          <Row label="score-diff travel" value={result?.derived?.score_differential_travel} />
          <Row label="time since entry" value={result?.derived?.time_since_entry} />
          <Row label="fee model" value="UNAVAILABLE" />
        </dl>
        <table className="data-table">
          <thead>
            <tr>
              <th>field</th>
              <th>status</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(result?.availability || {})
              .filter(([name]) =>
                [
                  "entry_price_cents",
                  "current_price_cents",
                  "price_travel",
                  "time_since_entry",
                  "score_differential",
                  "score_travel",
                  "seconds_remaining",
                ].includes(name),
              )
              .map(([name, status]) => (
                <tr key={name}>
                  <td>{name}</td>
                  <td>{text(status)}</td>
                </tr>
              ))}
          </tbody>
        </table>
      </article>

      <div className="grid" style={{ marginTop: 14 }}>
        <article>
          <h2>CONDITIONAL EV FROM CURRENT STATE</h2>
          <dl>
            <Row label="EV ¢" value={ev.conditional_ev_cents} />
            <Row label="definition" value={ev.ev_definition} />
            <Row label="formula" value={ev.ev_formula} />
            <Row label="8040 after t" value={ev.secondary_8040_after_t} />
            <Row label="query mode" value={result?.query_mode} />
            <Row label="entry source" value={result?.entry_source} />
            <Row label="knn" value={result?.knn_status} />
            <Row label="reason" value={result?.reason} />
          </dl>
        </article>
        <article>
          <h2>95% CI</h2>
          <dl>
            <Row label="method" value={ev.method} />
            <Row label="lower ¢" value={ev.ci_lower_cents} />
            <Row label="upper ¢" value={ev.ci_upper_cents} />
            <Row label="level" value={ev.ci_level} />
          </dl>
        </article>
      </div>

      <div className="grid">
        <article>
          <h2>HISTORICAL SUPPORT</h2>
          <dl>
            <Row label="K" value={support.k} />
            <Row label="effective N" value={support.effective_neighbors} />
            <Row label="ESS" value={support.effective_sample_size} />
            <Row label="median d" value={support.median_distance} />
            <Row label="coverage" value={support.feature_coverage} />
            <Row label="support" value={support.support} />
          </dl>
        </article>
        <article>
          <h2>STATE CHANGE FROM ENTRY</h2>
          <dl>
            <Row label="EV at entry" value={change.ev_at_entry} />
            <Row label="EV now" value={change.ev_now} />
            <Row label="change" value={change.ev_change} />
          </dl>
          <p className="muted">Research comparison only. Not an exit instruction.</p>
        </article>
      </div>

      <article className="wide" style={{ marginTop: 14 }}>
        <h2>Distribution after t</h2>
        <dl>
          <Row label="mean" value={dist.mean} />
          <Row label="median" value={dist.median} />
          <Row label="std" value={dist.std} />
          <Row label="p10 / p90" value={`${text(dist.p10)} / ${text(dist.p90)}`} />
          <Row label="min / max" value={`${text(dist.min)} / ${text(dist.max)}`} />
          <Row label="price travel" value={result?.derived?.price_travel} />
          <Row label="time since entry" value={result?.derived?.time_since_entry} />
          <Row
            label="entry sizing ref"
            value={
              result?.sizing
                ? `${text((result.sizing as { recommended_allocation_band?: number }).recommended_allocation_band)}% · ${text((result.sizing as { role?: string }).role)}`
                : null
            }
          />
        </dl>
      </article>

      {ladder.length ? (
        <article className="wide" style={{ marginTop: 14 }}>
          <h2>Price ladder · reconstructed states</h2>
          <p className="muted">Historical replay only. Candle path ≠ fill. Features and EV change when the state changes.</p>
          <table className="data-table">
            <thead>
              <tr>
                <th>print</th>
                <th>¢</th>
                <th>conditional EV</th>
              </tr>
            </thead>
            <tbody>
              {ladder.map((row) => (
                <tr key={row.label}>
                  <td>{row.label}</td>
                  <td>{text(row.price)}</td>
                  <td>{text(row.ev)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </article>
      ) : null}

      <article className="wide" style={{ marginTop: 14 }}>
        <h2>Why this neighborhood</h2>
        <table className="data-table">
          <thead>
            <tr>
              <th>feature</th>
              <th>query</th>
              <th>neighbor median</th>
              <th>|Δ|</th>
            </tr>
          </thead>
          <tbody>
            {(result?.proximity || []).map((row) => (
              <tr key={row.feature}>
                <td>{row.feature}</td>
                <td>{text(row.query)}</td>
                <td>{text(row.neighbor_median)}</td>
                <td>{text(row.abs_delta)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </article>

      <article className="wide" style={{ marginTop: 14 }}>
        <h2>PCA space · PC1 × PC2</h2>
        <p className="muted">DISPLAY / DIAGNOSTIC. Proximity on this plot is not economic evidence.</p>
        <svg className="scatter" viewBox="0 0 100 60">
          <rect className="scatter-bg" x="0" y="0" width="100" height="60" />
          {points.map((p, i) => (
            <circle
              key={`${p.pc1}-${i}`}
              cx={(p.x * 100) / 100}
              cy={(p.y * 60) / 100}
              r="0.7"
              className={p.settlement === "YES" ? "dot-survive" : "dot-t40"}
            />
          ))}
        </svg>
      </article>

      <article className="wide" style={{ marginTop: 14 }}>
        <h2>Historical neighbors</h2>
        <table className="data-table">
          <thead>
            <tr>
              <th>#</th>
              <th>d</th>
              <th>date</th>
              <th>now</th>
              <th>travel</th>
              <th>pnl after t</th>
              <th>settl</th>
              <th>T40 after</th>
            </tr>
          </thead>
          <tbody>
            {neighbors.map((row) => (
              <tr key={`${row.trade_id}-${row.rank}`} onClick={() => onNeighbor(row)} style={{ cursor: "pointer" }}>
                <td>{text(row.rank)}</td>
                <td>{row.distance == null ? "UNAVAILABLE" : row.distance.toFixed(3)}</td>
                <td>{text(row.game_date)}</td>
                <td>{text(row.current_price_cents)}</td>
                <td>{text(row.price_travel)}</td>
                <td>{text(row.pnl_hold_after_t ?? row.final_pnl_taker_8040_cents)}</td>
                <td>{text(row.settlement)}</td>
                <td>{row.hit_40_after ? "path" : "no"}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {replay ? (
          <div>
            <h3>
              Replay {text(replay.ticker)} · {text(replay.game_date)}
            </h3>
            <p className="muted">
              Candle path ≠ fill. Settlement {text(replay.settlement)}. 42 {text(replay.marks?.hit_42)} · 41{" "}
              {text(replay.marks?.hit_41)} · 40 {text(replay.marks?.hit_40)}
            </p>
            <table className="data-table">
              <thead>
                <tr>
                  <th>t s</th>
                  <th>¢</th>
                  <th>home</th>
                  <th>away</th>
                </tr>
              </thead>
              <tbody>
                {(replay.path || []).slice(0, 40).map((pt, i) => (
                  <tr key={`${pt.t}-${i}`}>
                    <td>{text(pt.t_sec)}</td>
                    <td>{text(pt.price_cents)}</td>
                    <td>{text(pt.home_score)}</td>
                    <td>{text(pt.away_score)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </article>

      <div className="grid">
        <article>
          <h2>Hedge lab · 41/42 → 40</h2>
          <p className="muted">Path events. FILL_UNAVAILABLE. 1m close resolution.</p>
          <dl>
            <Row label="n ≤42" value={resolution.n_first_le_42} />
            <Row label="n ≤41" value={resolution.n_first_le_41} />
            <Row label="42 without 41" value={resolution.n_42_without_41} />
            <Row label="same bar" value={resolution.n_same_bar_42_and_41} />
          </dl>
          {["42", "41"].map((key) => {
            const row = ((hedge as { triggers?: Record<string, Record<string, unknown>> } | null)?.triggers || {})[key];
            if (!row) return null;
            return (
              <div key={key}>
                <h3>trigger {key}</h3>
                <dl>
                  <Row label="path triggered" value={row.n_triggered_path} />
                  <Row label="opp 40 reached" value={row.n_price_reached} />
                  <Row label="path EV ¢" value={row.path_based_mean_pnl_cents} />
                </dl>
              </div>
            );
          })}
        </article>
        <article>
          <h2>Calibration table</h2>
          <dl>
            <Row label="status" value={cal.status} />
            <Row label="reason" value={cal.reason} />
          </dl>
          <table className="data-table">
            <thead>
              <tr>
                <th>band</th>
                <th>N</th>
                <th>realized</th>
                <th>%</th>
              </tr>
            </thead>
            <tbody>
              {(cal.table || []).map((row) => (
                <tr key={row.band}>
                  <td>{text(row.band)}</td>
                  <td>{text(row.n)}</td>
                  <td>{text(row.realized_PNL)}</td>
                  <td>{text(row.recommended_band)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="muted">If bands do not separate OOS, every query stays 3%.</p>
        </article>
      </div>

      <article className="wide" style={{ marginTop: 14 }}>
        <h2>Validation</h2>
        <dl>
          <Row label="TRAIN N" value={validation?.train_n} />
          <Row label="VAL N" value={validation?.validation_n} />
          <Row label="OOS N" value={validation?.oos_n} />
          <Row label="snapshot OOS N" value={(validation?.snapshot_oos as { n?: number } | undefined)?.n} />
        </dl>
      </article>

      <article className="wide" style={{ marginTop: 14 }}>
        <h2>Bankroll sleeves · ENTRY_SIZING_REFERENCE</h2>
        <p className="muted">OOS entry walk-forward on the 604 book. Not a new buy. Calibration {text((sizing?.calibration as { status?: string } | undefined)?.status)}.</p>
        <table className="data-table">
          <thead>
            <tr>
              <th>sleeve</th>
              <th>ending ¢</th>
              <th>PNL ¢</th>
              <th>max DD ¢</th>
              <th>N</th>
            </tr>
          </thead>
          <tbody>
            {["3", "4", "5", "austin_dynamic"].map((key) => {
              const row = ((sizing?.bankroll || {}) as Record<string, { ending_bankroll_cents?: number; total_PNL_cents?: number; max_drawdown_cents?: number; trade_count?: number }>)[key];
              if (!row) return null;
              return (
                <tr key={key}>
                  <td>{key === "austin_dynamic" ? "dynamic → 3%" : `${key}%`}</td>
                  <td>{text(row.ending_bankroll_cents)}</td>
                  <td>{text(row.total_PNL_cents)}</td>
                  <td>{text(row.max_drawdown_cents)}</td>
                  <td>{text(row.trade_count)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </article>

      <article className="wide" style={{ marginTop: 14 }}>
        <h2>Feature relationships</h2>
        <p className="muted">CORRELATION ≠ CAUSATION. ZERO_VARIANCE is not UNAVAILABLE.</p>
        <table className="data-table">
          <thead>
            <tr>
              <th>feature</th>
              <th>target</th>
              <th>pearson</th>
              <th>status</th>
              <th>n</th>
            </tr>
          </thead>
          <tbody>
            {(((lab?.correlations as { feature: string; target: string; pearson: number | null; status?: string; sample_count: number }[]) || [])
              .filter((row) => row.target === "pnl_hold_after_t" || row.target === "final_pnl_taker_8040_cents")
              .slice(0, 16)
            ).map((row) => (
              <tr key={`${row.feature}-${row.target}`}>
                <td>{row.feature}</td>
                <td>{row.target}</td>
                <td>{row.pearson == null || !Number.isFinite(row.pearson) ? text(row.status || "UNAVAILABLE") : row.pearson.toFixed(3)}</td>
                <td>{text(row.status)}</td>
                <td>{row.sample_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </article>

      <article className="wide" style={{ marginTop: 14 }}>
        <h2>Audit</h2>
        <dl>
          <Row label="dataset" value={audit?.dataset} />
          <Row label="EV definition" value={audit?.ev_definition} />
          <Row label="execution" value={audit?.execution_status} />
          <Row label="K" value={audit?.k} />
        </dl>
      </article>
    </div>
  );
}
