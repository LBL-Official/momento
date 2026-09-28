/** Presentational charts from authoritative measurement values only. No invented rates. */

type MeasurementLike = {
  name?: string;
  status?: string;
  value?: number | null;
  detail?: Record<string, unknown>;
};

function rateParts(m: MeasurementLike | undefined): {
  trueN: number | null;
  avail: number | null;
  rate: number | null;
} {
  if (!m) return { trueN: null, avail: null, rate: null };
  const d = m.detail || {};
  const trueN = typeof d.count_true === "number" ? d.count_true : null;
  const avail = typeof d.count_available === "number" ? d.count_available : null;
  const rate =
    typeof m.value === "number" && Number.isFinite(m.value)
      ? m.value
      : trueN != null && avail != null && avail > 0
        ? trueN / avail
        : null;
  return { trueN, avail, rate };
}

function RateRow({
  label,
  m,
  tone,
}: {
  label: string;
  m: MeasurementLike | undefined;
  tone: "a" | "b";
}) {
  const { trueN, avail, rate } = rateParts(m);
  const pct = rate == null ? 0 : Math.max(0, Math.min(1, rate)) * 100;
  const pctLabel = rate == null ? "—" : `${pct.toFixed(1)}%`;
  const countLabel =
    trueN != null && avail != null ? `${trueN} / ${avail}` : "—";

  return (
    <div className="rate-row">
      <div className="rate-row-meta">
        <span className="rate-row-label">{label}</span>
        <span className="rate-row-value evidence">{pctLabel}</span>
        <span className="rate-row-count muted evidence">{countLabel}</span>
      </div>
      <div className="chart-bar-track" aria-hidden="true">
        <div
          className={`chart-bar-fill chart-bar-fill-${tone}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

export default function ResultsCharts({
  populationN,
  t40,
  kalshi,
}: {
  populationN: number | null | undefined;
  t40: MeasurementLike | undefined;
  kalshi: MeasurementLike | undefined;
}) {
  return (
    <section className="results-charts" aria-label="Result charts">
      <div className="results-charts-head">
        <h2>Rates</h2>
        {populationN != null ? (
          <span className="muted small evidence">N = {populationN}</span>
        ) : null}
      </div>
      <RateRow label="Path · T40" m={t40} tone="a" />
      <RateRow label="Terminal · YES" m={kalshi} tone="b" />
    </section>
  );
}
