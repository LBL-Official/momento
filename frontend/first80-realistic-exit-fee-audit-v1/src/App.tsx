import { useEffect, useState } from "react";

type Gate = { ok: boolean; observed?: { n: number; survivors: number; stops: number; leaks: number; surv_pct: number } };
type Strat = { gross_ev?: number | null; net_ev?: number | null; mean_fees?: number | null; trigger_pct?: number | null; mean_exit_proxy?: number | null };
type Region = { region: string; count: number; pct_all: number | null; pct_triggered: number | null };
type Jump = {
  jumped_through_40: { k: number; pct: number | null };
  jump_close: { median: number | null; p75: number | null; p90: number | null; p95: number | null; worst: number | null; mean: number | null };
  orderly_or_class_counts?: Record<string, number>;
};
type Frontier = {
  trigger: number;
  trigger_pct: number | null;
  mean_exit_moderate: number | null;
  gross_ev_moderate: number | null;
  fees_moderate: number | null;
  net_ev_moderate: number | null;
  net_ev_conservative: number | null;
};
type Master = {
  strategy: string;
  gross_ev: number | null;
  entry_fees: number | null;
  exit_or_hedge_fees: number | null;
  net_ev: number | null;
  moderate_net_ev: number | null;
  conservative_net_ev: number | null;
};
type Sport = {
  halted: boolean;
  path_gate?: Gate;
  stop_gate?: Gate;
  hold?: Strat;
  t1?: Strat;
  t2?: Strat;
  t3?: Strat;
  exit_regions?: Region[];
  threshold_triggers?: { exit_price: number; trigger_count: number; trigger_probability: number | null }[];
  jumps?: Jump;
  frontier?: Frontier[];
  trigger_selection?: { trigger: number; val_net_ev_moderate: number | null };
  hedge_opportunity?: {
    opponent_available: number;
    n: number;
    by_H: { H: number; pct_before_stop: number | null; p_reaches_and_a1_wins: number | null; p_reaches_and_a1_loses: number | null; false_hedge_share_of_opps: number | null }[];
  };
  hedge_full?: Record<string, { H1: number | null; H2: number | null; H3: number | null; sens: Record<string, number | null> }>;
  best_hedge?: { H: number };
  master?: Master[];
  fee_grid?: { exit_price: number; taker_fee: number; gross_exit_pnl: number; net_exit_pnl: number }[];
  oos_note?: string | null;
};
type Dash = {
  banner: string;
  verdict: string;
  sports: Record<string, Sport>;
};

const VIEWS = [
  ["baseline", "1 Baseline"],
  ["exits", "2 Exit dist"],
  ["jumps", "3 Jump-through"],
  ["fees", "4 Taker fees"],
  ["ev", "5 Net EV"],
  ["hedge", "6 Hedge frontier"],
  ["fills", "7 Fill sensitivity"],
  ["master", "8 Master"],
] as const;

function fmt(n?: number | null, d = 2) {
  return n == null || Number.isNaN(n) ? "—" : n.toFixed(d);
}

function tone(n?: number | null) {
  if (n == null) return "";
  if (n > 0) return "pos";
  if (n < 0) return "neg";
  return "";
}

function Card({ k, v, cls }: { k: string; v: string; cls?: string }) {
  return (
    <div className="card">
      <div className="k">{k}</div>
      <div className={`v ${cls ?? ""}`}>{v}</div>
    </div>
  );
}

function Bars({ items }: { items: { label: string; n: number }[] }) {
  const m = Math.max(1, ...items.map((b) => b.n));
  return (
    <div className="bars" style={{ marginBottom: 22 }}>
      {items.map((b) => (
        <div key={b.label} className="bar" style={{ height: `${(100 * b.n) / m}%` }} title={`${b.label}: ${b.n}`}>
          <span>{b.label}</span>
        </div>
      ))}
    </div>
  );
}

