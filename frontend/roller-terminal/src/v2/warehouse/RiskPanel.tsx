import { useState } from "react";
import { apiFetch } from "../../api/base";
import { useDeskSettings } from "../settings/useDeskSettings";

type RiskResult = {
  mode?: string;
  seed?: number;
  research_result_hash?: string;
  risk_result_hash?: string;
  deterministic?: Record<string, unknown>;
  monte_carlo?: {
    terminal_bankroll?: Record<string, number>;
    max_drawdown?: Record<string, number>;
    probabilities?: Record<string, number>;
    path_summaries?: Record<string, number>;
    fees?: string;
    fills?: string;
    note?: string;
  };
  costs?: Record<string, unknown>;
  correlation?: { status?: string };
  model_uncertainty?: Record<string, unknown> | null;
  not?: string[];
};

function pct(value: unknown): string {
  if (typeof value !== "number" || Number.isNaN(value)) return "—";
  return `${(value * 100).toFixed(2)}%`;
}

function money(value: unknown): string {
  if (typeof value !== "number" || Number.isNaN(value)) return "—";
  return `$${value.toFixed(2)}`;
}

export default function RiskPanel({
  researchHash,
  classifications,
}: {
  researchHash?: string;
  classifications?: string[];
}) {
  const [mode, setMode] = useState("A");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<RiskResult | null>(null);
  const {
    bankrollDollars,
    setBankrollDollars,
    allocationPct,
    setAllocationPct,
    saving: deskSaving,
    error: deskError,
    save: saveDesk,
  } = useDeskSettings();
  const run = async () => {
    setBusy(true);
    setError(null);
    try {
      const res = await apiFetch("/warehouse-research/risk", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          mode,
          seed: 20260913,
          research_result_hash: researchHash || "",
          classifications: classifications || [],
          persist: true,
          config: {
            monte_carlo_paths: 100000,
            initial_bankroll: bankrollDollars,
            trade_allocation: allocationPct / 100,
          },
        }),
      });
      const body = (await res.json()) as RiskResult & { detail?: string };
      if (!res.ok) throw new Error(typeof body.detail === "string" ? body.detail : "Risk failed");
      setResult(body);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };
  const d = result?.deterministic || {};
  const mc = result?.monte_carlo;
  return (
    <section className="ws-risk-panel" aria-label="Bankroll and risk">
      <p className="v2-kicker">Bankroll & Risk</p>
      <p className="muted small">
        Consumer of the research result. Candle-path ≠ fill. Risk result ≠ research CSV. Bankroll and allocation
        come from ROLLER settings.
      </p>
      <div className="ws-capital-inputs">
        <label>
          Bankroll $
          <input
            type="number"
            min={1}
            value={bankrollDollars}
            onChange={(e) => setBankrollDollars(Number(e.target.value) || 0)}
          />
        </label>
        <label>
          Risk per trade %
          <input
            type="number"
            min={0.01}
            max={100}
            step={0.01}
            value={allocationPct}
            onChange={(e) => setAllocationPct(Number(e.target.value) || 0)}
          />
        </label>
        <button type="button" className="btn-secondary" disabled={deskSaving} onClick={() => void saveDesk()}>
          {deskSaving ? "Saving…" : "Save settings"}
        </button>
      </div>
      {deskError ? <p className="muted small">{deskError}</p> : null}
      <div className="ws-labs-toolbar">
        <label>
          Mode
          <select value={mode} onChange={(e) => setMode(e.target.value)}>
            <option value="A">A theoretical binary</option>
            <option value="B">B empirical classifications</option>
            <option value="C">C requires external p_i</option>
          </select>
        </label>
        <button type="button" className="btn-secondary" disabled={busy} onClick={() => void run()}>
          {busy ? "Simulating…" : "Run risk"}
        </button>
      </div>
      {error ? <p className="muted small">{error}</p> : null}
      {result ? (
        <dl className="ws-warehouse-meta">
          <div>
            <dt>Break-even / required p</dt>
            <dd>
              {pct(d.break_even_probability)} / {pct(d.required_win_probability)}
            </dd>
          </div>
          <div>
            <dt>EV/trade / EV/week</dt>
            <dd>
              {pct(d.trade_ev)} ({money(d.trade_ev_dollars)}) / {pct(d.weekly_ev)} ({money(d.weekly_ev_dollars)})
            </dd>
          </div>
          <div>
            <dt>Weekly vol / target wins</dt>
            <dd>
              {pct(d.weekly_volatility)} / {String(d.min_wins_for_target ?? "—")}
            </dd>
          </div>
          <div>
            <dt>MC mean / median bankroll</dt>
            <dd>
              {money(mc?.terminal_bankroll?.mean)} / {money(mc?.terminal_bankroll?.median)}
            </dd>
          </div>
          <div>
            <dt>P(lose money) / P(≥1.5×)</dt>
            <dd>
              {pct(mc?.probabilities?.P_final_lt_B0)} / {pct(mc?.probabilities?.P_final_ge_1_5x)}
            </dd>
          </div>
          <div>
            <dt>MDD p5 / costs</dt>
            <dd>
              {pct(mc?.max_drawdown?.p5)} / fees {String(result.costs?.fees || "UNAVAILABLE")}
            </dd>
          </div>
          <div>
            <dt>Correlation</dt>
            <dd>{result.correlation?.status || "—"}</dd>
          </div>
          <div>
            <dt>risk_result_hash</dt>
            <dd className="ws-mono">{result.risk_result_hash || "—"}</dd>
          </div>
        </dl>
      ) : null}
    </section>
  );
}
