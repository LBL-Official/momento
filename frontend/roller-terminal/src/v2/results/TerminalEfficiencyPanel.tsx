import type { DetailPayload } from "../components/DetailDrawer";
import type { ContractRates } from "./resultsContract";

export type TeCounts = {
  n_entry?: number;
  n_win_exit?: number;
  n_loss_exit?: number;
  n_ambiguous?: number;
  n_terminal_yes?: number;
  n_terminal_no?: number;
  n_terminal_missing?: number;
};

export type TeSummary = {
  semantics_version?: string;
  code_version?: string;
  note?: string;
  n_entry_rows?: number;
  n_te_attached?: number;
  n_te_scoped?: number;
  filters?: Record<string, string>;
  overall?: TeCounts;
  by_score_side?: {
    leading?: TeCounts;
    tied?: TeCounts;
    trailing?: TeCounts;
    unavailable?: TeCounts;
  };
};

type Trade = Record<string, unknown> & { te?: Record<string, unknown> };

type Props = {
  summary: TeSummary | null | undefined;
  trades: Trade[];
  onOpenDetail: (detail: DetailPayload) => void;
  rates?: ContractRates | null;
};

function rate(win: number, loss: number): string {
  const n = win + loss;
  if (!n) return "—";
  return `${((win / n) * 100).toFixed(1)}%`;
}

function cents(e4: unknown): string {
  if (typeof e4 !== "number" || !Number.isFinite(e4)) return "—";
  return `${Math.round(e4 / 100)}¢`;
}