export default function App() {
  const [dash, setDash] = useState<Dash | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [sport, setSport] = useState<"nba" | "ncaab">("nba");
  const [view, setView] = useState<(typeof VIEWS)[number][0]>("baseline");

  useEffect(() => {
    fetch("/data/dashboard.json")
      .then((r) => {
        if (!r.ok) throw new Error(`dashboard.json ${r.status}`);
        return r.json();
      })
      .then(setDash)
      .catch((e: Error) => setErr(e.message));
  }, []);

  const s = dash?.sports[sport];

  return (
    <div className="app">
      <div className="banner">{dash?.banner ?? "Loading FIRST80 realistic exit + fee audit…"}</div>
      <div className="top">
        <div className="brand">
          FIRST80 EXIT + FEE V1
          <small>Candle proxy · not a fill · settlement fee = 0</small>
        </div>
        <div className="ctrl">
          <label>Sport</label>
          <select value={sport} onChange={(e) => setSport(e.target.value as "nba" | "ncaab")}>
            <option value="nba">NBA</option>
            <option value="ncaab">NCAAB</option>
          </select>
        </div>
        {dash && <Card k="Verdict" v={dash.verdict} cls={dash.verdict === "A" ? "pos" : dash.verdict === "D" ? "neg" : "warn"} />}
      </div>
      <div className="tabs">
        {VIEWS.map(([id, label]) => (
          <button key={id} className={view === id ? "on" : ""} onClick={() => setView(id)}>
            {label}
          </button>
        ))}
      </div>
      <div className="main">
        {err && <p className="neg">Failed to load dashboard: {err}</p>}
        {!dash && !err && <p className="muted">Loading measured results…</p>}
        {s?.halted && <p className="neg">Analysis halted for {sport}. No new EV claims.</p>}
        {dash && s && !s.halted && view === "baseline" && (
          <>
            <h2>Panel 1 — FIRST-80 baseline</h2>
            <p className="panel-note">Frozen close-stop universe. Path survival is candle-path, not a maker fill.</p>
            <div className="row">
              <Card k="n" v={String(s.path_gate?.observed?.n ?? "—")} />
              <Card k="Survivors" v={String(s.path_gate?.observed?.survivors ?? "—")} cls="pos" />
              <Card k="Stops" v={String(s.path_gate?.observed?.stops ?? "—")} cls="neg" />
              <Card k="Survival" v={`${fmt(s.path_gate?.observed?.surv_pct, 2)}%`} />
              <Card k="Path gate" v={s.path_gate?.ok ? "PASS" : "FAIL"} cls={s.path_gate?.ok ? "pos" : "neg"} />
              <Card k="Stop gate" v={s.stop_gate?.ok ? "PASS" : "FAIL"} cls={s.stop_gate?.ok ? "pos" : "neg"} />
            </div>
            {s.oos_note && <p className="warn">OOS: {s.oos_note}</p>}
          </>
        )}
        {dash && s && !s.halted && view === "exits" && (
          <>
            <h2>Panel 2 — Exit price distribution</h2>
            <p className="panel-note">Model B: trigger-candle yes_bid_close among 40-close triggers. Trigger distribution ≠ realized proxy.</p>
            <Bars
              items={(s.exit_regions ?? [])
                .filter((r) => r.region !== "No deterioration exit")
                .map((r) => ({ label: r.region, n: r.count }))}
            />
            <table>
              <thead>
                <tr>
                  <th>Region</th>
                  <th>Count</th>
                  <th>% all</th>
                  <th>% triggered</th>
                </tr>
              </thead>
              <tbody>
                {(s.exit_regions ?? []).map((r) => (
                  <tr key={r.region}>
                    <td>{r.region}</td>
                    <td>{r.count}</td>
                    <td>{fmt(r.pct_all)}</td>
                    <td>{fmt(r.pct_triggered)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <h2>Threshold trigger P(close ≤ T)</h2>
            <table>
              <thead>
                <tr>
                  <th>T</th>
                  <th>Count</th>
                  <th>P</th>
                </tr>
              </thead>
              <tbody>
                {(s.threshold_triggers ?? []).map((r) => (
                  <tr key={r.exit_price}>
                    <td>{r.exit_price}¢</td>
                    <td>{r.trigger_count}</td>
                    <td>{fmt(r.trigger_probability)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
        {dash && s && !s.halted && view === "jumps" && (
          <>
            <h2>Panel 3 — Jump-through risk</h2>
            <p className="panel-note">previous_close − trigger_close. Candle gap, not L2.</p>
            <div className="row">
              <Card k="Median jump" v={`${fmt(s.jumps?.jump_close.median)}¢`} />
              <Card k="p75" v={`${fmt(s.jumps?.jump_close.p75)}¢`} />
              <Card k="p90" v={`${fmt(s.jumps?.jump_close.p90)}¢`} />
              <Card k="p95" v={`${fmt(s.jumps?.jump_close.p95)}¢`} />
              <Card k="Worst" v={`${fmt(s.jumps?.jump_close.worst)}¢`} cls="neg" />
              <Card k="Jump through 40" v={`${fmt(s.jumps?.jumped_through_40.pct)}%`} />
            </div>
            <table>
              <thead>
                <tr>
                  <th>Class</th>
                  <th>Count</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(s.jumps?.orderly_or_class_counts ?? {}).map(([k, n]) => (
                  <tr key={k}>
                    <td>{k}</td>
                    <td>{n}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
        {dash && s && !s.halted && view === "fees" && (
          <>
            <h2>Panel 4 — Taker fee curve</h2>
            <p className="panel-note">ceil_6dp(0.07 × P × (1−P)), M=1, 1 contract. SETTLEMENT_FEE = 0. CURRENT entry fee = 0.</p>
            <Bars items={(s.fee_grid ?? []).map((f) => ({ label: `${f.exit_price}`, n: Math.round(f.taker_fee * 100) }))} />
            <p className="caption">Bar height ∝ taker fee (scaled ×100). Source: published Kalshi quadratic schedule.</p>
            <table>
              <thead>
                <tr>
                  <th>Exit</th>
                  <th>Taker fee</th>
                  <th>Gross vs 80</th>
                  <th>Net CURRENT</th>
                </tr>
              </thead>
              <tbody>
                {(s.fee_grid ?? []).map((f) => (
                  <tr key={f.exit_price}>
                    <td>{f.exit_price}¢</td>
                    <td>{fmt(f.taker_fee, 4)}¢</td>
                    <td className={tone(f.gross_exit_pnl)}>{fmt(f.gross_exit_pnl)}</td>
                    <td className={tone(f.net_exit_pnl)}>{fmt(f.net_exit_pnl, 4)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
        {dash && s && !s.halted && view === "ev" && (
          <>
            <h2>Panel 5 — Net EV by exit strategy</h2>
            <div className="row">
              <Card k="Hold net" v={`${fmt(s.hold?.net_ev)}¢`} cls={tone(s.hold?.net_ev)} />
              <Card k="T1 ideal net" v={`${fmt(s.t1?.net_ev)}¢`} cls={tone(s.t1?.net_ev)} />
              <Card k="T2 moderate net" v={`${fmt(s.t2?.net_ev)}¢`} cls={tone(s.t2?.net_ev)} />
              <Card k="T3 conservative net" v={`${fmt(s.t3?.net_ev)}¢`} cls={tone(s.t3?.net_ev)} />
              <Card k="T2 mean fees" v={`${fmt(s.t2?.mean_fees, 4)}¢`} />
              <Card k="T2 mean exit" v={`${fmt(s.t2?.mean_exit_proxy)}¢`} />
            </div>
            <h2>Frontier (FULL descriptive)</h2>
            <table>
              <thead>
                <tr>
                  <th>Trigger</th>
                  <th>Trig %</th>
                  <th>Mean exit B</th>
                  <th>Gross B</th>
                  <th>Fees</th>
                  <th>Net mod</th>
                  <th>Net cons</th>
                </tr>
              </thead>
              <tbody>
                {(s.frontier ?? []).map((f) => (
                  <tr key={f.trigger}>
                    <td>{f.trigger}</td>
                    <td>{fmt(f.trigger_pct)}</td>
                    <td>{fmt(f.mean_exit_moderate)}</td>
                    <td className={tone(f.gross_ev_moderate)}>{fmt(f.gross_ev_moderate)}</td>
                    <td>{fmt(f.fees_moderate, 4)}</td>
                    <td className={tone(f.net_ev_moderate)}>{fmt(f.net_ev_moderate)}</td>
                    <td className={tone(f.net_ev_conservative)}>{fmt(f.net_ev_conservative)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="caption">
              VAL-selected trigger: {s.trigger_selection?.trigger}¢ (VAL net {fmt(s.trigger_selection?.val_net_ev_moderate)}).
              Selection did not use OOS.
            </p>
          </>
        )}
        {dash && s && !s.halted && view === "hedge" && (
          <>
            <h2>Panel 6 — Hedge frontier</h2>
            <p className="panel-note">
              Maker fill scenario. Opportunity = A2 bid_close ≥ H before A1 40-close. Opponent available {s.hedge_opportunity?.opponent_available}/{s.hedge_opportunity?.n}.
            </p>
            <table>
              <thead>
                <tr>
                  <th>H</th>
                  <th>Opp % before stop</th>
                  <th>P(reach & A1 wins)</th>
                  <th>P(reach & A1 loses)</th>
                  <th>False-hedge share</th>
                  <th>H1 net</th>
                  <th>H2 p50 net</th>
                  <th>H3 p25 net</th>
                </tr>
              </thead>
              <tbody>
                {(s.hedge_opportunity?.by_H ?? []).map((h) => {
                  const g = s.hedge_full?.[String(h.H)];
                  return (
                    <tr key={h.H}>
                      <td>{h.H}</td>
                      <td>{fmt(h.pct_before_stop)}</td>
                      <td>{fmt(h.p_reaches_and_a1_wins)}</td>
                      <td>{fmt(h.p_reaches_and_a1_loses)}</td>
                      <td>{fmt(h.false_hedge_share_of_opps)}</td>
                      <td className={tone(g?.H1)}>{fmt(g?.H1)}</td>
                      <td className={tone(g?.H2)}>{fmt(g?.H2)}</td>
                      <td className={tone(g?.H3)}>{fmt(g?.H3)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </>
        )}
        {dash && s && !s.halted && view === "fills" && (
          <>
            <h2>Panel 7 — Fill-probability sensitivity</h2>
            <p className="panel-note">
              Assumed p_fill, not measured. Best VAL hedge H={s.best_hedge?.H}. CURRENT fees. Unhedged = idealized 80→40.
            </p>
            <table>
              <thead>
                <tr>
                  <th>p_fill</th>
                  {(s.hedge_opportunity?.by_H ?? []).map((h) => (
                    <th key={h.H}>H={h.H}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {["0.25", "0.40", "0.50", "0.60", "0.75", "0.90", "1.00"].map((p) => (
                  <tr key={p}>
                    <td>{p}</td>
                    {(s.hedge_opportunity?.by_H ?? []).map((h) => {
                      const ev = s.hedge_full?.[String(h.H)]?.sens[p];
                      return (
                        <td key={h.H} className={tone(ev)}>
                          {fmt(ev)}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
        {dash && s && !s.halted && view === "master" && (
          <>
            <h2>Panel 8 — Master comparison</h2>
            <p className="panel-note">Cents per contract. Hedge rows: H1 net / H2 moderate / H3 conservative. Not live-ready.</p>
            <table>
              <thead>
                <tr>
                  <th>Strategy</th>
                  <th>Gross</th>
                  <th>Entry fees</th>
                  <th>Exit/hedge fees</th>
                  <th>Net</th>
                  <th>Moderate</th>
                  <th>Conservative</th>
                </tr>
              </thead>
              <tbody>
                {(s.master ?? []).map((m) => (
                  <tr key={m.strategy}>
                    <td>{m.strategy}</td>
                    <td className={tone(m.gross_ev)}>{fmt(m.gross_ev)}</td>
                    <td>{fmt(m.entry_fees, 4)}</td>
                    <td>{fmt(m.exit_or_hedge_fees, 4)}</td>
                    <td className={tone(m.net_ev)}>{fmt(m.net_ev)}</td>
                    <td className={tone(m.moderate_net_ev)}>{fmt(m.moderate_net_ev)}</td>
                    <td className={tone(m.conservative_net_ev)}>{fmt(m.conservative_net_ev)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
      </div>
    </div>
  );
}
