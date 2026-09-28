import { useCallback, useEffect, useState } from "react";
import { UniverseError, fetchBook } from "./api";
import { text } from "./text";
import type { BookEvRow, BookTape, ResearchBook } from "./types";

function Row({ label, value }: { label: string; value: unknown }) {
  return (
    <div className="row">
      <dt>{label}</dt>
      <dd>{text(value)}</dd>
    </div>
  );
}

function EvTable({ rows }: { rows: BookEvRow[] }) {
  return (
    <table className="data-table">
      <thead>
        <tr>
          <th>cut</th>
          <th>N</th>
          <th>S</th>
          <th>W∩T40</th>
          <th>L∩T40</th>
          <th>EV</th>
          <th>book</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.key || row.label}>
            <td>{text(row.label || row.key)}</td>
            <td>{row.n}</td>
            <td>{text(row.s_display)}</td>
            <td>{text(row.w_t40)}</td>
            <td>{text(row.l_t40)}</td>
            <td>{text(row.ev_per_trade_display)}</td>
            <td>{text(row.book_cents)}¢</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function TapeCard({ tape }: { tape: BookTape }) {
  return (
    <article>
      <h2>{text(tape.label)}</h2>
      <dl>
        <Row label="role" value={tape.role} />
        <Row label="N" value={tape.n} />
        <Row label="80/40 S" value={tape.s_display} />
        <Row label="W ∩ T40" value={tape.w_t40} />
        <Row label="L ∩ T40" value={tape.l_t40} />
        <Row label="EV" value={tape.ev_per_trade_display} />
        <Row label="book" value={`${text(tape.book_cents)}¢`} />
        <Row label="window" value={(tape.window || []).join(" → ")} />
      </dl>
    </article>
  );
}

export default function Book() {
  const [book, setBook] = useState<ResearchBook | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const payload = await fetchBook();
      if (payload.status !== "OBSERVED") {
        setBook(null);
        setError(payload.message || payload.status || "LOCK_MISMATCH");
        return;
      }
      setBook(payload);
      setError(null);
    } catch (err) {
      setBook(null);
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

  const observed = book !== null && book.status === "OBSERVED";
  const registered = book?.registered;
  const baseline = book?.baseline;
  const tapes = book?.tapes || [];
  const q2 = tapes.find((tape) => tape.tape_id === "nba_2q_regular");
  const ncaab = tapes.find((tape) => tape.tape_id === "ncaab_h12_h21");

  return (
    <>
      <div className="page-meta">
        <span className={`pill ${observed ? "is-ok" : "is-bad"}`}>
          {observed ? text(registered?.status) : error ? "LOCK_MISMATCH" : "UNREAD"}
        </span>
        <span className="pill is-idle">not live</span>
        <button type="button" onClick={() => void load()}>
          refresh
        </button>
      </div>

      {error ? <p className="banner is-bad">{error}</p> : null}

      {observed && registered ? (
        <section className="grid">
          <article className="wide">
            <p>Official upcoming-season strategy: FIRST78→67</p>
            <p>Live execution: disabled</p>
            <p>Validation: NOT_YET_IDENTIFIABLE</p>
            <h2>Historical registered research baseline</h2>
            <p className="muted">HISTORICAL_REGISTERED_RESEARCH_BASELINE. Registration metadata below is unchanged.</p>
            <div className="stat-row">
              <div className="stat">
                <dt>Book</dt>
                <dd>
                  {text(registered.sport)} {text(registered.slice)}
                  <span className="sub">{text(registered.title)}</span>
                </dd>
              </div>
              <div className="stat">
                <dt>Rule</dt>
                <dd>
                  {text(registered.rule)} {text(registered.entry_cents)}/{text(registered.stop_cents)}
                  <span className="sub">{text(registered.season_phase)} · {text(registered.contracts)} contract</span>
                </dd>
              </div>
              <div className="stat">
                <dt>2025-26 baseline</dt>
                <dd>
                  {text(baseline?.s_display)}
                  <span className="sub">
                    {text(baseline?.ev_per_trade_display)} · book {text(baseline?.book_cents)}¢
                  </span>
                </dd>
              </div>
              <div className="stat">
                <dt>Live</dt>
                <dd className="is-bad">
                  {text(book.live_execution)}
                  <span className="sub">{text(book.book_id)}</span>
                </dd>
              </div>
            </div>
            <ul className="muted">
              {(registered.clauses || []).map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
            <p className="muted">{text(book.identity)}</p>
          </article>
        </section>
      ) : null}

      {observed ? (
        <section className="grid four">
          {tapes.map((tape) => (
            <TapeCard key={tape.tape_id} tape={tape} />
          ))}
        </section>
      ) : null}

      {observed ? (
        <section className="grid">
          <article className="wide">
            <h2>Hold / reverse (NCAAB analog)</h2>
            <table className="data-table">
              <thead>
                <tr>
                  <th>NBA claim</th>
                  <th>NCAAB / baseline</th>
                  <th>verdict</th>
                </tr>
              </thead>
              <tbody>
                {(book.hold_reverse || []).map((row) => (
                  <tr key={row.claim}>
                    <td>{text(row.claim)}</td>
                    <td>{text(row.ncaab)}</td>
                    <td className={row.verdict === "reverses" ? "is-bad" : "is-ok"}>{text(row.verdict)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </article>
        </section>
      ) : null}

      {q2 ? (
        <section className="grid">
          <article>
            <h2>Q2 regular season · lead at 80</h2>
            <EvTable rows={q2.lead || []} />
          </article>
          <article>
            <h2>Q2 regular season · open</h2>
            <EvTable rows={q2.open || []} />
          </article>
        </section>
      ) : null}

      {ncaab ? (
        <section className="grid">
          <article>
            <h2>NCAAB analog · lead at 80</h2>
            <EvTable rows={ncaab.lead || []} />
          </article>
          <article>
            <h2>NCAAB analog · open</h2>
            <EvTable rows={ncaab.open || []} />
          </article>
        </section>
      ) : null}

      {observed ? (
        <section className="grid">
          <article>
            <h2>Watch · log only, do not skip</h2>
            <dl>
              {(book.watch_do_not_filter || []).map((row) => (
                <Row key={row.cell} label={row.cell} value={row.why} />
              ))}
            </dl>
          </article>
          <article>
            <h2>Forbidden</h2>
            <ul className="muted">
              {(book.forbidden || []).map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          </article>
          <article>
            <h2>2026-27 measurement</h2>
            <ul className="muted">
              {(book.measurement || []).map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          </article>
          <article>
            <h2>Later conversion</h2>
            <ul className="muted">
              {(book.conversion || []).map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
            <dl>
              <Row label="write-up" value={book.writeup_path} />
              <Row label="library" value={book.library_path} />
              <Row label="note" value={book.note_path} />
            </dl>
          </article>
        </section>
      ) : null}
    </>
  );
}
