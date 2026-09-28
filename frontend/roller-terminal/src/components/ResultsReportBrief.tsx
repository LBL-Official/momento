import type { Ref } from "react";

/** Plain-English report brief from authoritative result fields only. No invented rates or edge claims. */

type MeasurementLike = {
  name?: string;
  status?: string;
  value?: number | null;
  detail?: Record<string, unknown>;
  caveat?: string | null;
};

type SpecLike = {
  identity?: { name?: string; description?: string } | null;
  population_binding?: {
    leagues?: string[];
    default_structural_slices?: string[];
  } | null;
  anchor?: { event?: string; price_e4?: number | null } | null;
  path_conditions?: unknown[];
  terminal_conditions?: unknown[];
} | null;

function fmtPct(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return "—";
  return `${(v * 100).toFixed(1)}%`;
}

function rateParts(m: MeasurementLike | undefined) {
  if (!m) return { trueN: null as number | null, avail: null as number | null, rate: null as number | null };
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

function questionLine(spec: SpecLike): string {
  const leagues = spec?.population_binding?.leagues ?? [];
  const slices = spec?.population_binding?.default_structural_slices ?? [];
  const event = spec?.anchor?.event;
  const price = spec?.anchor?.price_e4;
  const parts: string[] = [];
  if (leagues.length) parts.push(leagues.join(" / "));
  if (slices.length) parts.push(slices.join(" / "));
  if (event === "FIRST_PRICE_TOUCH" && typeof price === "number") {
    parts.push(`first touch at ${Math.round(price / 100)}¢`);
  } else if (event && event !== "OBSERVATION_TIME") {
    parts.push(event.replace(/_/g, " ").toLowerCase());
  }
  if (parts.length) return parts.join(" · ");
  const name = spec?.identity?.name?.trim();
  if (name) return name.replace(/_/g, " ");
  return "Executed research object";
}

function Metric({
  label,
  value,
  sub,
}: {
  label: string;
  value: string;
  sub: string;
}) {
  return (
    <div className="report-metric">
      <div className="report-metric-label">{label}</div>
      <div className="report-metric-value evidence">{value}</div>
      <div className="report-metric-sub muted">{sub}</div>
    </div>
  );
}

export default function ResultsReportBrief({
  spec,
  populationN,
  populationDescription,
  t40,
  kalshi,
  executionStatus,
  isStale,
  titleRef,
}: {
  spec: SpecLike;
  populationN: number | null | undefined;
  populationDescription?: string | null;
  t40: MeasurementLike | undefined;
  kalshi: MeasurementLike | undefined;
  executionStatus?: string;
  isStale: boolean;
  titleRef?: Ref<HTMLHeadingElement>;
}) {
  const t40p = rateParts(t40);
  const kalp = rateParts(kalshi);
  const headline = questionLine(spec);

  return (
    <section className="results-report" aria-label="Research report">
      <div className="results-report-top">
        <div>
          <div className="results-report-kicker">Measurement report</div>
          <h2 className="results-report-title" id="results-heading" tabIndex={-1} ref={titleRef}>
            {headline}
          </h2>
        </div>
        <div className="results-report-status">
          {isStale ? (
            <span className="pill status-STALE">PRIOR</span>
          ) : (
            <span className={`pill status-${executionStatus}`}>{executionStatus ?? "—"}</span>
          )}
        </div>
      </div>

      {isStale ? (
        <p className="notice results-report-note">
          Spec changed since this run — numbers still answer the executed question.
        </p>
      ) : null}

      <div className="report-metrics">
        <Metric
          label="Population"
          value={populationN != null ? String(populationN) : "—"}
          sub={populationDescription ? "matched observations" : "N"}
        />
        <Metric
          label="Path · T40"
          value={fmtPct(t40p.rate)}
          sub={
            t40p.trueN != null && t40p.avail != null
              ? `${t40p.trueN} of ${t40p.avail} · not a win rate`
              : "path proportion"
          }
        />
        <Metric
          label="Terminal · YES"
          value={fmtPct(kalp.rate)}
          sub={
            kalp.trueN != null && kalp.avail != null
              ? `${kalp.trueN} of ${kalp.avail} · not edge`
              : "settlement proportion"
          }
        />
      </div>

      <p className="results-report-footnote muted small">
        MEASUREMENT ≠ EDGE · Survive ≠ terminal yes · Candle path ≠ fill
      </p>
    </section>
  );
}
