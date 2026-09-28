import { useEffect, useMemo, useState } from "react";
import { UniverseError, fetchLubbock } from "./api";
import { text } from "./text";

type Interval = { lo?: string; hi?: string; estimate?: string };
type Bucket = {
  bucket_id?: string;
  status?: string;
  schedule_completeness?: string;
  warehouse_games?: string;
  canonical_linked_games?: string;
  first80_rows?: string;
  first80_games?: string;
  rank_lo?: string;
  rank_hi?: string;
  progress_lo?: string;
  progress_hi?: string;
  date_min?: string;
  date_max?: string;
  p_t40?: string;
  p_yes?: string;
  p_t40_wilson?: Interval;
  p_yes_wilson?: Interval;
  gap_vs_0_80?: string;
  mean_observed_entry_cents?: string;
  calibration_residual?: string;
  brier?: string;
  gross_ev_cents?: string;
  gross_ev_interval?: Interval;
  legacy_shorthand_ev_cents?: string;
  hold_ev_cents?: string;
  stop_minus_hold_cents?: string;
  net_ev?: string;
  path_completeness?: string;
  win_no_t40?: string;
  win_t40?: string;
  loss_no_t40?: string;
  loss_t40?: string;
  overlapping?: boolean;
  entry_bands?: Record<string, string>;
};
type Contrast = {
  estimate?: string;
  lo?: string;
  hi?: string;
  classification?: string;
  n_dates_late?: string;
  n_dates_early?: string;
  n_late?: string;
  n_early?: string;
  p?: string;
  block?: string;
  unsupported_late_rows?: string;
};
type Daily = { league_local_date: string; games: string; cumulative_games: string; cumulative_progress: string };
type Series = {
  sport: string;
  season_id: string;
  phase: string;
  universe_id: string;
  holm_primary: boolean;
  role: string;
  schedule_completeness: string;
  warehouse_games: string;
  date_min: string;
  date_max: string;
  start_basis_counts: Record<string, string>;
  first80_rows: string;
  candle_basis: string;
  net_ev: string;
  live_execution: boolean;
  submits: boolean;
  whole: Bucket;
  deciles: Bucket[];
  quintiles: Bucket[];
  cumulative: Bucket[];
  contrasts: Record<string, Contrast>;
  daily: Daily[];
};
type Conclusion = {
  sport: string;
  season_id: string;
  classification: string;
  holm_p: string;
  statement: string;
};
type LubbockPage = {
  schedule_completeness: string;
  net_ev: string;
  submits: boolean;
  live_execution: boolean;
  path_status: string;
  interpretation: string;
  holm: { label: string; p: string; holm_p: string }[];
  identity: { note: string; nba_604: number; ncaab_332: number; wnba_246: number; derived_four: number };
  conclusions: Conclusion[];
  series: Series[];
};

const GRAIN: Record<string, keyof Pick<Series, "deciles" | "quintiles" | "cumulative">> = {
  decile: "deciles",
  quintile: "quintiles",
  cumulative: "cumulative",
};

