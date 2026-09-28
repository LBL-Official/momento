import { useEffect, useState, type MouseEvent } from "react";
import { Desk } from "./Desk";

const STORAGE_KEY = "tk-ultra-live-inputs";
const INK = "#c8c4bc";
const LINE = "#2a2e36";

const ROWS: { id: string; input: string; purpose: string; owner: string }[] = [
  {
    id: "entry-stop",
    input: "Entry and the 40 stop",
    purpose: "Turns the stop into the 60¢ B average: locked = 20 − B_avg",
    owner:
      "Choosin Texas, static, N=936. The loss barrier is the stop. This prior does not change with the clock.",
  },
  {
    id: "austin-ref",
    input: "A reference price, plus the Austin read",
    purpose:
      "expected B = 100 − A_ref under β = −1. The EV and the interval sit beside that. They do not enter the residual or the route.",
    owner:
      "Austin, N=604, query_at, persist=False. The price is AUSTIN_QUERY_PRICE, a historical query price. It is the reference, not the bid you can sell.",
  },
  {
    id: "ballhog-q",
    input: "How much exposure to remove",
    purpose: "q* for the hedge you are pricing",
    owner:
      "Ballhog, and only if the state call asks for the sibling. The assessment stamps it SIBLING CONTEXT — NOT MODEL INPUT. It does not change expected B.",
  },
  {
    id: "opposing-yes",
    input: "B, the opposing YES",
    purpose: "The wing contract",
    owner: "Not on the compose. b_contract stays UNAVAILABLE unless an overlay names it.",
  },
  {
    id: "bid-ask",
    input: "A YES bid and B YES ask",
    purpose: "route edge = (100 − B_ask) − A_bid",
    owner: "Not on the compose. Missing quotes come back QUOTE_UNAVAILABLE, never 0.",
  },
  {
    id: "held-qty",
    input: "Quantity of A still held, quantity of B already bought, and the average price paid for that B",
    purpose: "The runway: how expensive the remaining B can be and still beat 60¢",
    owner: "Not on the compose. q_a, q_b, and b_avg_existing_cents arrive only as an overlay.",
  },
];

function loadChecked(): string[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    const parsed = raw ? (JSON.parse(raw) as unknown) : [];
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((id): id is string => typeof id === "string");
  } catch {
    return [];
  }
}

type Props = { onHome: () => void; onDesk: () => void };

export default function TkUltraInputs({ onHome, onDesk }: Props) {
  const [checked, setChecked] = useState<string[]>(loadChecked);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(checked));
  }, [checked]);

  function goHome(event: MouseEvent<HTMLAnchorElement>) {
    event.preventDefault();
    onHome();
  }

  function goDesk(event: MouseEvent<HTMLAnchorElement>) {
    event.preventDefault();
    onDesk();
  }

  function toggle(id: string) {
    setChecked((prev) => (prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]));
  }

  return (
    <Desk kicker="Relative value hedging · TK Ultra" title="Live Inputs Needed" active="tk-ultra">
      <p className="muted" style={{ marginTop: 14 }}>
        Check an input when that part of the bracket is supplying it. The marks stay in this browser. LIVE EXECUTION = FALSE.
      </p>
      <div className="page-meta">
        <a className="pill" href="#/" onClick={goHome}>
          bracket
        </a>
        <a className="pill" href="#/tk-ultra" onClick={goDesk}>
          calculator
        </a>
        <span className="pill">
          {checked.length}/{ROWS.length}
        </span>
      </div>
      <ul style={{ listStyle: "none", margin: "18px 0 0", padding: 0 }}>
        {ROWS.map((row) => {
          const on = checked.includes(row.id);
          return (
            <li key={row.id} style={{ display: "flex", alignItems: "flex-start", gap: 14, padding: "14px 0", borderTop: `1px solid ${LINE}` }}>
              <button
                type="button"
                aria-pressed={on}
                aria-label={`${on ? "Uncheck" : "Check"} ${row.input}`}
                onClick={() => toggle(row.id)}
                style={{
                  width: 16,
                  height: 16,
                  borderRadius: "50%",
                  border: `2px solid ${INK}`,
                  background: on ? INK : "transparent",
                  padding: 0,
                  flex: "0 0 auto",
                  cursor: "pointer",
                  marginTop: 3,
                }}
              />
              <div style={{ minWidth: 0 }}>
                <p style={{ margin: 0, color: on ? "#8b8f98" : INK }}>{row.input}</p>
                <p className="muted" style={{ margin: "6px 0 0" }}>
                  {row.purpose}
                </p>
                <p className="muted" style={{ margin: "4px 0 0" }}>
                  {row.owner}
                </p>
              </div>
            </li>
          );
        })}
      </ul>
    </Desk>
  );
}
