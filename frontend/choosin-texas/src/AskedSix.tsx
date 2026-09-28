import { useCallback, useEffect, useState } from "react";
import { UniverseError, fetchAskedSix } from "./api";
import { text } from "./text";
import type { AskedSixPage, AskedSixTauBook, TradePath } from "./types";

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

function TauPaths({ book }: { book: AskedSixTauBook }) {
  if (book.status === "DATA_REQUIRED") {
    return <p className="banner is-bad">{text(book.message)}</p>;
  }
  const paths = book.paths || [];
  const top = (book.ledger_rank || [])[0];
  return (
    <div className="tau-block">
      <h3>
        {book.rule} · N={book.n} · {book.entry_cents}/{book.entry_cap_cents} cap · gain {book.gain_cents}¢
      </h3>
      <p className="muted">{text(book.note)}</p>
      <div className="path-list">
        {paths.map((path) => (
          <div key={path.key} className={path.key === top ? "path-line is-top" : "path-line"}>
            <span>{path.key}</span>
            <span>
              {text(path.S_display)} · {text(path.S_pct_display)}
            </span>
            <span>
              {text(path.ev_per_trade_display)} · n={path.n}
            </span>
          </div>
        ))}
      </div>
      <p className="muted">ledger rank {text((book.ledger_rank || []).join(" > "))}</p>
    </div>
  );
}

export default function AskedSix() {
  const [page, setPage] = useState<AskedSixPage | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const next = await fetchAskedSix();
      if (next.status !== "OBSERVED") {
        setPage(null);
        setError(next.message || next.status || "LOCK_MISMATCH");
        return;
      }
      setPage(next);
      setError(null);
    } catch (err) {
      setPage(null);
      setError(err instanceof UniverseError ? err.message : err instanceof Error ? err.message : String(err));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const observed = page !== null && page.status === "OBSERVED";
  const rules = ["FIRST80", "FIRST75", "FIRST77", "FIRST81", "FIRST83"] as const;

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
      {observed ? (
        <>
          <p className="banner">
            Asked-six ≠ derived four. 1182 ≠ 936. 1126 ≠ 913. 1158 ≠ 933. FIRST81 four 940 / six 1193.
            FIRST83 four 973 / six 1243. LIVE EXECUTION = FALSE. Candle path ≠ fill.
          </p>
          <section className="grid">
            <article className="wide">
              <h2>Asked-six pool · NBA 2Q+3Q ∪ NCAAB 1H2+2H1 ∪ WNBA 2Q+3Q</h2>
              <p className="muted">{text(page.pool?.ncaab_window_note)}</p>
              <dl>
                {rules.map((rule) => (
                  <Row
                    key={rule}
                    label={rule}
                    value={
                      page.books?.[rule]?.identity ||
                      page.books?.[rule]?.message ||
                      page.books?.[rule]?.n
                    }
                  />
                ))}
              </dl>
              {rules.map((rule) => {
                const book = page.pool?.books?.[rule];
                return book ? <TauPaths key={rule} book={book} /> : null;
              })}
            </article>
          </section>
          <section className="grid six">
            {(page.partitions || []).map((row) => (
              <article key={row.partition_id}>
                <h2>
                  {row.sport_label} · {row.slice_label}
                </h2>
                {row.ncaab_window_note ? <p className="muted">{row.ncaab_window_note}</p> : null}
                {rules.map((rule) => {
                  const book = row.books?.[rule];
                  return book ? <TauPaths key={rule} book={book} /> : null;
                })}
              </article>
            ))}
          </section>
          <section className="grid">
            <article className="wide">
              <h2>OOS · CSV dataset_split IN_SAMPLE vs OOS</h2>
              <p className="muted">{text(page.oos?.in_sample_note)}</p>
              <p className="muted">{text(page.oos?.label)}</p>
              {rules.map((rule) => {
                const oos = page.oos?.books?.[rule];
                if (!oos) return null;
                if (oos.status === "DATA_REQUIRED") {
                  return (
                    <div key={rule} className="tau-block">
                      <h3>{rule}</h3>
                      <p className="banner is-bad">{text(oos.message)}</p>
                    </div>
                  );
                }
                const split = oos.split;
                const train = oos.train;
                const test = oos.test;
                return (
                  <div key={rule} className="tau-block">
                    <h3>
                      {rule} OOS · train {text(split?.train_n)} · test {text(split?.test_n)} · val {text(split?.validation_n)}
                    </h3>
                    <p className="muted">{text(split?.rule)}</p>
                    <p className="muted">
                      train {text(split?.train_window)} · test {text(split?.test_window)} · not a fill
                    </p>
                    {train?.pool ? (
                      <>
                        <h3>Train asked-six N={train.pool.n}</h3>
                        <div className="path-list">
                          {(train.pool.paths || []).map((path: TradePath) => (
                            <PathRow key={`tr-${path.key}`} path={path} />
                          ))}
                        </div>
                      </>
                    ) : null}
                    {test?.pool ? (
                      <>
                        <h3>Test asked-six N={test.pool.n}</h3>
                        <div className="path-list">
                          {(test.pool.paths || []).map((path: TradePath) => (
                            <PathRow key={`te-${path.key}`} path={path} />
                          ))}
                        </div>
                      </>
                    ) : null}
                    <dl>
                      {Object.values(test?.slices || {}).map((slice) => (
                        <Row
                          key={`${rule}-${slice.partition_id}`}
                          label={`${slice.sport_label} ${slice.slice_label} test`}
                          value={
                            slice.status === "DATA_REQUIRED"
                              ? slice.message
                              : `N=${slice.n} OBSERVED`
                          }
                        />
                      ))}
                    </dl>
                    <p className="muted">{text(oos.note)}</p>
                  </div>
                );
              })}
            </article>
            <article>
              <h2>Not this desk</h2>
              <ul className="muted">
                {(page.disclaimers || []).map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
            </article>
          </section>
        </>
      ) : null}
    </>
  );
}
