import { useState } from "react";
import { patchVitalParameters, type VitalParameterRow, type VitalParameters } from "./api/vitalApi";

type Props = {
  botId: string | undefined;
  parameters: VitalParameters | null;
  onError: (message: string | null) => void;
  onRefresh: () => void;
};

export default function ParameterSheet({ botId, parameters, onError, onRefresh }: Props) {
  const rows = parameters?.parameters || [];
  const editable = Boolean(parameters?.editable && parameters.spec_status !== "SPEC_MISMATCH");
  const [entry, setEntry] = useState("");
  const [win, setWin] = useState("");
  const [loss, setLoss] = useState("");
  const [budget, setBudget] = useState("");
  const [busy, setBusy] = useState(false);

  const rowValue = (key: string) => rows.find((row) => row.key === key)?.value;

  const onPatch = async () => {
    if (!botId || !editable) return;
    setBusy(true);
    onError(null);
    try {
      const body: Record<string, number> = {};
      if (entry.trim()) body.iti_entry_cents = Number(entry);
      if (win.trim()) body.iti_win_cents = Number(win);
      if (loss.trim()) body.iti_loss_cents = Number(loss);
      if (budget.trim()) body.max_position_budget_cents = Number(budget);
      await patchVitalParameters(botId, body);
      setEntry("");
      setWin("");
      setLoss("");
      setBudget("");
      onRefresh();
    } catch (err) {
      onError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="vital-card" aria-label="Parameters">
      <p className="ws-kicker">Parameters</p>
      <p className="muted small">
        {parameters?.note || "Observed constants. Browser does not submit orders."}
        {parameters?.spec_status ? ` · spec ${parameters.spec_status}` : ""}
      </p>
      {rows.length === 0 ? (
        <p className="muted small">OBSERVATION_UNAVAILABLE</p>
      ) : (
        <div className="stax-table-wrap">
          <table className="stax-table vital-param-table">
            <thead>
              <tr>
                <th>Key</th>
                <th>Value</th>
                <th>Unit</th>
                <th>Source</th>
                <th>Edit</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row: VitalParameterRow) => (
                <tr key={row.key}>
                  <td>{row.key}</td>
                  <td>{row.value == null || row.value === "" ? "OBSERVATION_UNAVAILABLE" : String(row.value)}</td>
                  <td>{row.unit}</td>
                  <td>{row.source}</td>
                  <td>{row.editable ? "DEMO" : row.locked_reason || "locked"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {editable ? (
        <div className="vital-toolbar" style={{ marginTop: "0.75rem" }}>
          <label>
            Entry ¢
            <input
              value={entry}
              onChange={(event) => setEntry(event.target.value)}
              placeholder={String(rowValue("iti_entry_cents") ?? "")}
              inputMode="numeric"
            />
          </label>
          <label>
            Win ¢
            <input
              value={win}
              onChange={(event) => setWin(event.target.value)}
              placeholder={String(rowValue("iti_win_cents") ?? "")}
              inputMode="numeric"
            />
          </label>
          <label>
            Loss ¢
            <input
              value={loss}
              onChange={(event) => setLoss(event.target.value)}
              placeholder={String(rowValue("iti_loss_cents") ?? "")}
              inputMode="numeric"
            />
          </label>
          <label>
            Budget ¢
            <input
              value={budget}
              onChange={(event) => setBudget(event.target.value)}
              placeholder={String(rowValue("max_position_budget_cents") ?? "")}
              inputMode="numeric"
            />
          </label>
          <button type="button" className="btn-secondary" disabled={busy || !botId} onClick={() => void onPatch()}>
            {busy ? "Applying…" : "Apply Demo prices"}
          </button>
        </div>
      ) : (
        <p className="muted small">Factory and production rows stay locked.</p>
      )}
    </section>
  );
}
