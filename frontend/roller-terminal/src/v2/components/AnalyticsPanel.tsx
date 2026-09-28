import { useMemo, useState } from "react";
import type { ResearchResult } from "../../ResultsView";
import { wilsonCi as wilsonInterval } from "../results/wilson";

type Props = {
  result: ResearchResult | null | undefined;
};

type Availability = "AVAILABLE" | "NOT AVAILABLE" | "ASSUMPTION REQUIRED";

type MetricRow = {
  group: string;
  name: string;
  availability: Availability;
  value: string;
  note: string;
};

function wilsonCi(successes: number, n: number, z = 1.96): [number, number] | null {
  const ci = wilsonInterval(successes, n, z);
  return ci ? [ci.lower, ci.upper] : null;
}

function rateFromMeasurement(m: { value?: number | null; detail?: Record<string, unknown> } | undefined) {
  if (!m) return null;
  if (typeof m.value === "number" && Number.isFinite(m.value)) return m.value;
  const d = m.detail || {};
  const t = typeof d.count_true === "number" ? d.count_true : null;
  const a = typeof d.count_available === "number" ? d.count_available : null;
  if (t != null && a != null && a > 0) return t / a;
  return null;
}

export default function AnalyticsPanel({ result }: Props) {
  const [entryCents, setEntryCents] = useState(80);
  const [exitCents, setExitCents] = useState(40);
  const [feeCents, setFeeCents] = useState(0);
  const [contracts, setContracts] = useState(1);

  const rows: MetricRow[] = useMemo(() => {
    const n = result?.summary?.population_n ?? result?.population?.count ?? null;
    const t40 = result?.measurements?.find((m) => m.name === "t40_rate");
    const yes = result?.measurements?.find((m) => m.name === "kalshi_yes_rate");
    const t40Rate = rateFromMeasurement(t40);
    const yesRate = rateFromMeasurement(yes);
    const t40True =
      typeof t40?.detail?.count_true === "number" ? t40.detail.count_true : null;
    const yesTrue =
      typeof yes?.detail?.count_true === "number" ? yes.detail.count_true : null;

    const out: MetricRow[] = [
      {
        group: "EMPIRICAL RATES",
        name: "Sample size",
        availability: n != null ? "AVAILABLE" : "NOT AVAILABLE",
        value: n != null ? String(n) : "NOT AVAILABLE",
        note: "Authoritative population count from execution.",
      },
      {
        group: "EMPIRICAL RATES",
        name: "T40 proportion",
        availability: t40Rate != null ? "AVAILABLE" : "NOT AVAILABLE",
        value: t40Rate != null ? `${(t40Rate * 100).toFixed(2)}%` : "NOT AVAILABLE",
        note: "Derived from authoritative T40 measurement.",
      },
      {
        group: "EMPIRICAL RATES",
        name: "Terminal YES proportion",
        availability: yesRate != null ? "AVAILABLE" : "NOT AVAILABLE",
        value: yesRate != null ? `${(yesRate * 100).toFixed(2)}%` : "NOT AVAILABLE",
        note: "Derived from authoritative Kalshi YES measurement.",
      },
    ];

    if (n != null && t40True != null) {
      const ci = wilsonCi(t40True, n);
      out.push({
        group: "DISTRIBUTION",
        name: "T40 Wilson 95% CI",
        availability: ci ? "AVAILABLE" : "NOT AVAILABLE",
        value: ci
          ? `${(ci[0] * 100).toFixed(2)}% – ${(ci[1] * 100).toFixed(2)}%`
          : "NOT AVAILABLE",
        note: "DERIVED FROM AUTHORITATIVE DATA (binomial Wilson interval).",
      });
    } else {
      out.push({
        group: "DISTRIBUTION",
        name: "T40 Wilson 95% CI",
        availability: "NOT AVAILABLE",
        value: "NOT AVAILABLE",
        note: "Authoritative inputs required for this metric are not currently bound.",
      });
    }

    if (n != null && yesTrue != null) {
      const ci = wilsonCi(yesTrue, n);
      out.push({
        group: "DISTRIBUTION",
        name: "YES Wilson 95% CI",
        availability: ci ? "AVAILABLE" : "NOT AVAILABLE",
        value: ci
          ? `${(ci[0] * 100).toFixed(2)}% – ${(ci[1] * 100).toFixed(2)}%`
          : "NOT AVAILABLE",
        note: "DERIVED FROM AUTHORITATIVE DATA (binomial Wilson interval).",
      });
    }

    out.push(
      {
        group: "VOLATILITY",
        name: "Path volatility",
        availability: "NOT AVAILABLE",
        value: "NOT AVAILABLE",
        note: "Authoritative inputs required for this metric are not currently bound to this research object.",
      },
      {
        group: "VOLATILITY",
        name: "Maximum adverse movement",
        availability: "NOT AVAILABLE",
        value: "NOT AVAILABLE",
        note: "Authoritative inputs required for this metric are not currently bound to this research object.",
      },
      {
        group: "RETURN ECONOMICS",
        name: "EV / Sharpe / P&L",
        availability: "ASSUMPTION REQUIRED",
        value: "ASSUMPTION REQUIRED",
        note: "Use Scenario Analysis below. Never blended with empirical rates.",
      },
      {
        group: "RISK",
        name: "Kelly / drawdown economics",
        availability: "ASSUMPTION REQUIRED",
        value: "ASSUMPTION REQUIRED",
        note: "Requires user-supplied economic model — not empirical execution.",
      },
    );

    return out;
  }, [result]);

  const yesRate = rateFromMeasurement(result?.measurements?.find((m) => m.name === "kalshi_yes_rate"));
  const scenario = useMemo(() => {
    if (yesRate == null) return null;
    const entry = entryCents / 100;
    const loss = exitCents / 100;
    const fee = feeCents / 100;
    const winPnL = 1 - entry - fee;
    const losePnL = -(entry - loss) - fee;
    // Hypothetical: win with terminal YES rate, else lose to exit rule — USER SCENARIO ONLY
    const ev = yesRate * winPnL + (1 - yesRate) * losePnL;
    const breakeven = (entry - loss + fee) / (1 - loss);
    return {
      evPerContract: ev,
      evScenario: ev * contracts,
      breakeven,
      winPnL,
      losePnL,
    };
  }, [yesRate, entryCents, exitCents, feeCents, contracts]);

  const groups = [...new Set(rows.map((r) => r.group))];

  return (
    <div className="v2-analytics">
      <p className="v2-lede">
        Metrics are classified by authoritative availability. Unavailable metrics render{" "}
        <span className="evidence">NOT AVAILABLE</span> — never fabricated.
      </p>

      {groups.map((g) => (
        <section key={g} className="v2-analytics-group">
          <h3 className="v2-kicker">{g}</h3>
          <table className="v2-analytics-table">
            <thead>
              <tr>
                <th>Metric</th>
                <th>Availability</th>
                <th>Value</th>
                <th>Note</th>
              </tr>
            </thead>
            <tbody>
              {rows
                .filter((r) => r.group === g)
                .map((r) => (
                  <tr key={r.name}>
                    <td>{r.name}</td>
                    <td className="evidence">{r.availability}</td>
                    <td className="evidence">{r.value}</td>
                    <td className="muted">{r.note}</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </section>
      ))}

      <section className="v2-scenario research-object">
        <div className="v2-kicker">Scenario analysis</div>
        <h3>Not empirical execution performance</h3>
        <p className="muted">
          USER-SUPPLIED HYPOTHETICAL ECONOMICS. Visually separate from authoritative measurements.
          No implied fills. No claim the trade was executable.
        </p>
        <div className="v2-filter-row">
          <label>
            Entry ¢
            <input
              type="number"
              value={entryCents}
              onChange={(e) => setEntryCents(Number(e.target.value))}
            />
          </label>
          <label>
            Exit / loss ¢
            <input
              type="number"
              value={exitCents}
              onChange={(e) => setExitCents(Number(e.target.value))}
            />
          </label>
          <label>
            Fee ¢
            <input
              type="number"
              value={feeCents}
              onChange={(e) => setFeeCents(Number(e.target.value))}
            />
          </label>
          <label>
            Contracts
            <input
              type="number"
              value={contracts}
              onChange={(e) => setContracts(Number(e.target.value))}
            />
          </label>
        </div>
        {scenario && yesRate != null ? (
          <div className="v2-metric-row">
            <div className="v2-metric">
              <div className="v2-metric-label">EV / contract</div>
              <div className="v2-metric-value evidence">{scenario.evPerContract.toFixed(4)}</div>
            </div>
            <div className="v2-metric">
              <div className="v2-metric-label">EV / scenario</div>
              <div className="v2-metric-value evidence">{scenario.evScenario.toFixed(4)}</div>
            </div>
            <div className="v2-metric">
              <div className="v2-metric-label">Breakeven p(YES)</div>
              <div className="v2-metric-value evidence">
                {(scenario.breakeven * 100).toFixed(2)}%
              </div>
            </div>
            <div className="v2-metric">
              <div className="v2-metric-label">Uses empirical p(YES)</div>
              <div className="v2-metric-value evidence">{(yesRate * 100).toFixed(2)}%</div>
              <div className="v2-metric-sub muted">Authoritative rate × user economics</div>
            </div>
          </div>
        ) : (
          <p className="muted">
            NOT AVAILABLE — Authoritative inputs required for this metric are not currently bound
            to this research object.
          </p>
        )}
      </section>
    </div>
  );
}
