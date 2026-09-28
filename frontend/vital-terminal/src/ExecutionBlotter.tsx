import { useState } from "react";
import { bpText, metricText, moneyText, priceText, type VitalExecution, type VitalTrade } from "./api/vitalApi";

type Props = {
  execution: VitalExecution | null;
};

export default function ExecutionBlotter({ execution }: Props) {
  const [selected, setSelected] = useState<VitalTrade | null>(null);
  return (
    <section className="vital-card" aria-label="Execution blotter">
      <div className="vital-row-head">
        <p className="ws-kicker">Blotter</p>
        <p className="muted small">
          {execution?.status || "OBSERVATION_UNAVAILABLE"} · trades{" "}
          {execution?.trades_status || "OBSERVATION_UNAVAILABLE"} · fills{" "}
          {execution?.fills_status || "OBSERVATION_UNAVAILABLE"}
        </p>
      </div>
      <p className="muted small">
        One confirmed market is one row. Unread is not empty. Candle path is not a fill.
      </p>
      <dl className="vital-mini-dl">
        <div>
          <dt>Trades</dt>
          <dd>{metricText(execution?.summary?.total_trades)}</dd>
        </div>
        <div>
          <dt>Open</dt>
          <dd>{metricText(execution?.summary?.open)}</dd>
        </div>
        <div>
          <dt>Closed</dt>
          <dd>{metricText(execution?.summary?.closed)}</dd>
        </div>
        <div>
          <dt>Fills</dt>
          <dd>{metricText(execution?.summary?.total_fills)}</dd>
        </div>
      </dl>
      {execution?.trades_status === "CONFIRMED" && execution.trades ? (
        <div className="stax-table-wrap">
          <table className="stax-table vital-blotter">
            <thead>
              <tr>
                <th>Market</th>
                <th>Game</th>
                <th>Entry</th>
                <th>Exit</th>
                <th>Risked</th>
                <th>Paid</th>
                <th>Qty</th>
                <th>Gross</th>
                <th>State</th>
              </tr>
            </thead>
            <tbody>
              {execution.trades.length === 0 ? (
                <tr>
                  <td colSpan={9} className="muted small">
                    CONFIRMED: no trades
                  </td>
                </tr>
              ) : (
                execution.trades.map((trade) => (
                  <tr key={trade.trade_id} className="stax-click" onClick={() => setSelected(trade)}>
                    <td className="vital-clip">{metricText(trade.market)}</td>
                    <td>{metricText(trade.game)}</td>
                    <td>{priceText(trade.entry_price_cents ?? trade.entry_price)}</td>
                    <td>
                      {trade.status === "OPEN" && (trade.exit_price_cents ?? trade.exit_price)?.status !== "CONFIRMED"
                        ? "—"
                        : priceText(trade.exit_price_cents ?? trade.exit_price)}
                    </td>
                    <td>{moneyText(trade.amount_risked_cents ?? trade.amount_traded_cents ?? trade.entry_amount)}</td>
                    <td>
                      {trade.status === "OPEN" && (trade.amount_exited_cents ?? trade.exit_amount)?.status !== "CONFIRMED"
                        ? "—"
                        : moneyText(trade.amount_exited_cents ?? trade.exit_amount)}
                    </td>
                    <td>{metricText(trade.entry_contracts)}</td>
                    <td>
                      {trade.status === "OPEN" && trade.gross_realized_cents?.status !== "CONFIRMED"
                        ? "—"
                        : moneyText(trade.gross_realized_cents, true)}
                    </td>
                    <td>{trade.status || "UNREAD"}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="muted small">TRADES {execution?.trades_status || "OBSERVATION_UNAVAILABLE"}</p>
      )}
      {selected ? (
        <div className="vital-trade-detail">
          <p className="ws-kicker">Trade {selected.trade_id}</p>
          <p className="muted small">
            {metricText(selected.market)} · {metricText(selected.game)} · alloc{" "}
            {bpText(selected.pct_bankroll_allocated_bp)} · net {moneyText(selected.net_realized_cents, true)}
          </p>
          <p className="muted small">
            SOURCE {selected.source || "UNAVAILABLE"} · OBS {selected.observation_status || "UNAVAILABLE"}
          </p>
          <button type="button" className="btn-secondary" onClick={() => setSelected(null)}>
            Close
          </button>
        </div>
      ) : null}
      {execution?.fills_status === "CONFIRMED" && execution.fills ? (
        <div className="stax-table-wrap">
          <table className="stax-table vital-blotter">
            <thead>
              <tr>
                <th>Time</th>
                <th>Market</th>
                <th>Qty</th>
                <th>Price</th>
                <th>Amount</th>
                <th>Kind</th>
                <th>Source</th>
              </tr>
            </thead>
            <tbody>
              {execution.fills.length === 0 ? (
                <tr>
                  <td colSpan={7} className="muted small">
                    CONFIRMED: no fills
                  </td>
                </tr>
              ) : (
                execution.fills.map((fill) => (
                  <tr key={fill.fill_id}>
                    <td>{metricText(fill.timestamp)}</td>
                    <td>{metricText(fill.market)}</td>
                    <td>{metricText(fill.contracts)}</td>
                    <td>{priceText(fill.price_cents)}</td>
                    <td>{moneyText(fill.amount_cents)}</td>
                    <td>{metricText(fill.fee_kind)}</td>
                    <td>{fill.source || "UNAVAILABLE"}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="muted small">FILLS {execution?.fills_status || "OBSERVATION_UNAVAILABLE"}</p>
      )}
    </section>
  );
}
