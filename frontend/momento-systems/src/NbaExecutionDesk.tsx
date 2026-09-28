import { useEffect, useState } from "react";

type Tab = "runtime" | "contract" | "funding" | "status" | "field_to_code" | "policy" | "policy_v0" | "strategy" | "evidence" | "testing";

const TABS: Array<[Tab, string]> = [
  ["runtime", "Runtime"],
  ["contract", "Execution Contract"],
  ["funding", "Funding & Routing"],
  ["status", "Implementation"],
  ["field_to_code", "Field → Code"],
  ["policy", "Policy v1"],
  ["policy_v0", "Policy v0 (history)"],
  ["strategy", "Strategy Spec"],
  ["evidence", "Evidence"],
  ["testing", "Testing"],
];

type Props = {
  onHome: () => void;
};

type Json = Record<string, unknown>;

const cell: React.CSSProperties = { border: "1px solid #333", padding: "4px 8px", verticalAlign: "top" };

function show(value: unknown): string {
  if (value === null || value === undefined) return "UNAVAILABLE";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function obj(value: unknown): Json {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Json) : {};
}

function list(value: unknown): Json[] {
  return Array.isArray(value) ? (value as Json[]) : [];
}

function cents(value: unknown): string {
  return typeof value === "number" ? `$${(value / 100).toFixed(2)}` : "UNAVAILABLE";
}

function Row({ label, value }: { label: string; value: unknown }) {
  return (
    <tr>
      <td style={cell}>{label}</td>
      <td style={cell}>{show(value)}</td>
    </tr>
  );
}

