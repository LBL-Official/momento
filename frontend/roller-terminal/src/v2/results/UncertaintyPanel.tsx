import type { DetailPayload } from "../components/DetailDrawer";
import { formatPct, wilsonCi } from "./wilson";
import type { AnswerResult } from "./ResultsAnswer";
import { pathRate, terminalRate } from "./measurementLookup";
import { jointIsMeasured } from "./partitionTypes";

type Props = {
  result: AnswerResult;
  onOpenDetail: (detail: DetailPayload) => void;
};

export default function UncertaintyPanel({ result, onOpenDetail }: Props) {
  const path = pathRate(result);
  const yes = terminalRate(result);
  const partition = result.empirical_partition;
  const joint = jointIsMeasured(partition);
  const tAndW = partition?.cells?.find((c) => c.key === "T_AND_W" || (c.path_true && c.terminal_true));
  const tRow = partition?.cells?.filter((c) => c.path_true).reduce((s, c) => s + c.n, 0) ?? null;
  const notTRow = partition?.cells?.filter((c) => c.path_true === false).reduce((s, c) => s + c.n, 0) ?? null;

  const cards: Array<{
    title: string;
    successes: number | null;
    n: number | null;
    label: string;
  }> = [
    {
      title: path.name === "t40_rate" ? "P(T40)" : "P(PATH)",
      successes: path.trueN,
      n: path.avail,
      label: path.name,
    },
  ];
  if (yes.avail != null && yes.trueN != null) {
    cards.push({ title: "P(W)", successes: yes.trueN, n: yes.avail, label: yes.name });
  }
  if (joint && tAndW && tRow) {
    cards.push({
      title: "P(W | PATH)",
      successes: tAndW.n,
      n: tRow,
      label: "P(W|PATH)",
    });
  }
  if (joint && notTRow) {
    const notTAndW = (partition?.cells ?? [])
      .filter((c) => c.path_true === false && c.terminal_true)
      .reduce((s, c) => s + c.n, 0);
    cards.push({
      title: "P(W | ¬PATH)",
      successes: notTAndW,
      n: notTRow,
      label: "P(W|¬PATH)",
    });
  }

  return (
    <section className="ws-level">
      <p className="v2-kicker">Level 3 · How certain is the measurement?</p>
      <h2>Uncertainty</h2>
      <p className="muted small">
        Wilson 95% interval from this run’s successes and denominator. Independence is not assumed.
      </p>
      <div className="ws-breakdown">
        {cards.map((c) => {
          const ci = c.successes != null && c.n != null && c.n > 0 ? wilsonCi(c.successes, c.n) : null;
          return (
            <button
              key={c.title}
              type="button"
              className="ws-breakdown-card"
              onClick={() =>
                onOpenDetail({
                  title: c.title,
                  value: ci ? formatPct(ci.p) : "—",
                  subtitle:
                    c.successes != null && c.n != null ? `${c.successes} / ${c.n}` : undefined,
                  sections: [
                    {
                      heading: "Point estimate",
                      body: <p>{ci ? formatPct(ci.p, 2) : "Not currently measured"}</p>,
                    },
                    {
                      heading: "Wilson 95% interval",
                      body: (
                        <p className="evidence">
                          {ci ? `${formatPct(ci.lower, 2)} — ${formatPct(ci.upper, 2)}` : "—"}
                        </p>
                      ),
                    },
                    {
                      heading: "Success / failure / denominator",
                      body: (
                        <p>
                          {c.successes ?? "—"} successes ·{" "}
                          {c.successes != null && c.n != null ? c.n - c.successes : "—"} failures · N ={" "}
                          {c.n ?? "—"}
                        </p>
                      ),
                    },
                    {
                      heading: "Caveats",
                      body: (
                        <p>
                          Sample size is the measurement denominator. Dependence and regime
                          concentration are not modeled. Out-of-sample status is not claimed.
                        </p>
                      ),
                    },
                  ],
                })
              }
            >
              <div className="v2-kicker">{c.title}</div>
              <div className="ws-breakdown-value evidence">{ci ? formatPct(ci.p) : "—"}</div>
              <div className="muted small">
                {ci ? `Wilson 95% ${formatPct(ci.lower)} — ${formatPct(ci.upper)}` : "Not measured"}
              </div>
              {c.successes != null && c.n != null ? (
                <div className="evidence small">
                  {c.successes} / {c.n}
                </div>
              ) : null}
            </button>
          );
        })}
      </div>
    </section>
  );
}
