import { useMemo, useState } from "react";
import type { DetailPayload } from "../../v2/components/DetailDrawer";
import type { PathWindowRow, SuperasiTrade } from "../types/superasi";
import PathWindowStrip from "./PathWindowStrip";

type Props = {
  trades: SuperasiTrade[];
  windows: PathWindowRow[];
  onOpenDetail: (detail: DetailPayload) => void;
};

const PAGE = 25;

export default function TradeTable({ trades, windows, onOpenDetail }: Props) {
  const [page, setPage] = useState(0);
  const pages = Math.max(1, Math.ceil(trades.length / PAGE));
  const slice = useMemo(
    () => trades.slice(page * PAGE, page * PAGE + PAGE),
    [page, trades],
  );
  return (
    <section className="ws-level" aria-label="Observation table">
      <p className="v2-kicker">Authoritative population</p>
      <h2>Observation table</h2>
      <p className="muted small">
        UI pagination only. Package N is uncapped. Path outcome ≠ terminal outcome.
      </p>
      <div className="sa-table-wrap">
        <table className="sa-table">
          <thead>
            <tr>
              <th>Ticker</th>
              <th>Slice</th>
              <th>Entry close</th>
              <th>Path loss</th>
              <th>Terminal YES</th>
              <th>Ask</th>
              <th>T40 close</th>
            </tr>
          </thead>
          <tbody>
            {slice.map((t) => {
              const pathLoss = t.loss_exit === true || t.T40 === true || t.path_true === false;
              return (
                <tr
                  key={t.observation_id || t.ticker}
                  onClick={() =>
                    onOpenDetail({
                      title: t.ticker,
                      subtitle: pathLoss ? "PATH LOSS · NOT A FILL" : "PATH HELD",
                      value:
                        t.terminal_yes == null
                          ? "terminal UNAVAILABLE"
                          : t.terminal_yes
                            ? "terminal YES"
                            : "terminal NO",
                      sections: [
                        {
                          heading: "Identity",
                          body: (
                            <p className="evidence">
                              {t.sport || "—"} · {t.league || "—"} · {t.slice || "—"} ·{" "}
                              {t.dataset_split || "—"} · {t.internal_game_id || "—"}
                              {t.alignment ? ` · ${t.alignment}` : ""}
                            </p>
                          ),
                        },
                        {
                          heading: "Window",
                          body: pathLoss ? (
                            <PathWindowStrip ticker={t.ticker} rows={windows} />
                          ) : (
                            <p>No path-loss window. Offset 0 is not a fill.</p>
                          ),
                        },
                      ],
                    })
                  }
                >
                  <td className="evidence">{t.ticker}</td>
                  <td>{t.slice || "—"}</td>
                  <td className="evidence">{t.entry_close ?? "—"}</td>
                  <td>{pathLoss ? "YES" : "NO"}</td>
                  <td>
                    {t.terminal_yes == null ? "UNAVAILABLE" : t.terminal_yes ? "YES" : "NO"}
                  </td>
                  <td>{t.entry_ask_status === "UNAVAILABLE" ? "UNAVAILABLE" : t.entry_ask ?? "—"}</td>
                  <td className="evidence">{t.window_derived?.t40_close ?? "—"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="sa-pager">
        <button type="button" className="v2-text-link" disabled={page <= 0} onClick={() => setPage((p) => p - 1)}>
          Previous
        </button>
        <span className="evidence">
          {page + 1} / {pages} · N = {trades.length}
        </span>
        <button
          type="button"
          className="v2-text-link"
          disabled={page + 1 >= pages}
          onClick={() => setPage((p) => p + 1)}
        >
          Next
        </button>
      </div>
    </section>
  );
}
