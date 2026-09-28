import type { DetailPayload } from "../components/DetailDrawer";
import type { AnswerResult } from "./ResultsAnswer";
import type { WorkflowDraft } from "../workflow/types";
import { computeFiniteMath } from "./finiteMath";
import { formatPct, wilsonCi } from "./wilson";
import { LAST_TRADE_UNAVAILABLE } from "./lastTradeBasis";
import { economicsOpen, readResultsContract } from "./resultsContract";

type Props = {
  result: AnswerResult;
  draft?: WorkflowDraft | null;
  onOpenDetail: (detail: DetailPayload) => void;
};

function fmtCents(v: number | null): string {
  if (v == null || !Number.isFinite(v)) return "—";
  const sign = v > 0 ? "+" : "";
  return `${sign}${v.toFixed(2)}¢`;
}

export default function FiniteMathPanel({ result, draft, onOpenDetail }: Props) {
  const math = computeFiniteMath(result, draft);
  const contract = readResultsContract(result);
  const lastPrint = contract.lastTrade;
  const evOpen = economicsOpen(contract.economics.observedPathEv);
  const modelAOpen = economicsOpen(contract.economics.modelA);
  const ci =
    math.pathTrue != null && math.pathAvail != null && math.pathAvail > 0
      ? wilsonCi(math.pathTrue, math.pathAvail)
      : null;

  const cards = [
    {
      title: "Observed path",
      value: formatPct(math.pathRate),
      sub:
        math.pathTrue != null && math.pathAvail != null
          ? `${math.pathTrue} / ${math.pathAvail}`
          : "Not measured",
    },
    {
      title: "Wilson 95%",
      value: ci ? `${formatPct(ci.lower)} – ${formatPct(ci.upper)}` : "—",
      sub: ci ? "score interval on path rate" : "Need successes / N",
    },
    {
      title: lastPrint
        ? "Observed executable-path EV"
        : modelAOpen || math.modelA
          ? "Model A EV"
          : "Hypothetical EV",
      value: lastPrint
        ? "UNAVAILABLE"
        : modelAOpen
          ? fmtCents(contract.economics.modelA.estimate_cents ?? math.modelAEvCents)
          : evOpen
            ? fmtCents(contract.economics.observedPathEv.estimate_cents ?? math.observedEvCents)
            : "UNAVAILABLE",
      sub: lastPrint
        ? LAST_TRADE_UNAVAILABLE
        : modelAOpen || math.modelA
          ? "20 − 60q · +20 / −40 / 0 leak"
          : evOpen && math.observedN
            ? `mean exit−entry · n = ${math.observedN}`
            : contract.economics.observedPathEv.reason ?? "No exit closes in this result",
    },
    {
      title: "Max drawdown",
      value: lastPrint
        ? "UNAVAILABLE"
        : math.maxDrawdownCents != null
          ? `${math.maxDrawdownCents}¢`
          : "—",
      sub: lastPrint ? LAST_TRADE_UNAVAILABLE : math.maxDrawdownSource ?? "P&L sequence required",
    },
    {
      title: "Risk of ruin",
      value: lastPrint
        ? "UNAVAILABLE"
        : math.riskOfRuin != null
          ? `${(math.riskOfRuin * 100).toFixed(2)}%`
          : "—",
      sub: lastPrint
        ? LAST_TRADE_UNAVAILABLE
        : `$50 snapshot · ${math.riskOfRuinSource ?? "not measured"}`,
    },
  ];

  return (
    <section className="ws-level ws-finite-math">
      <p className="v2-kicker">Level 2 · Finite math</p>
      <h2>Backtest report</h2>
      <p className="muted small">
        {lastPrint
          ? "LAST TRADE ≠ EXECUTABLE PRICE. Model A and path EV are UNAVAILABLE on this basis."
          : "HYPOTHETICAL · CANDLE PATH ≠ FILL. Model A 80→40 payoffs apply only to enter-80 / reach-40. Other queries use observed exit−entry when an exit bar exists. Settlement is never invented."}
      </p>
      <div className="ws-breakdown">
        {cards.map((c) => (
          <button
            key={c.title}
            type="button"
            className="ws-breakdown-card"
            onClick={() =>
              onOpenDetail({
                title: c.title,
                value: c.value,
                subtitle: c.sub,
                sections: [
                  {
                    heading: "What this is",
                    body: (
                      <p>
                        {c.title === "Model A EV" || c.title === "Hypothetical EV"
                          ? math.modelA
                            ? "Documented FIRST80 Model A: EV_cents = 20 − 60q where q is P(hit 40). Survive +20¢, close-40 −40¢, leak 0."
                            : "Mean of hyp_pnl_cents = (exit_close − entry_close) / 100 on rows that have an observed exit bar."
                          : c.title === "Risk of ruin"
                            ? "Asymptotic gambler’s ruin on a $50 research snapshot: ratio = ((1−p)/p)×(L/W); RoR = 1 if ratio ≥ 1 else ratio^(bankroll/L)."
                            : c.title === "Max drawdown"
                              ? "Peak-to-trough on the chronological hypothetical P&L sequence. Not live account equity."
                              : "Wilson score interval from this run’s path successes and denominator."}
                      </p>
                    ),
                  },
                  {
                    heading: "Caveats",
                    body: (
                      <p>
                        CANDLE PATH ≠ FILL. MEASUREMENT ≠ EDGE. Ruin math assumes independent
                        identical trials and is not a live-account forecast.
                      </p>
                    ),
                  },
                ],
              })
            }
          >
            <div className="v2-kicker">{c.title}</div>
            <div className="ws-breakdown-value evidence">{c.value}</div>
            <div className="muted small">{c.sub}</div>
          </button>
        ))}
      </div>
    </section>
  );
}
