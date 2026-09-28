import { useState } from "react";
import { Desk } from "./Desk";

const TRADE = "f84fd059fc0e1429";

type Props = { onHome: () => void };

export default function OrchestraDesk({ onHome }: Props) {
  const [tradeId, setTradeId] = useState(TRADE);
  const [body, setBody] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function load() {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`/api/systimo/orchestra/context/${encodeURIComponent(tradeId)}`);
      const payload = await res.json();
      if (!res.ok) throw new Error(payload?.detail?.message || `orchestra ${res.status}`);
      setBody(payload);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Desk kicker="Orchestra" title="Systimo query" active="bracket">
      <div className="page-meta">
        <a className="pill" href="#/" onClick={(event) => { event.preventDefault(); onHome(); }}>
          bracket
        </a>
        <span className="pill">QUERY ONLY</span>
        <span className="pill">CONTROL DENY</span>
      </div>
      <p className="muted">
        Orchestra reads Systimo. It does not start jobs, does not call Vital, and does not submit.
      </p>
      <div className="row">
        <input value={tradeId} onChange={(event) => setTradeId(event.target.value)} />
        <button disabled={busy} type="button" onClick={() => void load()}>
          Load context
        </button>
      </div>
      {error ? <p className="banner is-bad">{error}</p> : null}
      {body ? <pre>{JSON.stringify(body, null, 2)}</pre> : <p className="muted">No context loaded.</p>}
    </Desk>
  );
}
