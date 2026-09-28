import { useCallback, useEffect, useState } from "react";
import { fetchObserve } from "./api";
import type { LsSnapshot } from "./types";

const POLL_MS = 12_000;

function text(value: unknown): string {
  if (value === null || value === undefined || value === "") return "UNAVAILABLE";
  return String(value);
}

function cents(value: unknown): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "UNAVAILABLE";
  return `${value}¢`;
}

function age(iso: string | undefined, nowMs: number): string {
  if (!iso) return "UNREAD";
  const ms = Date.parse(iso);
  if (!Number.isFinite(ms)) return "UNREAD";
  const delta = Math.max(0, nowMs - ms);
  if (delta < 1000) return "now";
  if (delta < 60_000) return `${Math.floor(delta / 1000)}s`;
  if (delta < 3_600_000) return `${Math.floor(delta / 60_000)}m`;
  return `${Math.floor(delta / 3_600_000)}h`;
}

function tone(ok: boolean | undefined | null): "ok" | "bad" | "idle" {
  if (ok === true) return "ok";
  if (ok === false) return "bad";
  return "idle";
}

function Row({ label, value, mark }: { label: string; value: unknown; mark?: "ok" | "bad" | "idle" }) {
  return (
    <div className="row">
      <dt>{label}</dt>
      <dd className={mark ? `is-${mark}` : undefined}>{text(value)}</dd>
    </div>
  );
}

export default function App() {
  const [snap, setSnap] = useState<LsSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [now, setNow] = useState(() => Date.now());

  const load = useCallback(async () => {
    try {
      const next = await fetchObserve();
      setSnap(next);
      setError(null);
      setNow(Date.now());
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setNow(Date.now());
    }
  }, []);

  useEffect(() => {
    void load();
    const id = window.setInterval(() => void load(), POLL_MS);
    return () => window.clearInterval(id);
  }, [load]);

  const hashes = snap?.hashes ?? {};
  const gates = snap?.gates ?? {};
  const updates = snap?.updates ?? {};
  const occupancy = snap?.occupancy ?? {};
  const service = snap?.service ?? {};
  const process = snap?.process ?? {};
  const env = snap?.environment ?? {};
  const errors = snap?.errors ?? {};
  const journal = snap?.journal ?? [];
  const unread = !snap?.ok;

  return (
    <main className="desk">
      <header className="mast">
        <div>
          <p className="kicker">direct · momento-live.service</p>
          <h1>Momento LS</h1>
        </div>
        <div className="mast-meta">
          <span className={`pill is-${tone(!unread)}`}>{unread ? "UNREAD" : "OBSERVED"}</span>
          <span className="pill">observe only</span>
          <span className="pill">no submit</span>
          <button type="button" onClick={() => void load()}>
            refresh
          </button>
        </div>
      </header>

      {error ? <p className="banner is-bad">{error}</p> : null}
      {unread && snap ? <p className="banner is-bad">{snap.reason || snap.status || "host unread"}</p> : null}

      <section className="grid">
        <article>
          <h2>Identity</h2>
          <dl>
            <Row label="instance" value={snap?.instance_id} />
            <Row label="service" value={snap?.service_name || service.name} />
            <Row label="active" value={service.active} mark={tone(service.active === "active")} />
            <Row label="pid" value={process.main_pid} />
            <Row label="started" value={service.started_at} />
            <Row label="restarts" value={service.n_restarts} />
            <Row label="restart policy" value={service.restart} />
            <Row label="prevent exit" value={service.restart_prevent_exit_status} />
            <Row label="kalshi env" value={env.kalshi_env} />
            <Row label="bankroll" value={snap?.bankroll_cents == null ? "UNAVAILABLE" : `${snap.bankroll_cents}¢`} />
            <Row label="source" value={snap?.source} />
            <Row label="observed" value={`${text(snap?.observed_at)} · ${age(snap?.observed_at, now)}`} />
          </dl>
        </article>

        <article>
          <h2>Gates</h2>
          <dl>
            <Row
              label="reconciliation"
              value={gates.reconciliation}
              mark={tone(String(gates.reconciliation || "").toLowerCase() === "healthy")}
            />
            <Row
              label="order submission"
              value={gates.order_submission}
              mark={tone(String(gates.order_submission || "").toLowerCase() === "enabled")}
            />
            <Row label="live armed" value={gates.live_armed} mark={tone(gates.live_armed)} />
            <Row
              label="authorized"
              value={gates.authorized_to_submit}
              mark={tone(gates.authorized_to_submit)}
            />
            <Row label="kill" value={gates.kill_switch} mark={tone(gates.kill_switch === false)} />
            <Row label="open slots" value={occupancy.open_slots} />
            <Row label="max slots" value={occupancy.max_open_slots} />
            <Row label="unknown orders" value={occupancy.unknown_orders} />
            <Row label="open MLB" value={occupancy.open_mlb_positions} />
          </dl>
        </article>

        <article className="wide">
          <h2>Hashes</h2>
          <dl className="hashes">
            <Row
              label="binary"
              value={hashes.binary}
              mark={tone(hashes.baseline_match)}
            />
            <Row label="baseline" value={hashes.baseline} />
            <Row
              label="baseline match"
              value={hashes.baseline_match}
              mark={tone(hashes.baseline_match)}
            />
            <Row label="bytes" value={hashes.binary_bytes} />
            <Row label="unit" value={hashes.unit} />
            <Row label="live.toml" value={hashes.live_toml} />
            <Row label="persist" value={hashes.persist} />
            <Row label="snapshot" value={hashes.snapshot} />
          </dl>
        </article>

        <article>
          <h2>Updates</h2>
          <dl>
            <Row label="YES bids" value={updates.mlb_yes_bid_n} />
            <Row label="first80" value={updates.first80_n} />
            <Row label="first81" value={updates.first81_n} />
            <Row label="submit→ack" value={updates.submit_to_ack_n} />
            <Row label="submit refused" value={updates.submit_refused_n} />
            <Row label="heartbeats" value={updates.heartbeat_n} />
            <Row label="markets" value={updates.heartbeat_markets} />
            <Row label="strategy games" value={updates.strategy_games} />
            <Row label="recon cleared" value={updates.recon_cleared_n} />
            <Row label="fills applied" value={updates.fill_applied_n} />
            <Row label="fill apply failed" value={updates.fill_apply_failed_n} />
            <Row label="last ticker" value={updates.last_mlb_ticker} />
            <Row label="last bid" value={cents(updates.last_mlb_bid_cents)} />
            <Row label="last ask" value={cents(updates.last_mlb_ask_cents)} />
            <Row label="journal since" value={updates.journal_since} />
            <Row label="last heartbeat" value={updates.last_heartbeat} />
          </dl>
        </article>

        <article>
          <h2>Errors</h2>
          <dl>
            <Row label="count" value={errors.n} mark={tone((errors.n ?? 0) === 0)} />
            <Row label="last" value={errors.last} />
          </dl>
          <ul className="log">
            {(errors.recent || []).length === 0 ? <li>none</li> : null}
            {(errors.recent || []).map((line, i) => (
              <li key={`${i}-${line}`}>{line}</li>
            ))}
          </ul>
        </article>

        <article className="wide">
          <h2>Journal</h2>
          <ul className="log">
            {journal.length === 0 ? <li>UNAVAILABLE</li> : null}
            {journal.map((line, i) => (
              <li key={`${i}-${line}`}>{line}</li>
            ))}
          </ul>
        </article>
      </section>
    </main>
  );
}