function Runtime({ body }: { body: Json }) {
  const worker = obj(body.worker);
  const status = obj(worker.status);
  const feed = obj(status.feed);
  const account = obj(status.account);
  const capital = obj(status.capital);
  const blockers = obj(status.blockers);
  const contract = obj(status.contract);
  const shardCash = obj(account.shard_cash_cents);
  const games = list(status.games);
  const journal = list(worker.journal_tail);
  return (
    <div>
      <h2>Worker</h2>
      <table style={{ borderCollapse: "collapse" }}>
        <tbody>
          <Row label="runtime" value={body.runtime} />
          <Row label="mode" value={body.mode} />
          <Row label="running" value={body.running} />
          <Row label="heartbeat" value={`${show(body.heartbeat)} (age ${show(worker.heartbeat_age_s)}s)`} />
          <Row label="healthy" value={body.healthy} />
          <Row label="executing" value={body.executing} />
          <Row label="service" value={status.service} />
          <Row label="version / build" value={`${show(status.version)} / ${show(status.build_id)}`} />
          <Row label="binary sha256 (process)" value={status.binary_sha256} />
          <Row label="binary sha256 (disk)" value={worker.binary_sha256_on_disk} />
          <Row label="contract" value={`${show(status.contract_id)} ${show(status.contract_sha256)}`} />
          <Row label="submission adapter linked" value={status.submission_adapter_linked} />
          <Row label="adapter environments" value={status.submission_adapter_environments} />
          <Row label="production orders compiled" value={status.production_orders_compiled} />
          <Row label="production permit" value={status.production_permit} />
          <Row label="momento-live.service (observed only)" value={worker.momento_live_active} />
          <Row label="observed at" value={worker.observed_at} />
          {worker.reason ? <Row label="reason" value={worker.reason} /> : null}
        </tbody>
      </table>

      <h2>Blockers</h2>
      {Object.keys(blockers).length === 0 ? (
        <p>{status.mode ? "none reported" : "UNAVAILABLE"}</p>
      ) : (
        <ul>
          {Object.entries(blockers).map(([code, detail]) => (
            <li key={code}>
              <b>{code}</b> {show(obj(detail).detail ?? "")}
            </li>
          ))}
        </ul>
      )}
      <p>Unresolved owner input: {show(contract.unresolved)}</p>

      <h2>Funds and capacity</h2>
      <table style={{ borderCollapse: "collapse" }}>
        <tbody>
          <Row label="account read ok" value={account.ok} />
          <Row label="account error" value={account.error ?? "none"} />
          <Row label="shard 0 cash" value={cents(shardCash["0"])} />
          <Row label="shard 3 cash" value={cents(shardCash["3"])} />
          <Row label="standard qty (6% of reference / 78¢)" value={capital.standard_qty} />
          <Row label="per-entry reserve" value={capital.standard_reserve} />
          <Row label="capacity positions by shard" value={capital.capacity_positions_by_shard} />
          <Row label="slots" value={capital.slots} />
          <Row label="batch" value={capital.batch} />
          <Row label="reserved" value={cents(capital.reserved_cents)} />
          <Row label="collateral" value={status.collateral} />
          <Row label="fees" value={status.fees} />
          <Row label="realized P&L" value={capital.realized_pnl_cents} />
        </tbody>
      </table>

      <h2>Feed</h2>
      <table style={{ borderCollapse: "collapse" }}>
        <tbody>
          <Row label="feed age (s)" value={feed.feed_age_s} />
          <Row label="public calls / errors" value={`${show(feed.public_calls_total)} / ${show(feed.public_errors_total)}`} />
          <Row label="last public error" value={feed.last_public_error ?? "none"} />
          <Row label="clock source" value={feed.clock_source} />
          <Row label="series" value={status.series} />
          <Row label="October 3" value={status.october_3} />
        </tbody>
      </table>

      <h2>Games ({games.length})</h2>
      <table style={{ borderCollapse: "collapse", fontSize: 12 }}>
        <thead>
          <tr>
            {["event", "start", "phase", "route", "pair", "clock", "markets", "candidate", "lifecycle", "shadow"].map((h) => (
              <th key={h} style={cell}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {games.map((g) => {
            const pair = obj(g.pair);
            const candidate = obj(g.candidate);
            const lifecycle = obj(g.lifecycle);
            const shadow = obj(g.shadow);
            return (
              <tr key={show(g.event_ticker)}>
                <td style={cell}>{show(g.event_ticker)}</td>
                <td style={cell}>{show(g.start)}</td>
                <td style={cell}>{show(g.phase)}</td>
                <td style={cell}>{show(g.route)}</td>
                <td style={cell}>{pair.ok ? "VERIFIED" : show(pair.reason)}</td>
                <td style={cell}>{g.clock ? show(obj(g.clock).bucket) : "UNAVAILABLE"}</td>
                <td style={cell}>
                  {list(g.markets).map((m) => (
                    <div key={show(m.ticker)}>
                      {show(m.team)} idx={show(m.exchange_index)} bid={show(m.yes_bid_cents)} ask={show(m.yes_ask_cents)} bars=
                      {show(m.bars_seen)} {show(obj(m.cross).outcome)}
                    </div>
                  ))}
                </td>
                <td style={cell}>{g.candidate ? `${show(candidate.ticker)} @ ${show(obj(candidate.signal).close_cents)}` : "none"}</td>
                <td style={cell}>{g.lifecycle ? show(lifecycle.state) : "none"}</td>
                <td style={cell}>{g.shadow ? `${show(shadow.label)} events=${list(shadow.events).length}` : "none"}</td>
              </tr>
            );
          })}
        </tbody>
      </table>

      <h2>Placeholders</h2>
      <p>{list(status.placeholders).map((p) => show(p.module)).join(", ") || "UNAVAILABLE"} — no approval, no probability.</p>

      <h2>Journal tail</h2>
      <pre style={{ whiteSpace: "pre-wrap", fontSize: 11 }}>
        {journal.map((row) => `${show(row.ts_ms)} ${show(row.kind)} ${show(row.game_id ?? "")} ${show(row.market_id ?? "")}`).join("\n") ||
          "UNAVAILABLE"}
      </pre>
    </div>
  );
}

export default function NbaExecutionDesk({ onHome }: Props) {
  const [tab, setTab] = useState<Tab>("runtime");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [body, setBody] = useState<Json | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let cancelled = false;
    fetch("/api/systimo/scope/sessions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source_node_id: "node:quad-1:algorithmic_execution" }),
    })
      .then(async (response) => {
        const payload = (await response.json()) as { session_id?: string; message?: string };
        if (!response.ok || !payload.session_id) {
          throw new Error(payload.message || `session ${response.status}`);
        }
        if (!cancelled) setSessionId(payload.session_id);
      })
      .catch((exc: Error) => {
        if (!cancelled) setError(exc.message);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (tab !== "runtime") return;
    const id = window.setInterval(() => setTick((t) => t + 1), 30000);
    return () => window.clearInterval(id);
  }, [tab]);

  useEffect(() => {
    if (!sessionId) return;
    let cancelled = false;
    setError(null);
    fetch(`/api/momento/execution/nba/${tab}`, {
      headers: { "x-momento-scope": sessionId },
    })
      .then(async (response) => {
        const payload = await response.json();
        if (!response.ok) {
          throw new Error(payload?.detail?.message || payload?.message || `desk ${response.status}`);
        }
        if (!cancelled) setBody(payload as Json);
      })
      .catch((exc: Error) => {
        if (!cancelled) setError(exc.message);
      });
    return () => {
      cancelled = true;
    };
  }, [sessionId, tab, tick]);

  return (
    <main style={{ fontFamily: "Menlo, monospace", padding: 24, background: "#111", color: "#eee", minHeight: "100vh" }}>
      <button type="button" onClick={onHome}>
        Bracket
      </button>
      <h1>NBA Bot 001 — FIRST78_67</h1>
      <p>LIVE EXECUTION = FALSE · PRODUCTION ORDERS NOT COMPILED · RUNNING ≠ HEALTHY ≠ EXECUTING · CANDLE PATH ≠ FILL</p>
      <div style={{ display: "flex", gap: 8, marginBottom: 16, flexWrap: "wrap" }}>
        {TABS.map(([id, label]) => (
          <button
            key={id}
            type="button"
            onClick={() => {
              setBody(null);
              setTab(id);
            }}
            aria-pressed={tab === id}
          >
            {label}
          </button>
        ))}
      </div>
      {error ? <p>{error}</p> : null}
      {body === null ? null : tab === "runtime" ? (
        <Runtime body={body} />
      ) : typeof body.markdown === "string" ? (
        <pre style={{ whiteSpace: "pre-wrap" }}>{body.markdown}</pre>
      ) : (
        <pre style={{ whiteSpace: "pre-wrap" }}>{JSON.stringify(body, null, 2)}</pre>
      )}
      <button type="button" disabled>
        start
      </button>
      <button type="button" disabled>
        stop
      </button>
      <button type="button" disabled>
        arm
      </button>
    </main>
  );
}
