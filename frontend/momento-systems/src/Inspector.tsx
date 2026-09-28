import { useEffect, useState } from "react";
import { fetchHealth, fetchIngestion, fetchLogic, fetchSystem, fetchSystemHealth } from "./api";
import { Desk } from "./Desk";
import MarketQuery from "./MarketQuery";
import type { HealthAggregate, LogicPayload, SystemRow } from "./types";

type Props = {
  systemId: string;
  mode: "backend" | "frontend";
  onHome: () => void;
};

function List({ items }: { items: string[] }) {
  if (!items.length) return <p className="muted">none</p>;
  return (
    <ul>
      {items.map((item) => (
        <li key={item}>{item}</li>
      ))}
    </ul>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="row">
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

export default function Inspector({ systemId, mode, onHome }: Props) {
  const [row, setRow] = useState<SystemRow | null>(null);
  const [logic, setLogic] = useState<LogicPayload | null>(null);
  const [healthText, setHealthText] = useState("UNKNOWN");
  const [aggregate, setAggregate] = useState<HealthAggregate | null>(null);
  const [ingest, setIngest] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    let delay = 400;
    setAggregate(null);
    setIngest(null);
    setError(null);
    setRow(null);
    setLogic(null);
    setHealthText("UNKNOWN");
    async function load() {
      while (!cancelled) {
        try {
          const [system, note, health] = await Promise.all([
            fetchSystem(systemId),
            fetchLogic(systemId),
            fetchSystemHealth(systemId),
          ]);
          if (cancelled) return;
          setRow(system);
          setLogic(note);
          setHealthText(`${health.state}${health.ok == null ? "" : health.ok ? " / ok" : " / not-ok"}`);
          setError(null);
          return;
        } catch (exc) {
          if (!cancelled) setError((exc as Error).message);
        }
        await new Promise((resolve) => window.setTimeout(resolve, delay));
        delay = Math.min(Math.floor(delay * 1.5), 4000);
      }
    }
    load();
    if (systemId === "system_maintenance") {
      fetchHealth()
        .then((body) => {
          if (!cancelled) setAggregate(body);
        })
        .catch(() => {
          if (!cancelled) setAggregate(null);
        });
    }
    if (systemId === "data_ingestion") {
      fetchIngestion()
        .then((body) => {
          if (!cancelled) setIngest(body);
        })
        .catch(() => {
          if (!cancelled) setIngest({ state: "UNKNOWN" });
        });
    }
    return () => {
      cancelled = true;
    };
  }, [systemId]);

  if (!row || !logic) {
    return (
      <Desk kicker="Momento systems · backend" title="CONNECTING" active="bracket">
        <p className="muted">Waiting for ROLLER :8791. Retrying automatically.</p>
        {error ? <p className="muted">{error}</p> : null}
      </Desk>
    );
  }

  const comingSoon = new Set([
    "fair_odds_modeling",
    "in_house_odds_modeling",
    "game_modeling",
    "algorithmic_execution",
  ]).has(row.id);
  const title = `${row.display_name}${mode === "frontend" ? " — frontend" : " — backend"}`;

  return (
    <Desk kicker="Momento systems · backend" title={title} active="bracket">
      <div className="page-meta">
        <a
          className="pill"
          href="#/"
          onClick={(event) => {
            event.preventDefault();
            onHome();
          }}
        >
          bracket
        </a>
        <span className="pill">{row.status}</span>
        <span className="pill">{healthText}</span>
      </div>
      {comingSoon ? (
        <div className="banner">
          <h2>COMING SOON</h2>
          <p>This bracket is a placeholder. It does not operate a desk and does not submit.</p>
          {row.id === "algorithmic_execution" ? (
            <p className="muted">
              NO NBA SUBMISSION IMPLEMENTATION. NBA Bot 001 worker collects data in SHADOW; the deployed build links no submission adapter (source adapter is fixture/demo only, production orders compiled out). MLB 001 is
              reference_only. LIVE EXECUTION = FALSE.
            </p>
          ) : null}
        </div>
      ) : null}
      <section className="grid">
        <article>
          <h2>SYSTEM</h2>
          <dl>
            <Row label="id" value={row.id} />
            <Row label="purpose" value={row.purpose} />
            <Row label="status" value={row.status} />
            <Row label="version" value={row.version} />
            <Row label="api" value={row.api_namespace} />
            <Row label="health" value={healthText} />
          </dl>
        </article>
        <article>
          <h2>LOGIC</h2>
          <p>{logic.logic}</p>
        </article>
        <article>
          <h2>UPSTREAM</h2>
          <List items={row.upstream_systems} />
        </article>
        <article>
          <h2>DOWNSTREAM</h2>
          <List items={row.downstream_systems} />
        </article>
        <article>
          <h2>INPUTS</h2>
          <List items={row.input_contracts} />
        </article>
        <article>
          <h2>OUTPUTS</h2>
          <List items={row.output_contracts} />
        </article>
        <article>
          <h2>IMPLEMENTATION PATHS</h2>
          <List items={row.implementation_paths} />
        </article>
        <article>
          <h2>RESEARCH / ARTIFACT PATHS</h2>
          <List items={row.research_paths} />
        </article>
        <article>
          <h2>FEATURE FLAGS</h2>
          <List items={row.feature_flags} />
        </article>
        <article>
          <h2>LIMITATIONS</h2>
          <p>{row.notes}</p>
        </article>
        <article>
          <h2>TESTS</h2>
          <p>ROLLER/tests/test_momento_*.py plus owning-desk lock tests.</p>
        </article>
        <article>
          <h2>MIGRATION STATUS</h2>
          <p>{row.status}</p>
        </article>
        {systemId === "system_maintenance" && aggregate ? (
          <article className="wide">
            <h2>ALL SYSTEMS</h2>
            <p>nba_bot {aggregate.nba_bot}</p>
            <ul>
              {aggregate.systems.map((item) => (
                <li key={item.system_id}>
                  {item.system_id}: {item.state}
                  {item.ok == null ? "" : item.ok ? " ok" : " not-ok"}
                </li>
              ))}
            </ul>
          </article>
        ) : null}
        {systemId === "database" ? <MarketQuery /> : null}
        {systemId === "data_ingestion" && ingest ? (
          <article className="wide">
            <h2>INGEST</h2>
            <p>autojest NOT_IMPLEMENTED</p>
            <p className="muted">{JSON.stringify(ingest.autojest)}</p>
          </article>
        ) : null}
      </section>
    </Desk>
  );
}
