import type { StaxCandidate } from "./types";
import { leagueLabel, timeframeLabel } from "./format";

type LocalCandidate = {
  id: string;
  name: string;
  source: "session" | "library" | "save";
  payload: Record<string, unknown>;
  universe?: StaxCandidate["universe"];
  n?: number | null;
  status?: string | null;
};

type Props = {
  open: boolean;
  items: LocalCandidate[];
  error?: string | null;
  onClose: () => void;
  onPick: (item: LocalCandidate) => void;
};

export default function StaxPicker({ open, items, error, onClose, onPick }: Props) {
  if (!open) return null;
  return (
    <div className="stax-picker-overlay" role="dialog" aria-label="Add ROLLER strategy">
      <div className="stax-picker">
        <div className="stax-picker-head">
          <div>
            <p className="ws-kicker">ADD EXISTING ROLLER OBJECT</p>
            <h2 className="ws-title">Saved research objects</h2>
          </div>
          <button type="button" className="btn-secondary" onClick={onClose}>
            Close
          </button>
        </div>
        <p className="muted">
          Use an already-saved ROLLER research object. New questions use + ADD STRATEGY.
        </p>
        {error ? <p className="stax-error">{error}</p> : null}
        {!items.length ? (
          <p className="muted">No ROLLER objects available. Run or save a Quick Start result first.</p>
        ) : (
          <table className="stax-table">
            <thead>
              <tr>
                <th>Object</th>
                <th>Universe</th>
                <th>N</th>
                <th>Status</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={`${item.source}-${item.id}`}>
                  <td>
                    <div className="evidence">{item.name}</div>
                    <div className="muted small">{item.source}</div>
                  </td>
                  <td className="muted">
                    {leagueLabel(item.universe)} · {timeframeLabel(item.universe)}
                  </td>
                  <td className="evidence">{item.n ?? "—"}</td>
                  <td className="muted">{item.status || "—"}</td>
                  <td>
                    <button type="button" className="btn-primary" onClick={() => onPick(item)}>
                      Add
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
