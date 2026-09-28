import { text } from "./text";
import type { DreDesk } from "./api";

type Props = {
  desk: DreDesk | null;
};

export default function Upstream({ desk }: Props) {
  const trade = desk?.trade_breakdown;
  const stratum = desk?.stratum;
  return (
    <section>
      <p className="kicker" style={{ marginTop: 8 }}>
        Bracket upstream
      </p>
      <div className="grid">
        <article>
          <h2>Trade Breakdown</h2>
          <p className="muted small">Choosin Texas · derived four · not Austin 604</p>
          <dl className="row">
            <div>
              <dt>Status</dt>
              <dd>{text(trade?.status)}</dd>
            </div>
            <div>
              <dt>N</dt>
              <dd>{text(trade?.n)}</dd>
            </div>
            <div>
              <dt>W</dt>
              <dd>{text(trade?.W)}</dd>
            </div>
            <div>
              <dt>L</dt>
              <dd>{text(trade?.L)}</dd>
            </div>
            <div>
              <dt>S</dt>
              <dd>{text(trade?.S_display)}</dd>
            </div>
          </dl>
          <p className="muted small">{text(trade?.note || trade?.detail)}</p>
        </article>
        <article>
          <h2>Position Stratification</h2>
          <p className="muted small">Austin · NBA 2Q∪3Q · never BUY/SKIP</p>
          <dl className="row">
            <div>
              <dt>Status</dt>
              <dd>{text(stratum?.status)}</dd>
            </div>
            <div>
              <dt>Book N</dt>
              <dd>{text(stratum?.book_n)}</dd>
            </div>
            <div>
              <dt>Live feed</dt>
              <dd>{text(stratum?.live_feed)}</dd>
            </div>
            <div>
              <dt>Dataset</dt>
              <dd>{text(stratum?.dataset_version)}</dd>
            </div>
          </dl>
          <p className="muted small">{text(stratum?.note || stratum?.detail)}</p>
        </article>
      </div>
    </section>
  );
}
