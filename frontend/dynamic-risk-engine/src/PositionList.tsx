import { useEffect, useMemo, useState } from "react";
import { DreError, fetchPositionList, type DreBook, type DreListRow } from "./api";
import { cents, text } from "./text";

type Props = {
  slice: string;
  query: string;
  book?: DreBook;
  onSlice: (value: string) => void;
  onQuery: (value: string) => void;
};

export default function PositionList({ slice, query, book = "80", onSlice, onQuery }: Props) {
  const [rows, setRows] = useState<DreListRow[]>([]);
  const [bookN, setBookN] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState(query);

  useEffect(() => {
    setDraft(query);
  }, [query]);

  useEffect(() => {
    fetchPositionList({ q: query || undefined, slice: slice || undefined }, book)
      .then((body) => {
        setRows(body.positions || []);
        setBookN(body.book_n ?? body.n ?? null);
        setError(null);
      })
      .catch((err: unknown) => {
        setError(err instanceof DreError ? err.message : String(err));
      });
  }, [query, slice, book]);

  const slices = useMemo(() => {
    const found = new Set(rows.map((row) => String(row.slice || "")).filter(Boolean));
    return ["", ...Array.from(found).sort()];
  }, [rows]);

  return (
    <section className="list-desk">
      <div className="list-head">
        <div>
          <p className="kicker">Open book · historical</p>
          <h2>Positions</h2>
        </div>
        <p className="muted small">
          {book === "78" ? "Austin 78/67." : "Austin 604."} Mode HISTORICAL. Live feed UNAVAILABLE. Last Observed is an artifact snapshot, not a live quote.
          {bookN != null ? ` Book N=${bookN}.` : ""}
        </p>
      </div>
      <form
        className="list-filters"
        onSubmit={(event) => {
          event.preventDefault();
          onQuery(draft.trim());
        }}
      >
        <label>
          Slice
          <select value={slice} onChange={(event) => onSlice(event.target.value)}>
            <option value="">All</option>
            {slices.filter(Boolean).map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </label>
        <label className="grow">
          Game / ticker
          <input value={draft} onChange={(event) => setDraft(event.target.value)} placeholder="Search" />
        </label>
        <button type="submit">Filter</button>
      </form>
      {error ? <div className="banner is-bad">{error}</div> : null}
      <div className="table-wrap">
        <table className="positions">
          <thead>
            <tr>
              <th>Game</th>
              <th>Position</th>
              <th>Entry</th>
              <th>Last Observed</th>
              <th>Slice</th>
              <th>Mode</th>
              <th>Updated</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr
                key={row.position_id}
                onClick={() => {
                  window.location.hash = `${book === "78" ? "#/" : "#/first80/"}positions/${row.position_id}`;
                }}
              >
                <td>
                  <span className="game">{text(row.game)}</span>
                  <span className="mono muted tiny">{text(row.ticker)}</span>
                </td>
                <td>{text(row.position_label)}</td>
                <td className="mono">{cents(row.entry_price_cents)}</td>
                <td className="mono">{cents(row.last_observed_price_cents)}</td>
                <td>{text(row.slice)}</td>
                <td>HISTORICAL</td>
                <td className="mono muted">{text(row.last_observed_at || row.entry_timestamp)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
