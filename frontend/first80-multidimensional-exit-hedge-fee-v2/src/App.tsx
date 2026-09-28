import { useEffect, useMemo, useState } from "react";

type Reach = { threshold: number; p_close: number; p_touch: number; p_win_given_close: number | null };
type DD = { max_dd_reaches: number; n: number; p_win: number | null };
type Band = { trigger: number; n: number; mean_proxy: number | null; bands: Record<string, number> };
type Pol = { threshold?: number; net_ev?: number | null; gross_ev?: number | null; mean_fees?: number | null; trigger_pct?: number | null; mean_exit?: number | null; trigger_type?: string; persist?: number; fee_scenario?: string; evidence?: string };
type Named = Record<string, { net_ev?: number | null; gross_ev?: number | null; mean_fees?: number | null; evidence?: string }>;
type Sport = {
  halted: boolean;
  path_gate?: { ok: boolean; observed?: { n: number; survivors: number; surv_pct: number } };
  oos_n?: number;
  oos_note?: string | null;
  reach?: Reach[];
  p_win_dd?: DD[];
  exit_bands?: Band[];
  t2_thresholds?: Pol[];
  t1_thresholds?: Pol[];
  t3_thresholds?: Pol[];
  trigger_types?: Pol[];
  fees?: Pol[];
  hedge_surface?: { H: number; p: number; net: number | null; opp?: number | null }[];
  ratios?: { hedge_ratio?: number; net_ev?: number | null; capital_reserved?: number }[];
  named?: Named;
  frontier?: { policy?: string; family?: string; net_ev?: number | null; downside?: number | null; capital?: number; fill_dependency?: number; evidence?: string }[];
  fee_attribution?: { strategy: string; gross_ev?: number | null; entry_fees?: number; exit_fees?: number; hedge_fees?: number; net_ev?: number | null }[];
  break_even_exit?: { exit_px: number; net_ev: number }[];
  break_even_fill?: { p_fill: number; net_ev: number | null }[];
  season?: Record<string, { independent?: { mean: number; p05: number; p_losing_season: number } }>;
  vol?: { threshold: number; vol: string; n: number; mean_exit?: number | null; p_win?: number | null }[];
  time?: { threshold: number; time: string; n: number; mean_exit?: number | null; p_win?: number | null }[];
  selection?: { taker_val?: Pol | null; taker_oos?: Pol | null; hedge_val?: { hedge_h?: number; net_ev?: number | null } | null; hedge_oos?: { net_ev?: number | null } | null };
  by_split?: Record<string, Named>;
};
type Dash = { banner: string; verdict: string; fill_grid: number[]; sports: Record<string, Sport> };

const VIEWS = [
  ["reach", "A Reach"],
  ["win", "B P(win|DD)"],
  ["exit", "C Exit dist"],
  ["fees", "D Fee attr"],
  ["hedge", "E Hedge surface"],
  ["front", "F Frontier"],
  ["season", "G Season"],
  ["master", "Master"],
] as const;