export default function TerminalEfficiencyPanel({ summary, trades, onOpenDetail, rates }: Props) {
  if (!summary) return null;
  const o = summary.overall ?? {};
  const win = o.n_win_exit ?? 0;
  const loss = o.n_loss_exit ?? 0;
  const sides = summary.by_score_side ?? {};
  const peek = trades.filter((t) => t.te).slice(0, 8);

  return (
    <section className="ws-te-results" aria-label="Base Terminal Efficiency">
      <p className="v2-kicker">Base Terminal Efficiency</p>
      <h2>Entry state → first WIN / LOSS</h2>
      <p className="muted small">
        {summary.note ||
          "PIT observation at the entry bar. Not a prediction. Not terminal efficiency. MEASUREMENT ≠ EDGE."}{" "}
        Headline P(win) is WIN / N. TE WIN/LOSS below is a separate exact-timestamp classified book
        and may drop AMBIGUOUS rows.
      </p>

      <div className="ws-te-stat-grid">
        <button
          type="button"
          className="ws-breakdown-card"
          onClick={() =>
            onOpenDetail({
              title: "TE entries",
              value: String(summary.n_te_scoped ?? 0),
              subtitle: `${summary.n_te_attached ?? 0} attached of ${summary.n_entry_rows ?? 0} entry rows`,
              sections: [
                {
                  heading: "Definition",
                  body: (
                    <p>
                      One observation per ticker at the entry bar. Score uses I(t) then snap.
                      Optional entry chips scope this book only.
                    </p>
                  ),
                },
              ],
            })
          }
        >
          <div className="v2-kicker">TE N</div>
          <div className="ws-breakdown-value evidence">{summary.n_te_scoped ?? 0}</div>
          <div className="muted">
            {summary.n_te_attached ?? 0} / {summary.n_entry_rows ?? 0} attached
          </div>
        </button>
        <button
          type="button"
          className="ws-breakdown-card"
          onClick={() =>
            onOpenDetail({
              title: "TE WIN",
              value: rate(win, loss),
              subtitle: `${win} WIN · ${loss} LOSS · ${o.n_ambiguous ?? 0} AMBIGUOUS`,
              sections: [
                {
                  heading: "Definition",
                  body: (
                    <p>
                      First later exit on the WIN book. Exact same timestamp as LOSS is AMBIGUOUS,
                      not generic minute TIE_EXCLUDED.
                    </p>
                  ),
                },
              ],
            })
          }
        >
          <div className="v2-kicker">TE WIN</div>
          <div className="ws-breakdown-value evidence">{rate(win, loss)}</div>
          <div className="muted">
            {win} / {win + loss || "—"}
          </div>
        </button>
        <button
          type="button"
          className="ws-breakdown-card"
          onClick={() =>
            onOpenDetail({
              title: "TE LOSS",
              value: rate(loss, win),
              subtitle: `${loss} LOSS of ${win + loss} classified`,
              sections: [
                {
                  heading: "Definition",
                  body: <p>First later exit on the LOSS book. Invalid sides stay INVALID_SEMANTICS.</p>,
                },
              ],
            })
          }
        >
          <div className="v2-kicker">TE LOSS</div>
          <div className="ws-breakdown-value evidence">{rate(loss, win)}</div>
          <div className="muted">
            {loss} / {win + loss || "—"}
          </div>
        </button>
        <div className="ws-breakdown-card">
          <div className="v2-kicker">TERMINAL YES</div>
          <div className="ws-breakdown-value evidence">
            {rates?.terminalYes != null && rates.settled
              ? `${rates.terminalYes} / ${rates.settled}`
              : o.n_terminal_yes != null && o.n_terminal_no != null
                ? `${o.n_terminal_yes} / ${o.n_terminal_yes + o.n_terminal_no}`
                : String(o.n_terminal_yes ?? "—")}
          </div>
          <div className="muted">
            {rates?.settled != null && rates.n != null
              ? `coverage ${rates.settled} / ${rates.n} · missing ${rates.terminalMissing ?? "—"} / ${rates.n}`
              : `YES ${o.n_terminal_yes ?? 0} · NO ${o.n_terminal_no ?? 0} · missing ${o.n_terminal_missing ?? 0} · settled denominator only`}
          </div>
        </div>
      </div>

      <h3 className="v2-kicker">By score side at entry</h3>
      <div className="ws-te-side-grid">
        {(
          [
            ["leading", "Leading"],
            ["tied", "Tied"],
            ["trailing", "Trailing"],
            ["unavailable", "Score unavailable"],
          ] as const
        ).map(([key, label]) => {
          const cell = sides[key] ?? {};
          const w = cell.n_win_exit ?? 0;
          const l = cell.n_loss_exit ?? 0;
          return (
            <div key={key} className="ws-te-side-card">
              <div className="v2-kicker">{label}</div>
              <div className="evidence">N = {cell.n_entry ?? 0}</div>
              <div className="muted small">
                WIN {w} · LOSS {l} · {rate(w, l)}
              </div>
            </div>
          );
        })}
      </div>

      {peek.length ? (
        <>
          <h3 className="v2-kicker">Entry observations</h3>
          <div className="ws-te-table-wrap">
            <table className="ws-te-table">
              <thead>
                <tr>
                  <th>Ticker</th>
                  <th>Score</th>
                  <th>Δ</th>
                  <th>Travel</th>
                  <th>TE exit</th>
                </tr>
              </thead>
              <tbody>
                {peek.map((row) => {
                  const te = row.te ?? {};
                  const team = te.team_points;
                  const opp = te.opponent_points;
                  return (
                    <tr key={String(row.ticker ?? te.observation_id)}>
                      <td>{String(row.ticker ?? "—")}</td>
                      <td>
                        {team != null && opp != null ? `${team}–${opp}` : (te.score_status as string) || "—"}
                      </td>
                      <td>{te.point_differential != null ? String(te.point_differential) : "—"}</td>
                      <td>{cents(te.cumulative_price_travel_e4)}</td>
                      <td>{String(te.exit_outcome ?? "—")}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      ) : (
        <p className="muted small">No TE observations on this result yet.</p>
      )}
      <p className="muted small">
        {summary.semantics_version ?? "1.0.0"} · {summary.code_version ?? "base_te_v1.0.0"}
      </p>
    </section>
  );
}
