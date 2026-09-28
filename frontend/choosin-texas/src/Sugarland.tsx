import { useCallback, useEffect, useMemo, useState } from "react";
import { fetchSugarland, UniverseError } from "./api";
import type { SugarlandContract, SugarlandPage, SugarlandStat } from "./types";

const KNOTS: { key: keyof SugarlandContract; label: string }[] = [
  { key: "h48", label: "48h" },
  { key: "h24", label: "24h" },
  { key: "h12", label: "12h" },
  { key: "h6", label: "6h" },
  { key: "h2", label: "2h" },
  { key: "h1", label: "1h" },
  { key: "p30", label: "T-30" },
];

function num(value: number | string | null | undefined): string {
  if (value === null || value === undefined || value === "UNAVAILABLE") return "UNAVAILABLE";
  if (typeof value === "string") return value;
  return value.toFixed(3);
}

function mean(values: number[]): number | null {
  if (!values.length) return null;
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function median(values: number[]): number | null {
  if (!values.length) return null;
  const ordered = [...values].sort((a, b) => a - b);
  const mid = Math.floor(ordered.length / 2);
  return ordered.length % 2 ? ordered[mid] : (ordered[mid - 1] + ordered[mid]) / 2;
}

function StatTable({ rows }: { rows: SugarlandStat[] }) {
  return (
    <table className="data-table">
      <thead>
        <tr>
          <th>Sport</th>
          <th>Cohort</th>
          <th>Eligible</th>
          <th>Endpoint</th>
          <th>Mean Δpp</th>
          <th>Median</th>
          <th>95% interval</th>
          <th>Share rising</th>
          <th>Return on ask</th>
          <th>Discovery</th>
          <th>Validation</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={`${row.sport}-${row.cohort}-${row.horizon_h ?? "a"}`}>
            <td>{row.sport}</td>
            <td>
              {row.cohort}
              {row.horizon_h !== undefined ? ` ${row.horizon_h}` : ""}
            </td>
            <td>{row.eligible_n}</td>
            <td>{row.endpoint_n}</td>
            <td>{num(row.mean_dpp)}</td>
            <td>{num(row.median_dpp)}</td>
            <td>
              {row.ci95_low === "INSUFFICIENT_SAMPLE"
                ? "INSUFFICIENT_SAMPLE"
                : `[${num(row.ci95_low)}, ${num(row.ci95_high)}]`}
            </td>
            <td>{num(row.share_rising)}</td>
            <td>{num(row.mean_return_on_ask)}</td>
            <td>
              {num(row.discovery_mean_dpp)} ({row.discovery_endpoint_n})
            </td>
            <td>
              {num(row.validation_mean_dpp)} ({row.validation_endpoint_n})
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function PathChart({ rows }: { rows: SugarlandContract[] }) {
  const complete = rows.filter((row) => KNOTS.every((knot) => typeof row[knot.key] === "number"));
  const series = KNOTS.map((knot) => {
    const vals = rows.map((row) => row[knot.key]).filter((value): value is number => typeof value === "number");
    const common = complete.map((row) => row[knot.key]).filter((value): value is number => typeof value === "number");
    return { label: knot.label, n: vals.length, mean: mean(vals), commonN: common.length, common: mean(common) };
  });
  const points = series.filter((item) => item.mean !== null) as { label: string; n: number; mean: number; common: number | null; commonN: number }[];
  if (!points.length) return <p className="muted">No fresh quotes on this slice.</p>;
  const ys = points.flatMap((item) => [item.mean, item.common].filter((value): value is number => value !== null));
  const min = Math.min(...ys);
  const max = Math.max(...ys);
  const span = max - min || 0.01;
  const width = 640;
  const height = 220;
  const x = (index: number) => 40 + (index * (width - 70)) / Math.max(points.length - 1, 1);
  const y = (value: number) => 20 + ((max - value) / span) * (height - 50);
  const line = (key: "mean" | "common") =>
    points
      .map((item, index) => (item[key] === null ? null : `${index === 0 ? "M" : "L"} ${x(index)} ${y(item[key] as number)}`))
      .filter(Boolean)
      .join(" ");
  return (
    <div>
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Pregame bid path and sample size">
        <path d={line("mean")} fill="none" stroke="#8fd4c8" strokeWidth="2" />
        <path d={line("common")} fill="none" stroke="#c4b48a" strokeWidth="2" />
        {points.map((item, index) => (
          <g key={item.label}>
            <circle cx={x(index)} cy={y(item.mean)} r="3" fill="#8fd4c8" />
            <text x={x(index)} y={height - 8} textAnchor="middle" fill="#8b8f98" fontSize="11">
              {item.label} n={item.n}
            </text>
          </g>
        ))}
      </svg>
      <p className="muted">
        Teal is every contract with a quote at that lead. Tan is the common-complete sample (n=
        {complete.length}). Counts are on the axis so a path cannot hide contracts entering or leaving.
      </p>
    </div>
  );
}

function Histogram({ values }: { values: number[] }) {
  if (!values.length) return <p className="muted">No endpoint bids on this slice.</p>;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const bins = 21;
  const width = max - min || 1;
  const counts = Array.from({ length: bins }, () => 0);
  for (const value of values) {
    const index = Math.min(bins - 1, Math.floor(((value - min) / width) * bins));
    counts[index] += 1;
  }
  const peak = Math.max(...counts);
  return (
    <svg viewBox="0 0 640 160" role="img" aria-label="Distribution of bid appreciation">
      {counts.map((count, index) => {
        const bar = (count / peak) * 120;
        return <rect key={index} x={20 + index * 28} y={140 - bar} width="22" height={bar} fill="#6e8cff" />;
      })}
      <text x="20" y="156" fill="#8b8f98" fontSize="11">
        {min.toFixed(2)} pp
      </text>
      <text x="560" y="156" fill="#8b8f98" fontSize="11">
        {max.toFixed(2)} pp
      </text>
    </svg>
  );
}

function cents(value: number | string | null | undefined): string {
  if (value === null || value === undefined || value === "UNAVAILABLE" || value === "INSUFFICIENT_SAMPLE") {
    return value === "INSUFFICIENT_SAMPLE" ? "INSUFFICIENT_SAMPLE" : "UNAVAILABLE";
  }
  if (typeof value === "string") return value;
  return value.toFixed(3);
}

function interval(cell: { ci95_low: number | string; ci95_high: number | string; interval_status: string } | undefined): string {
  if (!cell) return "UNAVAILABLE";
  if (cell.interval_status === "INSUFFICIENT_SAMPLE") return "INSUFFICIENT_SAMPLE";
  if (cell.interval_status === "UNAVAILABLE") return "UNAVAILABLE";
  return `[${cents(cell.ci95_low)}, ${cents(cell.ci95_high)}]`;
}

function Audit({ page }: { page: SugarlandPage }) {
  const blocks = page.audit?.blocks || [];
  const spread = blocks.filter((block) => block.spread_cents);
  const paired = blocks.filter((block) => block.paired);
  if (!spread.length && !paired.length) return null;
  return (
    <article className="wide">
      <h2>Endpoint and spread audit</h2>
      <p className="muted">
        These tables do not replace the frozen primary result. Quote profit in cents is exit bid minus entry ask. It equals bid
        appreciation minus the entry spread on the same complete sample. WNBA rows are library measurements and are not a dashboard sport.
      </p>
      <table className="data-table">
        <thead>
          <tr>
            <th>Sport</th>
            <th>Horizon</th>
            <th>Complete N</th>
            <th>Bid change ¢</th>
            <th>Entry spread ¢</th>
            <th>Quote profit ¢</th>
            <th>Profit interval</th>
            <th>Missing</th>
            <th>Boundary</th>
            <th>Stale</th>
            <th>Absent</th>
            <th>Wide spread</th>
            <th>Other</th>
          </tr>
        </thead>
        <tbody>
          {spread.map((block) => (
            <tr key={`${block.sport}-${block.horizon_h}-spread`}>
              <td>{block.sport}</td>
              <td>{block.horizon_h}h</td>
              <td>{block.spread_cents?.complete_n}</td>
              <td>{cents(block.spread_cents?.bid_appreciation_cents.mean_cents)}</td>
              <td>{cents(block.spread_cents?.entry_spread_cents.mean_cents)}</td>
              <td>{cents(block.spread_cents?.quote_profit_cents.mean_cents)}</td>
              <td>{interval(block.spread_cents?.quote_profit_cents)}</td>
              <td>{block.exclusions?.missing_n ?? "UNAVAILABLE"}</td>
              <td>{block.exclusions?.counts.BOUNDARY_QUOTE ?? "UNAVAILABLE"}</td>
              <td>{block.exclusions?.counts.STALE_OBSERVATION ?? "UNAVAILABLE"}</td>
              <td>{block.exclusions?.counts.ABSENT_CANDLES ?? "UNAVAILABLE"}</td>
              <td>{block.exclusions?.counts.EXCESSIVE_SPREAD ?? "UNAVAILABLE"}</td>
              <td>{block.exclusions?.counts.OTHER_EXCLUSION ?? "UNAVAILABLE"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <h2>Paired path from the 48h price</h2>
      <p className="muted">
        A contract enters because its 48h bid is around 80¢. It stays if it also has a 24h quote and a T−30 bid, including when the 24h bid
        has left that band.
      </p>
      <table className="data-table">
        <thead>
          <tr>
            <th>Sport</th>
            <th>Paired N</th>
            <th>Missing 24h</th>
            <th>Missing T−30</th>
            <th>Left band by 24h</th>
            <th>48h→24h ¢</th>
            <th>24h→T−30 ¢</th>
            <th>48h→T−30 ¢</th>
          </tr>
        </thead>
        <tbody>
          {paired.map((block) => (
            <tr key={`${block.sport}-paired`}>
              <td>{block.sport}</td>
              <td>{block.paired?.paired_n}</td>
              <td>{block.paired?.dropped_missing_24h}</td>
              <td>{block.paired?.dropped_missing_endpoint}</td>
              <td>{block.paired?.still_outside_around80_at_24h}</td>
              <td>
                {cents(block.paired?.cents_48_to_24.mean_cents)} {interval(block.paired?.cents_48_to_24)}
              </td>
              <td>
                {cents(block.paired?.cents_24_to_30.mean_cents)} {interval(block.paired?.cents_24_to_30)}
              </td>
              <td>
                {cents(block.paired?.cents_48_to_30.mean_cents)} {interval(block.paired?.cents_48_to_30)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </article>
  );
}

function downloadCsv(rows: SugarlandContract[]) {
  const header = ["ticker", "sport", "season", "game_date", "partition", "band", "lead_bucket", "dpp", "return_on_ask", "exclusion"];
  const body = rows.map((row) =>
    [row.ticker, row.sport, row.season, row.game_date, row.partition, row.band, row.lead_bucket, row.dpp ?? "", row.return_on_ask ?? "", row.exclusion]
      .map((cell) => `"${String(cell).replaceAll('"', '""')}"`)
      .join(","),
  );
  const blob = new Blob([[header.join(","), ...body].join("\n")], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "sugarland-nba-ncaab.csv";
  link.click();
  URL.revokeObjectURL(url);
}

export default function Sugarland() {
  const [page, setPage] = useState<SugarlandPage | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sport, setSport] = useState("NBA");
  const [view, setView] = useState("around48");
  const [season, setSeason] = useState("ALL");
  const [band, setBand] = useState("ALL");
  const [lead, setLead] = useState("ALL");
  const [partition, setPartition] = useState("ALL");

  const load = useCallback(async () => {
    try {
      const payload = await fetchSugarland();
      if (payload.status !== "OBSERVED") {
        setPage(null);
        setError(payload.message || payload.status);
        return;
      }
      setPage(payload);
      setError(null);
    } catch (err) {
      setPage(null);
      setError(err instanceof UniverseError || err instanceof Error ? err.message : String(err));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const seasons = useMemo(() => {
    const found = new Set((page?.contracts || []).filter((row) => row.sport === sport).map((row) => row.season));
    return ["ALL", ...Array.from(found).sort()];
  }, [page, sport]);

  const filtered = useMemo(() => {
    return (page?.contracts || []).filter((row) => {
      if (row.sport !== sport) return false;
      if (season !== "ALL" && row.season !== season) return false;
      if (partition !== "ALL" && row.partition !== partition) return false;
      if (band !== "ALL" && row.band !== band) return false;
      if (lead !== "ALL" && row.lead_bucket !== lead) return false;
      if (view === "around48") return row.h48_around80;
      if (view === "around24") return row.h24_around80;
      if (view === "union") return row.h48_around80 || row.h24_around80;
      if (view === "above70_48") return row.h48_above70;
      if (view === "cohort_a") return row.in_a;
      return true;
    });
  }, [page, sport, season, partition, band, lead, view]);

  function sliceDpp(row: SugarlandContract): number | null {
    if (view === "around48") return row.h48_dpp;
    if (view === "around24") return row.h24_dpp;
    if (view === "union") return row.h48_around80 ? row.h48_dpp : row.h24_dpp;
    return row.dpp;
  }
  function sliceAsk(row: SugarlandContract): number | null {
    if (view === "around48") return row.h48_return_on_ask;
    if (view === "around24") return row.h24_return_on_ask;
    if (view === "union") return row.h48_around80 ? row.h48_return_on_ask : row.h24_return_on_ask;
    return row.return_on_ask;
  }
  const dppValues = filtered.map(sliceDpp).filter((value): value is number => typeof value === "number");
  const askValues = filtered.map(sliceAsk).filter((value): value is number => typeof value === "number");
  const sliceMean = mean(dppValues);
  const sliceMedian = median(dppValues);
  const rising = dppValues.length ? dppValues.filter((value) => value > 0).length / dppValues.length : null;

  if (error) {
    return <p className="banner">{error}</p>;
  }
  if (!page) {
    return <p className="muted">Loading Sugarland…</p>;
  }

  const coverage = page.coverage[sport];

  return (
    <section>
      <p className="banner">Research only. Execution disabled. Quote paths are not fills and are not orders.</p>
      <article className="wide">
        <h2>Question</h2>
        <p>{page.question}</p>
        <p className="muted">
          {page.universe_id} · spec {page.spec_sha256.slice(0, 12)} · {page.library_note}
        </p>
        <ul>
          {page.limitations.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </article>
      <article className="wide">
        <h2>24–48h around 80¢</h2>
        <StatTable rows={page.tables.around_80} />
        <p className="muted">Return on ask is exit bid minus entry ask, divided by entry ask. It is a quote-based spread comparison. The cent comparison is in the audit.</p>
      </article>
      <Audit page={page} />
      <article className="wide">
        <h2>First-observed above 70</h2>
        <StatTable rows={page.tables.headline_first_observed_above_70} />
      </article>
      <article className="wide">
        <h2>Coverage</h2>
        {coverage ? (
          <p>
            {sport} games {coverage.games ?? "UNAVAILABLE"} · with clock {coverage.games_with_primary_clock ?? "UNAVAILABLE"} ·
            schedule exceptions {coverage.games_schedule_exception ?? "UNAVAILABLE"} · first-observed above 70{" "}
            {coverage.first_observed_above_70 ?? "UNAVAILABLE"} · missing endpoint {coverage.missing_endpoint_above_70 ?? "UNAVAILABLE"} ·
            listing time {coverage.listing_time ?? "UNAVAILABLE"}
          </p>
        ) : (
          <p>UNAVAILABLE</p>
        )}
        <p className="muted">
          Phase 8 parquet is inventory only and is not added to cohort N. NCAAB parquet games{" "}
          {page.parquet_inventory?.NCAAB?.games ?? "UNAVAILABLE"}, observation rows{" "}
          {page.parquet_inventory?.NCAAB?.observation_rows ?? "UNAVAILABLE"}. Order book{" "}
          {page.parquet_inventory?.NBA?.orderbook_data_available === false ? "UNAVAILABLE" : "see artifact"}.
        </p>
      </article>
      <article className="wide">
        <h2>Slice</h2>
        <p className="mast-meta">
          <label>
            Sport{" "}
            <select value={sport} onChange={(event) => setSport(event.target.value)}>
              <option>NBA</option>
              <option>NCAAB</option>
            </select>
          </label>
          <label>
            View{" "}
            <select value={view} onChange={(event) => setView(event.target.value)}>
              <option value="around48">48h around 80¢</option>
              <option value="around24">24h around 80¢</option>
              <option value="union">Union, 48h preferred</option>
              <option value="above70_48">48h above 70¢</option>
              <option value="cohort_a">First-observed above 70</option>
            </select>
          </label>
          <label>
            Season{" "}
            <select value={season} onChange={(event) => setSeason(event.target.value)}>
              {seasons.map((item) => (
                <option key={item}>{item}</option>
              ))}
            </select>
          </label>
          <label>
            Band{" "}
            <select value={band} onChange={(event) => setBand(event.target.value)}>
              {["ALL", "(70,75)", "[75,80)", "[80,85)", "[85,90)", "[90,100)", "other"].map((item) => (
                <option key={item}>{item}</option>
              ))}
            </select>
          </label>
          <label>
            Lead{" "}
            <select value={lead} onChange={(event) => setLead(event.target.value)}>
              {["ALL", "[0,1)", "[1,2)", "[2,6)", "[6,12)", "[12,24)", "[24,48)", ">=48"].map((item) => (
                <option key={item}>{item}</option>
              ))}
            </select>
          </label>
          <label>
            Partition{" "}
            <select value={partition} onChange={(event) => setPartition(event.target.value)}>
              <option>ALL</option>
              <option value="discovery">discovery</option>
              <option value="validation">validation</option>
            </select>
          </label>
        </p>
        <p>
          Slice N {filtered.length}. Endpoint bids {dppValues.length}. Mean Δpp {sliceMean === null ? "UNAVAILABLE" : sliceMean.toFixed(3)}.
          Median {sliceMedian === null ? "UNAVAILABLE" : sliceMedian.toFixed(3)}. Share rising{" "}
          {rising === null ? "UNAVAILABLE" : rising.toFixed(3)}. Mean return on ask{" "}
          {askValues.length ? (askValues.reduce((sum, value) => sum + value, 0) / askValues.length).toFixed(4) : "UNAVAILABLE"}.
        </p>
        <p className="muted">
          The date-block interval in the tables above is the unfiltered sport result. A filtered slice does not invent a new interval.
          Lead-time buckets use the primary clock and are descriptive.
        </p>
        <PathChart rows={filtered} />
        <Histogram values={dppValues} />
        <p>
          Slopes reported only when coverage gates pass. On this slice,{" "}
          {filtered.filter((row) => row.slope_status === "OK").length} of {filtered.length} have a slope.
        </p>
        <button type="button" onClick={() => downloadCsv(filtered)}>
          Export slice CSV
        </button>
        <table className="data-table">
          <thead>
            <tr>
              <th>Ticker</th>
              <th>Date</th>
              <th>Partition</th>
              <th>Band</th>
              <th>Δpp</th>
              <th>Return on ask</th>
              <th>Exclusion</th>
            </tr>
          </thead>
          <tbody>
            {filtered.slice(0, 40).map((row) => (
              <tr key={row.ticker}>
                <td>{row.ticker}</td>
                <td>{row.game_date}</td>
                <td>{row.partition || "UNAVAILABLE"}</td>
                <td>{row.band || ""}</td>
                <td>{num(sliceDpp(row))}</td>
                <td>{num(sliceAsk(row))}</td>
                <td>{row.exclusion || ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </article>
    </section>
  );
}