function num(value: string | undefined): number | null {
  if (!value || value === "UNAVAILABLE" || value === "NOT_APPLICABLE") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function span(lo: string | undefined, hi: string | undefined): string {
  if (!lo || !hi || lo === "UNAVAILABLE") return "UNAVAILABLE";
  return `${lo} to ${hi}`;
}

function Bars({
  buckets,
  label,
  valueOf,
  loOf,
  hiOf,
}: {
  buckets: Bucket[];
  label: string;
  valueOf: (bucket: Bucket) => string | undefined;
  loOf: (bucket: Bucket) => string | undefined;
  hiOf: (bucket: Bucket) => string | undefined;
}) {
  const points = buckets.filter((bucket) => bucket.status === "OBSERVED" && num(valueOf(bucket)) != null);
  const samples = points.flatMap((bucket) => [num(loOf(bucket)), num(hiOf(bucket)), num(valueOf(bucket))].filter((v): v is number => v != null));
  if (!points.length || !samples.length) {
    return <p className="banner">Interval plot UNAVAILABLE</p>;
  }
  const low = Math.min(...samples);
  const high = Math.max(...samples);
  const pad = high === low ? 1 : (high - low) * 0.12;
  const y0 = low - pad;
  const y1 = high + pad;
  const width = 640;
  const height = 180;
  const y = (value: number) => height - 16 - ((value - y0) / (y1 - y0)) * (height - 32);
  const step = width / points.length;
  return (
    <svg className="lubbock-plot" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={label}>
      <text x="8" y="14" className="plot-label">
        {label}
      </text>
      {points.map((bucket, index) => {
        const estimate = num(valueOf(bucket));
        const lo = num(loOf(bucket));
        const hi = num(hiOf(bucket));
        if (estimate == null) return null;
        const x = step * index + step / 2;
        return (
          <g key={bucket.bucket_id}>
            {lo != null && hi != null ? <line x1={x} x2={x} y1={y(lo)} y2={y(hi)} /> : null}
            <circle cx={x} cy={y(estimate)} r="3.5" />
            <text x={x} y={height - 2} textAnchor="middle">
              {bucket.bucket_id}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

export default function Lubbock() {
  const [page, setPage] = useState<LubbockPage | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sport, setSport] = useState("NBA");
  const [season, setSeason] = useState("2025-2026");
  const [phase, setPhase] = useState("REGULAR_SEASON");
  const [grain, setGrain] = useState("decile");
  const [universe, setUniverse] = useState("primary");

  useEffect(() => {
    fetchLubbock<LubbockPage>()
      .then((payload) => {
        setPage(payload);
        const primary = payload.series.find((row) => row.sport === "NBA" && row.holm_primary);
        if (primary) {
          setSeason(primary.season_id);
          setPhase(primary.phase);
        }
      })
      .catch((err: unknown) => {
        setError(err instanceof UniverseError ? err.message : "Lubbock UNAVAILABLE");
      });
  }, []);

  const sportRows = useMemo(() => (page?.series || []).filter((row) => row.sport === sport), [page, sport]);
  const seasons = useMemo(() => [...new Set(sportRows.map((row) => row.season_id))], [sportRows]);
  const activeSeason = seasons.includes(season)
    ? season
    : sportRows.find((row) => row.holm_primary)?.season_id || seasons[0] || season;
  const phases = useMemo(
    () => [...new Set(sportRows.filter((row) => row.season_id === activeSeason).map((row) => row.phase))],
    [sportRows, activeSeason],
  );
  const activePhase = phases.includes(phase) ? phase : phases.includes("REGULAR_SEASON") ? "REGULAR_SEASON" : phases[0] || phase;
  const series = sportRows.find((row) => row.season_id === activeSeason && row.phase === activePhase);
  const buckets = series ? series[GRAIN[grain] || "deciles"] : [];
  const disjoint = series ? (grain === "quintile" ? series.quintiles : series.deciles) : [];
  const conclusion = page?.conclusions.find((row) => row.sport === sport && row.season_id === activeSeason);
  const holm = page?.holm.find((row) => row.label === sport);

  if (error) return <p className="banner">{text(error)}</p>;
  if (!page || !series) return <p className="banner">Loading Lubbock.</p>;

  const exportHref = `/api/choosin-texas/lubbock/export.csv?sport=${encodeURIComponent(sport)}&season=${encodeURIComponent(activeSeason)}&phase=${encodeURIComponent(activePhase)}&grain=${encodeURIComponent(grain)}`;
  const identityAliases =
    sport === "NBA"
      ? [
          ["primary", "Austin/Dallas 604"],
          ["derived", "Derived-four NBA, same rows"],
          ["asked", "Asked-six NBA, same rows"],
        ]
      : sport === "NCAAB"
        ? [
            ["primary", "Derived-four 332"],
            ["asked", "Asked-six NCAAB, same rows"],
          ]
        : [["primary", series.universe_id]];

  return (
    <section>
      <p className="banner">
        Research only. Live execution disabled. Submits false. Net EV {text(page.net_ev)}. Candle path is not a fill.
        Schedule completeness {text(page.schedule_completeness)}. Path status {text(page.path_status)}. Findings are not an execution filter.
      </p>
      <div className="lubbock-controls">
        <label>
          Sport
          <select
            value={sport}
            onChange={(event) => {
              setSport(event.target.value);
              setUniverse("primary");
            }}
          >
            {["NBA", "NCAAB", "WNBA", "MLB"].map((item) => (
              <option key={item}>{item}</option>
            ))}
          </select>
        </label>
        <label>
          Season
          <select value={activeSeason} onChange={(event) => setSeason(event.target.value)}>
            {seasons.map((item) => (
              <option key={item}>{item}</option>
            ))}
          </select>
        </label>
        <label>
          Universe
          <select value={universe} onChange={(event) => setUniverse(event.target.value)}>
            {identityAliases.map(([id, label]) => (
              <option key={id} value={id}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label>
          Phase
          <select value={activePhase} onChange={(event) => setPhase(event.target.value)}>
            {phases.map((item) => (
              <option key={item}>{item}</option>
            ))}
          </select>
        </label>
        <label>
          Buckets
          <select value={grain} onChange={(event) => setGrain(event.target.value)}>
            <option value="decile">Deciles</option>
            <option value="quintile">Quintiles</option>
            <option value="cumulative">Cumulative</option>
          </select>
        </label>
        <a href={exportHref}>Download CSV</a>
      </div>
      <p className="banner">
        Universe {text(series.universe_id)}. Role {text(series.role)}. {universe === "primary" ? "Primary universe." : "Identity check. Same rows. Not a second Holm test."}{" "}
        {text(page.identity.note)} N in this phase {text(series.first80_rows)}. Warehouse-covered G {text(series.warehouse_games)}. Denominator{" "}
        {text(series.schedule_completeness)}. Dates {text(series.date_min)} to {text(series.date_max)}. Basis {text(series.candle_basis)}. Execution disabled.
      </p>

      <h2>Schedule and coverage</h2>
      <p>
        Schedule completeness and FIRST80 coverage are separate. G is retrospective warehouse metadata, not a claim that the official season is complete.
        Coverage limits kept out of the denominator: NBA 1230, NCAAB P5 721, WNBA 589. Start basis {text(JSON.stringify(series.start_basis_counts))}.
      </p>
      <div className="scroll-table">
        <table className="data-table">
          <thead>
            <tr>
              <th>League-local date</th>
              <th>Games</th>
              <th>Cumulative games</th>
              <th>Cumulative progress</th>
            </tr>
          </thead>
          <tbody>
            {series.daily.map((row) => (
              <tr key={row.league_local_date}>
                <td>{text(row.league_local_date)}</td>
                <td>{text(row.games)}</td>
                <td>{text(row.cumulative_games)}</td>
                <td>{text(row.cumulative_progress)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h2>Terminal outcomes</h2>
      <BucketTable
        buckets={buckets}
        columns={[
          ["p_yes", "YES rate"],
          ["gap_vs_0_80", "Gap vs 0.80"],
          ["mean_observed_entry_cents", "Mean observed entry"],
          ["calibration_residual", "Calibration residual"],
          ["brier", "Brier"],
        ]}
      />

      <h2>Path outcomes</h2>
      <p>
        The four cells require both a valid settlement and a valid T40 flag. They are legacy classifications. Every row is
        PATH_COMPLETENESS_UNVERIFIED. Terminal YES rate may use a larger settlement denominator.
      </p>
      <BucketTable
        buckets={buckets}
        columns={[
          ["p_t40", "P(T40)"],
          ["win_no_t40", "Win, no T40"],
          ["win_t40", "Win, T40"],
          ["loss_no_t40", "Loss, no T40"],
          ["loss_t40", "Loss, T40"],
          ["path_completeness", "Path status"],
        ]}
      />

      <h2>EV</h2>
      <p>Explicit gross EV is cents per contract. The legacy shorthand is a check, not a replacement. Net EV is UNAVAILABLE.</p>
      <BucketTable
        buckets={buckets}
        columns={[
          ["gross_ev_cents", "Gross EV"],
          ["legacy_shorthand_ev_cents", "Legacy shorthand"],
          ["hold_ev_cents", "Hold EV"],
          ["stop_minus_hold_cents", "Stop minus hold"],
          ["net_ev", "Net EV"],
        ]}
      />

      <h2>Warehouse-relative contrasts</h2>
      <p>
        Official-season final 10% and final 20% contrasts are UNAVAILABLE. Warehouse-relative deciles describe covered
        games only. Distinct active dates are a count, not a claim that the dates are independent.
      </p>
      <table className="data-table">
        <thead>
          <tr>
            <th>Contrast</th>
            <th>Estimate</th>
            <th>Interval</th>
            <th>Classification</th>
            <th>Distinct dates late</th>
            <th>Distinct dates earlier</th>
            <th>N late</th>
            <th>N earlier</th>
            <th>p</th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(series.contrasts).map(([name, contrast]) => (
            <tr key={name}>
              <td>{text(name)}</td>
              <td>{text(contrast.estimate)}</td>
              <td>{text(span(contrast.lo, contrast.hi))}</td>
              <td>{text(contrast.classification)}</td>
              <td>{text(contrast.n_dates_late)}</td>
              <td>{text(contrast.n_dates_early)}</td>
              <td>{text(contrast.n_late)}</td>
              <td>{text(contrast.n_early)}</td>
              <td>
                {text(contrast.p)}
                {name === "primary_ev" && series.holm_primary ? ` Holm ${text(holm?.holm_p)}` : ""}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {conclusion ? <p className="banner">{text(conclusion.statement)}</p> : <p className="banner">No regular-season conclusion for this phase.</p>}

      <h2>Disjoint buckets</h2>
      <div className="grid">
        <Bars
          buckets={disjoint}
          label="P(T40) with Wilson interval"
          valueOf={(bucket) => bucket.p_t40}
          loOf={(bucket) => bucket.p_t40_wilson?.lo}
          hiOf={(bucket) => bucket.p_t40_wilson?.hi}
        />
        <Bars
          buckets={disjoint}
          label="Gross EV cents with percentile interval"
          valueOf={(bucket) => bucket.gross_ev_cents}
          loOf={(bucket) => bucket.gross_ev_interval?.lo}
          hiOf={(bucket) => bucket.gross_ev_interval?.hi}
        />
      </div>

      <h2>Methodology</h2>
      <p>{text(page.interpretation)}</p>
      <p>
        The warehouse-relative primary contrast is the last 10% of covered games minus the preceding 90%, gross EV, cents per contract.
        Supported in this sample requires a positive estimate, an interval entirely above zero, and Holm-adjusted p at or below 0.05. Contradicted
        in this sample requires the corresponding negative result and the same Holm threshold. Otherwise the warehouse-relative legacy classification
        is inconclusive. Official-season final 10% and final 20% contrasts are UNAVAILABLE. WNBA primary season is 2025. WNBA 2026 and MLB 2026 are
        sensitivity seasons. Blocks of 3 and 7 examine dependence among distinct active dates.
      </p>
    </section>
  );
}

function BucketTable({ buckets, columns }: { buckets: Bucket[]; columns: [keyof Bucket, string][] }) {
  return (
    <div className="scroll-table">
      <table className="data-table">
        <thead>
          <tr>
            <th>Bucket</th>
            <th>Schedule</th>
            <th>G</th>
            <th>FIRST80 rows</th>
            <th>Ranks</th>
            <th>Dates</th>
            {columns.map(([, label]) => (
              <th key={label}>{label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {buckets.map((bucket) => (
            <tr key={bucket.bucket_id}>
              <td>
                {text(bucket.bucket_id)}
                {bucket.overlapping ? " overlap" : ""}
              </td>
              <td>{text(bucket.schedule_completeness || bucket.status)}</td>
              <td>{text(bucket.warehouse_games)}</td>
              <td>{text(bucket.first80_rows)}</td>
              <td>
                {text(bucket.rank_lo)}–{text(bucket.rank_hi)}
              </td>
              <td>
                {text(bucket.date_min)} to {text(bucket.date_max)}
              </td>
              {columns.map(([key]) => (
                <td key={String(key)}>{text(bucket[key])}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
