import { useCallback, useEffect, useState } from "react";
import { UniverseError, fetchExecutionValidation } from "./api";
import { text } from "./text";
import type { ExecutionValidationPage } from "./types";

function Row({ label, value }: { label: string; value: unknown }) {
  return (
    <div className="row">
      <dt>{label}</dt>
      <dd>{text(value)}</dd>
    </div>
  );
}

function CountTable({ title, rows }: { title: string; rows: Record<string, number> | undefined }) {
  const entries = Object.entries(rows ?? {});
  return (
    <>
      <h3>{title}</h3>
      <div className="scroll-table">
        <table className="data-table">
          <tbody>
            {entries.map(([key, value]) => (
              <tr key={key}>
                <td>{text(key)}</td>
                <td>{text(value)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

export default function ExecutionValidation() {
  const [page, setPage] = useState<ExecutionValidationPage | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setError("");
    try {
      setPage(await fetchExecutionValidation());
    } catch (err) {
      setPage(null);
      setError(err instanceof UniverseError ? err.message : "UNREAD");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const book40 = page?.books["80/40"];
  const book65 = page?.books["80/65"];

  return (
    <article className="wide">
      <h2>Execution validation</h2>
      {error ? <p className="banner is-bad">{error}</p> : null}
      {page ? (
        <>
          <dl>
            <Row label="specification" value={page.spec_id} />
            <Row label="configuration" value={page.configuration_id} />
            <Row label="separate 6% configuration" value={page.separate_configuration_id} />
            <Row label="live execution" value={page.live_execution} />
            <Row label="reference evidence" value={page.reference_evidence} />
            <Row label="simulated evidence" value={page.simulated_evidence} />
            <Row label="actual evidence" value={page.actual_evidence} />
            <Row label="actual fills" value={page.actual_fills} />
            <Row label="execution-aware portfolio P&L" value={page.execution_aware_portfolio_pnl} />
            <Row label="comparison" value={page.comparison_status} />
            <Row label="comparison reason" value={page.comparison_reason} />
            <Row label="historical fees" value={page.fees.historical_book} />
            <Row label="fee snapshot applies to this book" value={page.fees.snapshot.applies_to_historical_book} />
            <Row label="depth snapshots" value={page.coverage.order_book_depth_snapshots} />
            <Row label="depth deltas" value={page.coverage.order_book_deltas} />
            <Row label="sequence numbers" value={page.coverage.feed_sequence_numbers} />
            <Row label="game-time receive clock" value={page.coverage.game_time_local_receive_timestamps} />
            <Row label="public trade timestamps" value={page.coverage.exchange_trade_timestamps} />
            <Row label="actual order records" value={page.coverage.actual_order_records} />
            <Row label="trigger" value={page.observation_policy?.trigger} />
            <Row label="live-quote trigger" value={page.observation_policy?.live_quote_trigger} />
            <Row label="latency" value={page.observation_policy?.latency} />
            <Row label="hypothetical order intent" value={page.observation_policy?.hypothetical_order_intent} />
            <Row label="entry rest" value={page.observation_policy?.entry_rest} />
            <Row label="entry cancel" value={page.observation_policy?.entry_cancel} />
            <Row label="exit priority" value={page.observation_policy?.exit_priority} />
            <Row label="exit fallback" value={page.observation_policy?.exit_fallback} />
            <Row label="return calculation" value={page.observation_policy?.return_calculation} />
            <Row label="prospective collector" value={page.prospective_collector.status} />
            <Row label="prospective observations" value={page.prospective_collector.observations_collected} />
            <Row label="collector feed" value={page.prospective_collector.feed} />
            <Row label="simulated fills" value={page.prospective_collector.simulated_fills} />
            <Row label="specification frozen at" value={page.prospective_collector.spec_frozen_at} />
            <Row label="gap recharged" value={page.attribution.gap_recharged} />
            <Row label="attribution" value={page.attribution.note} />
            <Row label="80/40 unresolved" value={book40?.diagnostics.unresolved_events} />
            <Row label="80/65 unresolved" value={book65?.diagnostics.unresolved_events} />
            <Row label="80/40 depth rows" value={book40?.diagnostics.depth_available_entry_rows} />
            <Row label="80/65 depth rows" value={book65?.diagnostics.depth_available_entry_rows} />
            <Row label="80/40 benchmark profit cents" value={book40?.benchmark_pnl_cents} />
            <Row label="80/65 benchmark profit cents" value={book65?.benchmark_pnl_cents} />
          </dl>
          <CountTable title="80/40 candle bid minus nominal 80 cents" rows={book40?.diagnostics.entry_bid_minus_nominal_80} />
          <CountTable title="80/40 entry quote relation" rows={book40?.diagnostics.entry_quote_relations} />
          <CountTable title="80/40 exit quote relation" rows={book40?.diagnostics.exit_quote_relations} />
          <CountTable title="80/65 candle bid minus nominal 80 cents" rows={book65?.diagnostics.entry_bid_minus_nominal_80} />
          <CountTable title="80/65 entry quote relation" rows={book65?.diagnostics.entry_quote_relations} />
          <CountTable title="80/65 exit quote relation" rows={book65?.diagnostics.exit_quote_relations} />
          <h3>Missing execution parameters</h3>
          <ul>
            {page.specification.missing.map((line) => (
              <li key={line}>{text(line)}</li>
            ))}
          </ul>
        </>
      ) : null}
    </article>
  );
}
