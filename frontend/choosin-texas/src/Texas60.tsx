import { useCallback, useEffect, useState } from "react";
import { UniverseError, fetchUniverse60 } from "./api";
import { text, width } from "./text";
import type { ClockSlice, GapSlice, Partition, TradePath, Universe } from "./types";

function Row({ label, value }: { label: string; value: unknown }) {
  return (
    <div className="row">
      <dt>{label}</dt>
      <dd>{text(value)}</dd>
    </div>
  );
}

function PathRow({ path }: { path: TradePath }) {
  return (
    <div className="path-line">
      <span>{path.key}</span>
      <span>
        {text(path.S_display)} · {text(path.S_pct_display)}
      </span>
      <span>{text(path.ev_per_trade_display)}</span>
    </div>
  );
}

function PartitionCard({ row }: { row: Partition }) {
  const trade = row.trade_80_60;
  const cells = trade?.cells;
  return (
    <article>
      <h2>
        {row.sport_label} · {row.slice_label}
      </h2>
      <dl>
        <Row label="universe N" value={row.n} />
        <Row label="terminal W / L" value={`${row.W} / ${row.L}`} />
        <Row label="terminal W/N" value={`${text(row.terminal.p_display)} · ${text(row.terminal.p_pct_display)}`} />
        <Row label="80/60 S" value={`${text(trade?.S_display)} · ${text(trade?.S_pct_display)}`} />
        <Row label="80/60 EV" value={text(trade?.ev_per_trade_display)} />
        <Row label="book cents" value={trade?.book_cents} />
        <Row label="loss cents" value={trade?.loss_cents} />
        <Row label="band rank" value={(row.band_rank || []).join(" > ")} />
      </dl>
      <div className="path-list">
        {(row.band || []).map((path) => (
          <PathRow key={path.key} path={path} />
        ))}
      </div>
      <div className="cells">
        <div className="cell">
          <span>W ∩ ¬T60</span>
          {text(cells?.W_and_not_T60)}
        </div>
        <div className="cell">
          <span>W ∩ T60</span>
          {text(cells?.W_and_T60)}
        </div>
        <div className="cell">
          <span>L ∩ ¬T60</span>
          {text(cells?.L_and_not_T60)}
        </div>
        <div className="cell">
          <span>L ∩ T60</span>
          {text(cells?.L_and_T60)}
        </div>
      </div>
    </article>
  );
}

function ClockPanel({ clock }: { clock: ClockSlice }) {
  return (
    <article>
      <h2>
        {clock.slice_label} entries · T60 clock · {clock.n_t60} stops
      </h2>
      <div className="chart">
        {clock.bins
          .filter((bin) => bin.n > 0)
          .map((bin) => (
            <div key={bin.label} className="chart-row">
              <span>{bin.label}</span>
              <div className="track">
                <div className="fill fill-clock" style={{ width: width(bin.bar_pct) }} />
              </div>
              <span>
                {text(bin.n_display)} · {text(bin.pct_display)}
              </span>
            </div>
          ))}
      </div>
      <dl>
        {(clock.mean_remaining || []).map((row) => (
          <Row key={row.period} label={`${row.period} mean remaining`} value={`${row.clock_display} · n=${row.n}`} />
        ))}
      </dl>
    </article>
  );
}

function GapBlock({ title, row, note }: { title: string; row: GapSlice; note?: string }) {
  return (
    <article>
      <h2>{title}</h2>
      <dl>
        <Row label="touched" value={row.n} />
        <Row label="separate print" value={`${text(row.separate_print?.display)} · ${text(row.separate_print?.pct_display)}`} />
        {row.same_bar_at_or_below_60 ? (
          <Row
            label="same bar already ≤60"
            value={`${text(row.same_bar_at_or_below_60.display)} · ${text(row.same_bar_at_or_below_60.pct_display)}`}
          />
        ) : null}
        {row.separate_then_60 ? (
          <Row
            label="separate, then 60"
            value={`${text(row.separate_then_60.display)} · ${text(row.separate_then_60.pct_display)}`}
          />
        ) : null}
        {row.separate_held_above_60 ? (
          <Row
            label="separate, held above 60"
            value={`${text(row.separate_held_above_60.display)} · ${text(row.separate_held_above_60.pct_display)}`}
          />
        ) : null}
        {row.same_bar_at_or_below_55 ? (
          <Row
            label="same bar already ≤55"
            value={`${text(row.same_bar_at_or_below_55.display)} · ${text(row.same_bar_at_or_below_55.pct_display)}`}
          />
        ) : null}
        {row.continued_to_55 ? (
          <Row
            label="continued to 55"
            value={`${text(row.continued_to_55.display)} · ${text(row.continued_to_55.pct_display)}`}
          />
        ) : null}
        {row.never_printed_55 ? (
          <Row
            label="never printed 55"
            value={`${text(row.never_printed_55.display)} · ${text(row.never_printed_55.pct_display)}`}
          />
        ) : null}
      </dl>
      {note ? <p className="muted">{note}</p> : null}
    </article>
  );
}

