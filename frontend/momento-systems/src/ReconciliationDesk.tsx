import { useEffect, useState } from "react";
import { Desk } from "./Desk";

type Props = { onHome: () => void };

export default function ReconciliationDesk({ onHome }: Props) {
  const [body, setBody] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/momento/reconciliation")
      .then(async (res) => {
        if (!res.ok) throw new Error(`/momento/reconciliation ${res.status}`);
        return res.json();
      })
      .then(setBody)
      .catch((exc: Error) => setError(exc.message));
  }, []);

  return (
    <Desk kicker="Trade Reconciliation" title="Observe" active="bracket">
      <div className="page-meta">
        <a className="pill" href="#/" onClick={(event) => { event.preventDefault(); onHome(); }}>
          bracket
        </a>
        <span className="pill">NOT AN OMS</span>
        <span className="pill">no submit</span>
      </div>
      {error ? <p className="banner is-bad">{error}</p> : null}
      <section className="grid">
        <article>
          <h2>EXCHANGE STATE</h2>
          <p>Unread exchange state is UNAVAILABLE. This desk does not invent fills and does not submit.</p>
          <pre>{JSON.stringify(body, null, 2)}</pre>
        </article>
      </section>
    </Desk>
  );
}
