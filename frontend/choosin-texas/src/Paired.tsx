import { useCallback, useEffect, useState } from "react";
import { UniverseError, fetchPairedReplay } from "./api";
import ExecutionValidation from "./ExecutionValidation";
import { text } from "./text";
import type { CapitalBook, PairedReplay, PairedRun, PlannedAdmission, PlannedBook, PlannedRiskPolicy } from "./types";

function Row({ label, value }: { label: string; value: unknown }) {
  return (
    <div className="row">
      <dt>{label}</dt>
      <dd>{text(value)}</dd>
    </div>
  );
}

function ConfigPanel({ policy }: { policy: PlannedRiskPolicy }) {
  const config = policy.configuration;
  return (
    <article className="wide">
      <h2>Configuration</h2>
      <dl>
        <Row label="max simultaneous positions" value={config.max_open_positions} />
        <Row label="per-position premium cap percent" value={config.premium_percent_per_position} />
        <Row label="80/40 planned stop-risk cap percent" value={config.planned_stop_risk_percent_80_40} />
        <Row label="aggregate premium cap percent" value={config.premium_percent_portfolio} />
        <Row label="session" value={config.session_convention} />
        <Row label="reconstructed max 80/40" value={config.reconstructed_max_concurrent_80_40} />
        <Row label="reconstructed max 80/65" value={config.reconstructed_max_concurrent_80_65} />
        <Row label="prior result" value={policy.prior_result_status} />
        <Row label="selects a cap" value={policy.selects_a_cap} />
        <Row label="quantile convention" value={policy.quantile_convention} />
      </dl>
      <div className="scroll-table">
        <table className="data-table">
          <thead>
            <tr>
              <th>book</th>
              <th>cap</th>
              <th>role</th>
              <th>accepted</th>
              <th>P&L cents</th>
              <th>reconstructed max</th>
              <th>position-cap skips</th>
              <th>initial contracts</th>
            </tr>
          </thead>
          <tbody>
            {policy.diagnostics.map((row) => (
              <tr key={`${row.book}-${row.max_open_positions}`}>
                <td>{text(row.book)}</td>
                <td>{text(row.max_open_positions)}</td>
                <td>{text(row.label)}</td>
                <td>{text(row.accepted)}</td>
                <td>{text(row.through_close_pnl_cents)}</td>
                <td>{text(row.reconstructed_max_concurrent)}</td>
                <td>{text(row.position_cap_skips)}</td>
                <td>{text(row.initial_full_position_contracts)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </article>
  );
}

function OccupancyPanel({ book }: { book: PlannedBook }) {
  const turn = book.turnover;
  return (
    <article className="wide">
      <h2>{text(book.book)} occupancy</h2>
      <dl>
        <Row label="window" value={book.occupancy.window} />
        <Row label="reconstructed max" value={book.occupancy.max_concurrent} />
        <Row label="seconds at 0" value={book.occupancy.seconds_at_open_count["0"]} />
        <Row label="seconds at 1" value={book.occupancy.seconds_at_open_count["1"]} />
        <Row label="seconds at 2" value={book.occupancy.seconds_at_open_count["2"]} />
        <Row label="seconds at 3" value={book.occupancy.seconds_at_open_count["3"]} />
        <Row label="dates with candidates" value={turn.dates_with_candidates} />
        <Row label="dates with accepted entries" value={turn.dates_with_accepted_entries} />
        <Row label="accepted per date median" value={turn.accepted_per_entry_date.median} />
        <Row label="accepted per date 95th" value={turn.accepted_per_entry_date.p95} />
        <Row label="accepted per date maximum" value={turn.accepted_per_entry_date.maximum} />
        <Row label="holding seconds median" value={turn.holding_seconds.median} />
        <Row label="holding seconds 95th" value={turn.holding_seconds.p95} />
        <Row label="holding seconds maximum" value={turn.holding_seconds.maximum} />
        <Row label="seen with 0 open" value={turn.candidates_by_open_count_before["0"]} />
        <Row label="seen with 1 open" value={turn.candidates_by_open_count_before["1"]} />
        <Row label="seen with 2 open" value={turn.candidates_by_open_count_before["2"]} />
        <Row label="seen with 3 open" value={turn.candidates_by_open_count_before["3"]} />
        <Row label="position-cap skips" value={turn.position_cap_skips} />
        <Row label="other skips" value={turn.other_skips} />
        <Row label="busiest entry date" value={turn.busiest_entry_date?.date} />
        <Row label="busiest accepted" value={turn.busiest_entry_date?.accepted} />
        <Row label="blocked event" value={turn.blocked_example?.event_id} />
        <Row label="blocked at" value={turn.blocked_example?.entry_ts_display} />
        <Row label="blocking positions" value={turn.blocked_example?.blocking_event_ids_display} />
        <Row label="block versus freed window" value={turn.blocked_example?.relation_to_freed_window} />
        <Row label="freed-slot sequence" value={turn.freed_example?.sequence_display} />
        <Row label="largest dollar loss" value={book.loss_severity.largest_dollar_loss?.event_id} />
        <Row label="largest dollar loss dollars" value={book.loss_severity.largest_dollar_loss?.dollars_display} />
        <Row label="largest dollar loss of basis" value={book.loss_severity.largest_dollar_loss?.of_basis_pct_display} />
        <Row label="largest percent loss" value={book.loss_severity.largest_percent_loss?.event_id} />
        <Row label="largest percent loss dollars" value={book.loss_severity.largest_percent_loss?.dollars_display} />
        <Row label="largest percent loss of basis" value={book.loss_severity.largest_percent_loss?.of_basis_pct_display} />
        <Row label="same loss event" value={book.loss_severity.largest_dollar_and_percent_same_event} />
        <Row label="breach share of stops" value={book.loss_severity.breach_share_display} />
        <Row label="stopped loss median" value={book.loss_severity.stopped_loss_pct.median} />
        <Row label="stopped loss 95th" value={book.loss_severity.stopped_loss_pct.p95} />
        <Row label="stopped loss maximum" value={book.loss_severity.stopped_loss_pct.maximum} />
      </dl>
      <div className="scroll-table">
        <table className="data-table">
          <thead>
            <tr>
              <th>ts</th>
              <th>kind</th>
              <th>event</th>
              <th>before</th>
              <th>after</th>
            </tr>
          </thead>
          <tbody>
            {book.occupancy.change_points.map((point, index) => (
              <tr key={`${point.event_id}-${point.ts}-${index}`}>
                <td>{text(point.ts)}</td>
                <td>{text(point.kind)}</td>
                <td>{text(point.event_id)}</td>
                <td>{text(point.open_count_before)}</td>
                <td>{text(point.open_count)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </article>
  );
}

function AdmissionTable({ rows }: { rows: PlannedAdmission[] }) {
  const [filter, setFilter] = useState<"all" | "accepted" | "rejected">("all");
  const shown = rows.filter((row) => {
    if (filter === "accepted") return row.accepted;
    if (filter === "rejected") return !row.accepted;
    return true;
  });
  return (
    <article className="wide">
      <h2>Admissions</h2>
      <button type="button" onClick={() => setFilter("all")}>all</button>
      <button type="button" onClick={() => setFilter("accepted")}>accepted</button>
      <button type="button" onClick={() => setFilter("rejected")}>rejected</button>
      <div className="scroll-table">
        <table className="data-table">
          <thead>
            <tr>
              <th>event</th>
              <th>slice</th>
              <th>reason</th>
              <th>before</th>
              <th>after</th>
              <th>accepted contracts</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((row) => (
              <tr key={row.event_id}>
                <td>{text(row.event_id)}</td>
                <td>{text(row.sport)} {text(row.slice)}</td>
                <td>{text(row.reason)}</td>
                <td>{text(row.open_count_before)}</td>
                <td>{text(row.open_count_after)}</td>
                <td>{text(row.accepted_contracts)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </article>
  );
}

function PlannedCard({ book }: { book: PlannedBook }) {
  return (
    <article>
      <h2>{text(book.book)}</h2>
      <dl>
        <Row label="sizing" value={book.sizing_note} />
        <Row label="realized loss cap" value={book.realized_loss_cap} />
        <Row label="dates" value={`${text(book.date_start)} to ${text(book.date_end)}`} />
        <Row label="candidates" value={book.candidates} />
        <Row label="accepted" value={book.accepted} />
        <Row label="stopped" value={book.stopped} />
        <Row label="survivors" value={book.survivors} />
        <Row label="accepted win rate" value={book.accepted_win_rate_display} />
        <Row label="through-close P&L cents" value={book.through_close_pnl_cents} />
        <Row label="ending cash cents" value={book.ending_cash_cents} />
        <Row label="return percent" value={book.return_on_initial_pct_display} />
        <Row label="max concurrent" value={book.max_concurrent} />
        <Row label="max open premium dollars" value={book.max_open_entry_premium_dollars_display} />
        <Row label="max open premium of session basis" value={book.max_open_entry_premium_of_basis_pct_display} />
        <Row label="max planned stop risk of entry basis" value={book.max_planned_stop_risk_of_basis_pct_display} />
        <Row label="largest realized loss dollars" value={book.largest_single_realized_loss_dollars_display} />
        <Row label="largest realized loss of entry basis" value={book.largest_single_realized_loss_of_basis_pct_display} />
        <Row label="worst session" value={book.worst_session_date} />
        <Row label="worst session dollars" value={book.worst_session_dollars_display} />
        <Row label="worst session of frozen basis" value={book.worst_session_of_basis_pct_display} />
        <Row label="realized capital final cents" value={book.realized_capital.final_cents} />
        <Row label="realized-capital decline cents" value={book.realized_capital_max_drawdown.cents} />
        <Row label="of preceding peak" value={book.realized_capital_max_drawdown.of_peak_pct_display} />
        <Row label="stress proxy min cents" value={book.flat_stop_stress_proxy.min_cents} />
        <Row label="loss breaches" value={book.loss_breach_summary.count} />
        <Row label="breach threshold" value={book.loss_breach_summary.threshold} />
        <Row label="breach loss cents" value={book.loss_breach_summary.total_realized_loss_cents} />
      </dl>
      {book.loss_breaches.length ? (
        <ul>
          {book.loss_breaches.map((row) => (
            <li key={`${row.event_id}-${row.exit_ts}`}>
              {text(row.event_id)} {text(row.contracts)} {text(row.through_close_cents)} {text(row.realized_loss_cents)} {text(row.excess_cents)}
            </li>
          ))}
        </ul>
      ) : null}
    </article>
  );
}

function CapitalCard({ book }: { book: CapitalBook }) {
  return (
    <article>
      <h2>{text(book.book)}</h2>
      <dl>
        <Row label="dates" value={`${text(book.date_start)} to ${text(book.date_end)}`} />
        <Row label="candidates" value={book.candidates} />
        <Row label="accepted" value={book.accepted} />
        <Row label="stopped" value={book.stopped} />
        <Row label="survivors" value={book.survivors} />
        <Row label="accepted win rate" value={book.accepted_win_rate_display} />
        <Row label="full book survivors" value={book.full_book_survivor_display} />
        <Row label="contracts" value={book.contracts_taken} />
        <Row label="through-close P&L cents" value={book.through_close_pnl_cents} />
        <Row label="flat-stop P&L cents" value={book.flat_stop_pnl_cents} />
        <Row label="ending cash cents" value={book.ending_cash_cents} />
        <Row label="return on initial capital" value={book.return_on_initial_display} />
        <Row label="return percent" value={book.return_on_initial_pct_display} />
        <Row label="max concurrent" value={book.max_concurrent} />
        <Row label="max open premium cents" value={book.max_open_entry_premium_cents} />
        <Row label="max open premium dollars" value={book.max_open_entry_premium_dollars_display} />
        <Row label="max open premium of session basis" value={book.max_open_entry_premium_of_basis_pct_display} />
        <Row label="largest realized loss cents" value={book.largest_single_realized_loss_cents} />
        <Row label="largest realized loss dollars" value={book.largest_single_realized_loss_dollars_display} />
        <Row label="worst session" value={book.worst_session_date} />
        <Row label="worst session P&L cents" value={book.worst_session_realized_exit_pnl_cents} />
        <Row label="sessions with carried positions" value={book.sessions_with_carried_positions} />
        <Row label="planned flat loss cents" value={book.planned_flat_loss_per_full_position_cents} />
        <Row label="POSITION_CAP" value={book.reasons.POSITION_CAP} />
        <Row label="SKIP_CAPITAL_BUDGET" value={book.reasons.SKIP_CAPITAL_BUDGET} />
        <Row label="SKIP_CASH" value={book.reasons.SKIP_CASH} />
        <Row label="RESIZED_CAPITAL_BUDGET" value={book.reasons.RESIZED_CAPITAL_BUDGET} />
        <Row label="RESIZED_CASH" value={book.reasons.RESIZED_CASH} />
        <Row label={text(book.realized_capital.name)} value={book.realized_capital.final_cents} />
        <Row label={text(book.realized_capital_max_drawdown.name)} value={book.realized_capital_max_drawdown.dollars_display} />
        <Row label="of preceding peak" value={book.realized_capital_max_drawdown.of_peak_pct_display} />
        <Row label={text(book.flat_stop_stress_proxy.name)} value={book.flat_stop_stress_proxy.min_cents} />
      </dl>
      <p className="muted">{text(book.realized_capital.meaning)}</p>
      <p className="muted">{text(book.realized_capital_max_drawdown.meaning)}</p>
      <p className="muted">{text(book.flat_stop_stress_proxy.meaning)}</p>
    </article>
  );
}

function RunCard({ run }: { run: PairedRun }) {
  return (
    <article>
      <h2>
        {text(run.book)} · {text(run.configuration_id)} · {text(run.sizing)}
      </h2>
      <dl>
        <Row label="per-position risk cents" value={run.per_position_risk_cents} />
        <Row label="position cap" value={run.position_cap} />
        <Row label="flat loss cents" value={run.flat_loss_cents} />
        <Row label="entries taken" value={run.entries_taken} />
        <Row label="contracts taken" value={run.contracts_taken} />
        <Row label="max concurrent" value={run.max_concurrent} />
        <Row label="max deployed cents" value={run.max_deployed_cents} />
        <Row label="through-close P&L cents" value={run.through_close_pnl_cents} />
        <Row label="flat-stop P&L cents" value={run.flat_stop_pnl_cents} />
        <Row label="final cash cents" value={run.final_cash_cents} />
        <Row label="SKIP_CASH" value={run.skips.SKIP_CASH} />
        <Row label="SKIP_RISK_BUDGET" value={run.skips.SKIP_RISK_BUDGET} />
        <Row label="POSITION_CAP" value={run.skips.POSITION_CAP} />
        <Row label="SAME_EVENT" value={run.skips.SAME_EVENT} />
        <Row label="RESIZED_CASH" value={run.resized_cash_n} />
        <Row label={text(run.flat_stop_stress_proxy.name)} value={run.flat_stop_stress_proxy.min_cents} />
        <Row label="stress proxy final cents" value={run.flat_stop_stress_proxy.final_cents} />
        <Row label={text(run.realized_pnl_path.name)} value={run.realized_pnl_path.final_cents} />
      </dl>
      <p className="muted">{text(run.flat_stop_stress_proxy.meaning)}</p>
    </article>
  );
}

export default function Paired() {
  const [page, setPage] = useState<PairedReplay | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setError("");
    try {
      setPage(await fetchPairedReplay());
    } catch (err) {
      setPage(null);
      setError(err instanceof UniverseError ? err.message : "UNREAD");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const observed = page?.status === "OBSERVED";
  const book40 = page?.unit_book?.["80/40"];
  const book65 = page?.unit_book?.["80/65"];

  return (
    <>
      <div className="page-meta">
        <span className={`pill ${observed ? "is-ok" : "is-bad"}`}>
          {observed ? "OBSERVED" : error ? "LOCK_MISMATCH" : "UNREAD"}
        </span>
        <button type="button" onClick={() => void load()}>
          refresh
        </button>
      </div>
      {error ? <p className="banner is-bad">{error}</p> : null}
      {page ? (
        <section className="grid">
          <article className="wide">
            <h2>80/40 and 80/65 · same 936 events</h2>
            <dl>
              <Row label="primary research candidate" value={page.primary_research_candidate} />
              <Row label="live authorized" value={page.live_authorized} />
              <Row label="label" value={page.label} />
              <Row label="N" value={page.n} />
              <Row label="bankroll cents" value={page.bankroll_cents} />
              <Row label="portfolio risk cents" value={page.portfolio_risk_cents} />
              <Row label="entry cents" value={page.entry_cents} />
              <Row label="fees" value={page.fees} />
              <Row label="80/40 unit book cents" value={book40?.through_close_book_cents} />
              <Row label="80/40 stops" value={book40?.stops} />
              <Row label="80/65 unit book cents" value={book65?.through_close_book_cents} />
              <Row label="80/65 stops" value={book65?.stops} />
              <Row label="65 stops marked at settlement" value={page.clock.those_marked_at_settlement} />
            </dl>
          </article>
          <ExecutionValidation />
          {page.capital_policy ? (
            <article className="wide">
              <h2>6% deployed · 3 positions · 18% portfolio cap</h2>
              <dl>
                <Row label="policy" value={page.capital_policy.id} />
                <Row label="session" value={page.capital_policy.session_timezone} />
                <Row label="timestamps" value={page.capital_policy.timestamp_convention} />
                <Row label="accepted by both" value={page.capital_policy.accepted_both} />
                <Row label="accepted only 80/40" value={page.capital_policy.accepted_only_80_40} />
                <Row label="accepted only 80/65" value={page.capital_policy.accepted_only_80_65} />
                <Row label="candle path" value={page.capital_policy.notices.CANDLE_PATH_NOT_FILL} />
                <Row label="fees" value={page.capital_policy.notices.FEES_UNAVAILABLE} />
                <Row label="live" value={page.capital_policy.notices.LIVE_EXECUTION_DISABLED} />
                <Row label="forecast" value={page.capital_policy.notices.forecast} />
              </dl>
            </article>
          ) : null}
          {page.capital_policy ? <CapitalCard book={page.capital_policy.books["80/40"]} /> : null}
          {page.capital_policy ? <CapitalCard book={page.capital_policy.books["80/65"]} /> : null}
          {page.planned_risk_policy ? <ConfigPanel policy={page.planned_risk_policy} /> : null}
          {page.planned_risk_policy ? (
            <article className="wide">
              <h2>{text(page.planned_risk_policy.headings.book_40)}</h2>
              <h2>{text(page.planned_risk_policy.headings.book_65)}</h2>
              <h2>{text(page.planned_risk_policy.headings.both)}</h2>
              <dl>
                <Row label="policy" value={page.planned_risk_policy.id} />
                <Row label="sizing" value={page.planned_risk_policy.sizing_note} />
                <Row label="realized loss cap" value={page.planned_risk_policy.realized_loss_cap} />
                <Row label="accepted by both" value={page.planned_risk_policy.accepted_both} />
                <Row label="accepted only 80/40" value={page.planned_risk_policy.accepted_only_80_40} />
                <Row label="accepted only 80/65" value={page.planned_risk_policy.accepted_only_80_65} />
                <Row label="candle path" value={page.planned_risk_policy.notices.CANDLE_PATH_NOT_FILL} />
                <Row label="fees" value={page.planned_risk_policy.notices.FEES_UNAVAILABLE} />
                <Row label="live" value={page.planned_risk_policy.notices.LIVE_EXECUTION_DISABLED} />
              </dl>
            </article>
          ) : null}
          {page.planned_risk_policy ? <PlannedCard book={page.planned_risk_policy.books["80/40"]} /> : null}
          {page.planned_risk_policy ? <PlannedCard book={page.planned_risk_policy.books["80/65"]} /> : null}
          {page.planned_risk_policy ? <OccupancyPanel book={page.planned_risk_policy.books["80/40"]} /> : null}
          {page.planned_risk_policy ? <OccupancyPanel book={page.planned_risk_policy.books["80/65"]} /> : null}
          {page.planned_risk_policy ? <AdmissionTable rows={page.planned_risk_policy.books["80/40"].decisions} /> : null}
          {page.planned_risk_policy ? <AdmissionTable rows={page.planned_risk_policy.books["80/65"].decisions} /> : null}
          {page.runs.map((run) => (
            <RunCard key={`${run.book}-${run.configuration_id}-${run.sizing}`} run={run} />
          ))}
          <article className="wide">
            <h2>Notes</h2>
            <ul>
              {page.disclaimers.map((line) => (
                <li key={line}>{text(line)}</li>
              ))}
            </ul>
          </article>
        </section>
      ) : null}
    </>
  );
}