export default function Texas60() {
  const [universe, setUniverse] = useState<Universe | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const next = await fetchUniverse60();
      if (next.status !== "OBSERVED") {
        setUniverse(null);
        setError(next.message || next.status || "LOCK_MISMATCH");
        return;
      }
      setUniverse(next);
      setError(null);
    } catch (err) {
      setUniverse(null);
      if (err instanceof UniverseError) {
        setError(err.message);
        return;
      }
      setError(err instanceof Error ? err.message : String(err));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const observed = universe !== null && universe.status === "OBSERVED";
  const pool = observed ? universe.pool : null;
  const trade = pool?.trade_80_60;

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

      {pool && trade ? (
        <section className="grid">
          <article className="wide">
            <h2>80/60 · same derived four as 80/40</h2>
            <div className="stat-row">
              <div className="stat">
                <dt>Games N</dt>
                <dd>
                  {pool.n}
                  <span className="sub">{text(universe?.unit)}</span>
                </dd>
              </div>
              <div className="stat">
                <dt>Terminal W/N</dt>
                <dd>
                  {text(pool.terminal.p_display)}
                  <span className="sub">{text(pool.terminal.p_pct_display)}</span>
                </dd>
              </div>
              <div className="stat">
                <dt>80/60 S</dt>
                <dd>
                  {text(trade.S_display)}
                  <span className="sub">{text(trade.S_pct_display)}</span>
                </dd>
              </div>
              <div className="stat">
                <dt>80/60 EV</dt>
                <dd>
                  {text(trade.ev_per_trade_display)}
                  <span className="sub">
                    book {text(trade.book_cents)}¢ · loss {text(trade.loss_cents)}¢
                  </span>
                </dd>
              </div>
            </div>
            <p className="muted">
              {text(universe?.variables?.note)} {text(universe?.anchor_80_40?.note)} 80/40 S on this
              N is {text(universe?.anchor_80_40?.S_display)}.
            </p>
            <div className="stat-row second">
              {(pool.band || []).map((path) => (
                <div key={path.key} className={`stat ev-chip${path.key === "80/60" ? " is-top" : ""}`}>
                  <dt>{path.key} EV</dt>
                  <dd>
                    {text(path.ev_per_trade_display)}
                    <span className="sub">
                      {text(path.S_display)} · book {text(path.book_cents)}¢ · loss {text(path.loss_cents)}¢ · n=
                      {path.n}
                    </span>
                  </dd>
                </div>
              ))}
            </div>
            <p className="muted">Band rank {text((pool.band_rank || []).join(" > "))}. Full 936 book.</p>
          </article>
          {universe?.gap?.t65?.pool ? (
            <GapBlock
              title="65 · above the 60 stop"
              row={universe.gap.t65.pool}
              note={universe.gap.t65.note}
            />
          ) : null}
          {universe?.gap?.t60?.pool ? (
            <GapBlock
              title="60 · and the 55 continuation"
              row={universe.gap.t60.pool}
              note={universe.gap.t60.note}
            />
          ) : null}
        </section>
      ) : null}

      {observed ? (
        <section className="grid four">
          {universe.partitions.map((row) => (
            <PartitionCard key={row.partition_id} row={row} />
          ))}
        </section>
      ) : null}

      {observed && pool?.trade_80_60 ? (
        <section className="grid">
          <article className="wide">
            <h2>Charts · API bars only</h2>
            <div className="chart">
              {universe.partitions.map((row) => (
                <div key={`${row.partition_id}-s`} className="chart-row">
                  <span>{row.slice_label} 80/60 S</span>
                  <div className="track">
                    <div className="fill fill-s" style={{ width: width(row.trade_80_60?.S_bar_pct) }} />
                  </div>
                  <span>{text(row.trade_80_60?.S_pct_display)}</span>
                </div>
              ))}
              <div className="chart-row">
                <span>80/60 EV</span>
                <div className="track">
                  <div className="fill fill-ev" style={{ width: width(pool.trade_80_60.ev_bar_pct) }} />
                </div>
                <span>{text(pool.trade_80_60.ev_per_trade_display)}</span>
              </div>
            </div>
          </article>

          <article>
            <h2>Variables · locked</h2>
            <dl>
              <Row label="rule" value={universe.variables?.rule} />
              <Row label="entry" value={universe.variables?.entry_cents} />
              <Row label="stop" value={universe.variables?.stop_cents} />
              <Row label="gain" value={universe.variables?.gain_cents} />
              <Row label="loss" value={universe.variables?.loss_cents} />
              <Row label="N" value={universe.variables?.n} />
              <Row label="locked" value={universe.variables?.locked} />
              <Row label="recompute" value={universe.variables?.recompute} />
            </dl>
            <p className="muted">{text(universe.variables?.note)}</p>
          </article>

          {(universe.clocks || []).map((clock) => (
            <ClockPanel key={clock.slice} clock={clock} />
          ))}
          <article className="wide">
            <h2>Alignment</h2>
            <p className="muted">{text(universe.alignment?.model)}</p>
            <p className="muted">{text(universe.alignment?.note)}</p>
          </article>
          <article>
            <h2>Not this desk</h2>
            <ul className="muted">
              {(universe.disclaimers || []).map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          </article>
        </section>
      ) : null}
    </>
  );
}
