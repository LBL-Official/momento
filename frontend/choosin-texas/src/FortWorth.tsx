import { useEffect, useState } from "react";
import { UniverseError, fetchAustin } from "./api";
import { text } from "./text";

function Row({ label, value }: { label: string; value: unknown }) {
  return (
    <div className="row">
      <dt>{label}</dt>
      <dd>{text(value)}</dd>
    </div>
  );
}

export default function FortWorth() {
  const [payload, setPayload] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchAustin<Record<string, unknown>>("fort-worth/contract")
      .then(setPayload)
      .catch((err: unknown) => setError(err instanceof UniverseError ? err.message : String(err)));
  }, []);

  const policy = (payload?.policy || {}) as Record<string, unknown>;
  const hedge = (policy.hedge || {}) as Record<string, unknown>;
  const entry = (policy.entry || {}) as Record<string, unknown>;
  const contract = (payload?.last_contract || {}) as Record<string, unknown>;

  return (
    <div>
      {error ? <div className="banner is-bad">{error}</div> : null}
      <div className="page-meta">
        <span className="pill">RESEARCH_REGISTERED ≠ LIVE_ARMED</span>
        <span className="pill">no submit</span>
        <span className="pill">FILL_UNAVAILABLE</span>
      </div>
      <div className="grid">
        <article>
          <h2>Policy</h2>
          <dl>
            <Row label="entry" value={entry.rule} />
            <Row label="size" value={entry.size} />
            <Row label="reserve 120" value={entry.reserve_120} />
            <Row label="hedge when" value={hedge.when} />
            <Row label="hedge action" value={hedge.action} />
            <Row label="capital" value={hedge.capital} />
            <Row label="wick" value={hedge.wick} />
            <Row label="fallback" value={hedge.fallback} />
            <Row label="fill status" value={hedge.fill_status} />
          </dl>
        </article>
        <article>
          <h2>Last Austin contract</h2>
          <p className="muted">Austin writes this. Fort Worth does not execute it.</p>
          <dl>
            <Row label="band" value={contract.recommended_allocation_band} />
            <Row label="contracts" value={contract.contract_count} />
            <Row label="weighted EV" value={contract.weighted_ev} />
            <Row label="fee model" value={contract.fee_model_status} />
            <Row label="fill model" value={contract.fill_model_status} />
            <Row label="submits" value={contract.submits} />
          </dl>
        </article>
      </div>
      <article className="wide" style={{ marginTop: 14 }}>
        <h2>Forbidden</h2>
        <ul className="muted">
          {((policy.forbidden as string[]) || []).map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      </article>
    </div>
  );
}
