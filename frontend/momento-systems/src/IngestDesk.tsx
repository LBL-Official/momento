import { useEffect, useState } from "react";
import { Desk } from "./Desk";

type Props = { onHome: () => void };

export default function IngestDesk({ onHome }: Props) {
  const [status, setStatus] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/auto-roller/status")
      .then(async (res) => {
        if (!res.ok) throw new Error(`/auto-roller/status ${res.status}`);
        return res.json();
      })
      .then(setStatus)
      .catch((exc: Error) => setError(exc.message));
  }, []);

  const seasons = Array.isArray(status?.declared_seasons) ? status.declared_seasons : [];

  return (
    <Desk kicker="Data Ingestion" title="Auto Roller" active="bracket">
      <div className="page-meta">
        <a className="pill" href="#/" onClick={(event) => { event.preventDefault(); onHome(); }}>
          bracket
        </a>
        <span className="pill">observe</span>
        <span className="pill">Autojest NOT_IMPLEMENTED</span>
      </div>
      {error ? <p className="banner is-bad">{error}</p> : null}
      {!status && !error ? <p className="muted">Loading ingest status…</p> : null}
      {status ? (
        <section className="grid">
          <article>
            <h2>STATUS</h2>
            <p>Missing sports stay unavailable. This desk does not submit and does not invent minutes.</p>
            <pre>{JSON.stringify({ ingest: status.ingest, verify: status.verify, unavailable_sports: status.unavailable_sports }, null, 2)}</pre>
          </article>
          <article>
            <h2>DECLARED SEASONS</h2>
            <ul>
              {seasons.map((row) => {
                const item = row as { sport?: string; season?: string; root_exists?: boolean };
                return (
                  <li key={`${item.sport}-${item.season}`}>
                    {item.sport} {item.season} · {item.root_exists ? "present" : "UNAVAILABLE"}
                  </li>
                );
              })}
            </ul>
          </article>
        </section>
      ) : null}
    </Desk>
  );
}