function fmt(n?: number | null, d = 2) {
  return n == null || Number.isNaN(n) ? "—" : n.toFixed(d);
}
function tone(n?: number | null) {
  if (n == null) return "";
  return n > 0 ? "pos" : n < 0 ? "neg" : "";
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
    <div className="bars">
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
  const [split, setSplit] = useState<"FULL" | "TRAIN" | "VALIDATION" | "OOS">("FULL");
  const [view, setView] = useState<(typeof VIEWS)[number][0]>("reach");
  const [thr, setThr] = useState(40);
  const [model, setModel] = useState<"T1" | "T2" | "T3">("T2");
  const [pFill, setPFill] = useState(0.5);
  const [h, setH] = useState(40);
  const [fee, setFee] = useState("CURRENT_BASE_CASE");
  const [capital, setCapital] = useState("RESERVED_ENTRY_PLUS_HEDGE");

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
  const band = s?.exit_bands?.find((b) => b.trigger === thr);
  const tRow = useMemo(() => {
    const src = model === "T1" ? s?.t1_thresholds : model === "T3" ? s?.t3_thresholds : s?.t2_thresholds;
    return src?.find((x) => x.threshold === thr);
  }, [s, model, thr]);
  const hedgeCell = s?.hedge_surface?.find((x) => x.H === h && Math.abs(x.p - pFill) < 1e-9);
  const feeRow = s?.fees?.find((x) => x.fee_scenario === fee);
  const volAt = s?.vol?.filter((v) => v.threshold === thr) ?? [];
  const timeAt = s?.time?.filter((v) => v.threshold === thr) ?? [];

  return (
    <div className="app">
      <div className="banner">{dash?.banner ?? "Loading V2…"}</div>
      <div className="top">
        <div className="brand">
          FIRST80 MULTI-D V2
          <small>Observed ≠ fill · trigger ≠ exit · opportunity ≠ fill</small>
        </div>
        <div className="ctrl">
          <label>Sport</label>
          <select value={sport} onChange={(e) => setSport(e.target.value as "nba" | "ncaab")}>
            <option value="nba">NBA</option>
            <option value="ncaab">NCAAB</option>
          </select>
        </div>
        <div className="ctrl">
          <label>Data split</label>
          <select value={split} onChange={(e) => setSplit(e.target.value as typeof split)}>
            <option value="FULL">FULL</option>
            <option value="TRAIN">TRAIN</option>
            <option value="VALIDATION">VALIDATION</option>
            <option value="OOS">OOS</option>
          </select>
        </div>
        <div className="ctrl">
          <label>Threshold</label>
          <select value={thr} onChange={(e) => setThr(Number(e.target.value))}>
            {(dash?.sports.nba?.t2_thresholds ?? [{ threshold: 40 }]).map((x) => (
              <option key={x.threshold} value={x.threshold}>
                {x.threshold}
              </option>
            ))}
          </select>
        </div>
        <div className="ctrl">
          <label>Exit model</label>
          <select value={model} onChange={(e) => setModel(e.target.value as "T1" | "T2" | "T3")}>
            <option value="T1">T1 ideal (C)</option>
            <option value="T2">T2 close (B)</option>
            <option value="T3">T3 low (B/C)</option>
          </select>
        </div>
        <div className="ctrl">
          <label>Hedge H</label>
          <select value={h} onChange={(e) => setH(Number(e.target.value))}>
            {[40, 35, 30, 25, 20, 15, 10, 5].map((x) => (
              <option key={x} value={x}>
                {x}
              </option>
            ))}
          </select>
        </div>
        <div className="ctrl">
          <label>p_fill (D)</label>
          <select value={pFill} onChange={(e) => setPFill(Number(e.target.value))}>
            {(dash?.fill_grid ?? [0.5]).map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        </div>
        <div className="ctrl">
          <label>Fee scenario</label>
          <select value={fee} onChange={(e) => setFee(e.target.value)}>
            <option value="CURRENT_BASE_CASE">CURRENT</option>
            <option value="CONSERVATIVE_FEE_STRESS">CONSERVATIVE</option>
            <option value="HIGHER_FUTURE_FEE_STRESS">FUTURE 1.5×</option>
          </select>
        </div>
        <div className="ctrl">
          <label>Capital model</label>
          <select value={capital} onChange={(e) => setCapital(e.target.value)}>
            <option value="RESERVED_ENTRY_PLUS_HEDGE">80 + r×H reserved</option>
            <option value="ENTRY_ONLY">80 entry only</option>
          </select>
        </div>
        {dash && <Card k="Verdict" v={dash.verdict} cls="warn" />}
      </div>
      <div className="tabs">
        {VIEWS.map(([id, label]) => (
          <button key={id} className={view === id ? "on" : ""} onClick={() => setView(id)}>
            {label}
          </button>
        ))}
      </div>
      <div className="main">
        {err && <p className="neg">{err}</p>}
        {s?.halted && <p className="neg">Halted. No optimization.</p>}
        {dash && s && !s.halted && view === "reach" && (
          <>
            <h2>A. Deterioration reach — OBSERVED (A)</h2>
            <p className="caption">P(path close ≤ T) after FIRST-80. Frozen universe. Candle path, not a fill.</p>
            <div className="row">
              <Card k="n" v={String(s.path_gate?.observed?.n ?? "—")} />
              <Card k="Survivors" v={`${s.path_gate?.observed?.survivors} (${fmt(s.path_gate?.observed?.surv_pct)}%)`} cls="pos" />
              <Card k="Selected T close%" v={`${fmt(s.reach?.find((r) => r.threshold === thr)?.p_close)}%`} />
              <Card k="P(win | close≤T)" v={`${fmt(s.reach?.find((r) => r.threshold === thr)?.p_win_given_close)}%`} />
            </div>
            <Bars items={(s.reach ?? []).map((r) => ({ label: String(r.threshold), n: r.p_close }))} />
            <table>
              <thead>
                <tr>
                  <th>T</th>
                  <th>P(close)</th>
                  <th>P(touch)</th>
                  <th>P(win|close)</th>
                </tr>
              </thead>
              <tbody>
                {(s.reach ?? []).map((r) => (
                  <tr key={r.threshold}>
                    <td>{r.threshold}</td>
                    <td>{fmt(r.p_close)}</td>
                    <td>{fmt(r.p_touch)}</td>
                    <td>{fmt(r.p_win_given_close)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
        {dash && s && !s.halted && view === "win" && (
          <>
            <h2>B. P(favorite wins | min price ≤ X) — OBSERVED (A)</h2>
            <Bars items={(s.p_win_dd ?? []).map((r) => ({ label: String(r.max_dd_reaches), n: r.p_win ?? 0 }))} />
            <table>
              <thead>
                <tr>
                  <th>X</th>
                  <th>n</th>
                  <th>P(win)</th>
                </tr>
              </thead>
              <tbody>
                {(s.p_win_dd ?? []).map((r) => (
                  <tr key={r.max_dd_reaches}>
                    <td>{r.max_dd_reaches}</td>
                    <td>{r.n}</td>
                    <td>{fmt(r.p_win)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
        {dash && s && !s.halted && view === "exit" && (
          <>
            <h2>C. Exit proxy | trigger={thr} — ESTIMATED (B)</h2>
            <p className="caption">Trigger-candle bid close. Not an IOC fill (C). T1/T2/T3 for selected T: net {fmt(tRow?.net_ev)}¢ · mean exit {fmt(tRow?.mean_exit)} · trig {fmt(tRow?.trigger_pct)}%.</p>
            <Bars
              items={["37-40", "32-36", "27-31", "22-26", "<22"].map((k) => ({
                label: k,
                n: band?.bands?.[k] ?? 0,
              }))}
            />
            <h2>Vol / time at T={thr} (B)</h2>
            <table>
              <thead>
                <tr>
                  <th>Vol</th>
                  <th>n</th>
                  <th>Mean exit</th>
                  <th>P(win)</th>
                </tr>
              </thead>
              <tbody>
                {volAt.map((v) => (
                  <tr key={v.vol}>
                    <td>{v.vol}</td>
                    <td>{v.n}</td>
                    <td>{fmt(v.mean_exit)}</td>
                    <td>{fmt(v.p_win)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <table>
              <thead>
                <tr>
                  <th>Time since entry</th>
                  <th>n</th>
                  <th>Mean exit</th>
                  <th>P(win)</th>
                </tr>
              </thead>
              <tbody>
                {timeAt.map((v) => (
                  <tr key={v.time}>
                    <td>{v.time}</td>
                    <td>{v.n}</td>
                    <td>{fmt(v.mean_exit)}</td>
                    <td>{fmt(v.p_win)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
        {dash && s && !s.halted && view === "fees" && (
          <>
            <h2>D. Fee attribution — ESTIMATED</h2>
            <p className="caption">
              Selected fee scenario @40 T2: {fee} net {fmt(feeRow?.net_ev)} fees {fmt(feeRow?.mean_fees)}. Slippage (T1 vs T2) is the main gap, not fees.
            </p>
            <table>
              <thead>
                <tr>
                  <th>Strategy</th>
                  <th>Gross</th>
                  <th>Entry</th>
                  <th>Exit</th>
                  <th>Hedge</th>
                  <th>Net</th>
                </tr>
              </thead>
              <tbody>
                {(s.fee_attribution ?? []).map((f) => (
                  <tr key={f.strategy}>
                    <td>{f.strategy}</td>
                    <td className={tone(f.gross_ev)}>{fmt(f.gross_ev)}</td>
                    <td>{fmt(f.entry_fees, 4)}</td>
                    <td>{fmt(f.exit_fees, 4)}</td>
                    <td>{fmt(f.hedge_fees, 4)}</td>
                    <td className={tone(f.net_ev)}>{fmt(f.net_ev)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
        {dash && s && !s.halted && view === "hedge" && (
          <>
            <h2>E. Hedge sensitivity — ASSUMED p_fill (D)</h2>
            <p className="caption">
              H={h} p={pFill}: net {fmt(hedgeCell?.net)}¢ · opp {fmt(hedgeCell?.opp)}%. Maker opportunity ≠ fill. Fallback is T2@40 if missed.
              Capital = {capital === "ENTRY_ONLY" ? "80¢ entry" : `80 + r×${h}`}.
            </p>
            <table>
              <thead>
                <tr>
                  <th>Hedge ratio @ H=40 p=50%</th>
                  <th>Net EV</th>
                  <th>Reserved ¢</th>
                </tr>
              </thead>
              <tbody>
                {(s.ratios ?? []).map((r) => (
                  <tr key={r.hedge_ratio}>
                    <td>{r.hedge_ratio}</td>
                    <td className={tone(r.net_ev)}>{fmt(r.net_ev)}</td>
                    <td>{r.capital_reserved}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <table>
              <thead>
                <tr>
                  <th>H \ p</th>
                  {(dash.fill_grid ?? []).map((p) => (
                    <th key={p}>{p}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {[40, 35, 30, 25, 20, 15, 10, 5].map((hh) => (
                  <tr key={hh}>
                    <td>{hh}</td>
                    {(dash.fill_grid ?? []).map((p) => {
                      const c = s.hedge_surface?.find((x) => x.H === hh && Math.abs(x.p - p) < 1e-9);
                      return (
                        <td key={p} className={tone(c?.net)}>
                          {fmt(c?.net)}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
        {dash && s && !s.halted && view === "front" && (
          <>
            <h2>F. Policy frontier — mixed evidence</h2>
            <p className="caption">Y = net EV. Downside = per-trade downside deviation. Fill-dep 1 = hedge scenario. Do not pick on OOS (n={s.oos_n} {s.oos_note}).</p>
            <table>
              <thead>
                <tr>
                  <th>Policy</th>
                  <th>Family</th>
                  <th>Net EV</th>
                  <th>Downside</th>
                  <th>Capital</th>
                  <th>Fill dep</th>
                  <th>Grade</th>
                </tr>
              </thead>
              <tbody>
                {(s.frontier ?? []).map((f) => (
                  <tr key={f.policy}>
                    <td>{f.policy}</td>
                    <td>{f.family}</td>
                    <td className={tone(f.net_ev)}>{fmt(f.net_ev)}</td>
                    <td>{fmt(f.downside)}</td>
                    <td>{f.capital}</td>
                    <td>{f.fill_dependency}</td>
                    <td className="grade">{f.evidence}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
        {dash && s && !s.halted && view === "season" && (
          <>
            <h2>G. Season simulation — ESTIMATED (C)</h2>
            <p className="caption">10k resamples of the frozen universe × 7 contracts. Independent vs date-block correlation. Not a live season forecast.</p>
            <table>
              <thead>
                <tr>
                  <th>Book</th>
                  <th>Mean ¢</th>
                  <th>p05</th>
                  <th>P(lose)</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(s.season ?? {}).map(([k, v]) => (
                  <tr key={k}>
                    <td>{k}</td>
                    <td className={tone(v.independent?.mean)}>{fmt(v.independent?.mean)}</td>
                    <td>{fmt(v.independent?.p05)}</td>
                    <td>{fmt(v.independent?.p_losing_season, 3)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <h2>Break-even exit (taker mixture)</h2>
            <p className="caption">Net EV vs assumed realized stop price. OBSERVED trigger rate, ASSUMED fill at X.</p>
            <table>
              <thead>
                <tr>
                  <th>Exit ¢</th>
                  <th>Net EV</th>
                </tr>
              </thead>
              <tbody>
                {(s.break_even_exit ?? []).filter((x) => x.exit_px % 5 === 0).map((x) => (
                  <tr key={x.exit_px}>
                    <td>{x.exit_px}</td>
                    <td className={tone(x.net_ev)}>{fmt(x.net_ev)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
        {dash && s && !s.halted && view === "master" && (
          <>
            <h2>Master named policies — {split}</h2>
            <p className="caption">
              VAL taker T={s.selection?.taker_val?.threshold} net {fmt(s.selection?.taker_val?.net_ev)} → OOS {fmt(s.selection?.taker_oos?.net_ev)}. VAL hedge H=
              {s.selection?.hedge_val?.hedge_h} → OOS {fmt(s.selection?.hedge_oos?.net_ev)}. OOS n={s.oos_n} {s.oos_note}. LIVE DEPLOYMENT NOT AUTHORIZED.
            </p>
            <table>
              <thead>
                <tr>
                  <th>Strategy</th>
                  <th>Gross</th>
                  <th>Net</th>
                  <th>Fees</th>
                  <th>Grade</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries((split === "FULL" ? s.named : s.by_split?.[split]) ?? {}).map(([k, v]) => (
                  <tr key={k}>
                    <td>{k}</td>
                    <td className={tone(v.gross_ev)}>{fmt(v.gross_ev)}</td>
                    <td className={tone(v.net_ev)}>{fmt(v.net_ev)}</td>
                    <td>{fmt(v.mean_fees, 4)}</td>
                    <td className="grade">{v.evidence}</td>
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
