import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "./api";
import { QUERY_TYPES } from "./types";
import type {
  ArtifactRow,
  ActionRow,
  AgentRow,
  AgentRunRow,
  DatasetRow,
  GraphPayload,
  QueryResponse,
  SystimoConnection,
  SystimoHealth,
  SystimoSystem,
  SystimoTree,
  TreeSystem,
} from "./types";

function badgeClass(status: string): string {
  if (status === "HEALTHY" || status === "IMPLEMENTED") return "ok";
  if (status === "UNAVAILABLE" || status === "DECLARED") return "warn";
  return "bad";
}

function DomainTree({
  domain,
  rows,
  selected,
  onSelect,
}: {
  domain: string;
  rows: TreeSystem[];
  selected: string;
  onSelect: (id: string) => void;
}) {
  return (
    <div className="tree-node">
      <div>{domain}</div>
      {rows.map((row) => (
        <button
          key={row.id}
          className={`tree-btn${selected === row.id ? " active" : ""}`}
          onClick={() => onSelect(row.id)}
          type="button"
        >
          {row.name}
        </button>
      ))}
    </div>
  );
}

export default function App() {
  const [health, setHealth] = useState<SystimoHealth | null>(null);
  const [systems, setSystems] = useState<SystimoSystem[]>([]);
  const [connections, setConnections] = useState<SystimoConnection[]>([]);
  const [tree, setTree] = useState<SystimoTree | null>(null);
  const [graph, setGraph] = useState<GraphPayload | null>(null);
  const [datasets, setDatasets] = useState<DatasetRow[]>([]);
  const [artifacts, setArtifacts] = useState<ArtifactRow[]>([]);
  const [actions, setActions] = useState<ActionRow[]>([]);
  const [agents, setAgents] = useState<AgentRow[]>([]);
  const [agentRuns, setAgentRuns] = useState<AgentRunRow[]>([]);
  const [selectedSystem, setSelectedSystem] = useState("austin");
  const [selectedEdge, setSelectedEdge] = useState("");
  const [queryType, setQueryType] = useState("reverse_dependencies");
  const [querySubject, setQuerySubject] = useState("austin");
  const [pathFrom, setPathFrom] = useState("choosin_texas");
  const [pathTo, setPathTo] = useState("jump");
  const [queryResult, setQueryResult] = useState<QueryResponse | null>(null);
  const [workspace, setWorkspace] = useState<"registry" | "trace" | "orchestra" | "control" | "nba001">("registry");
  const [control, setControl] = useState<Record<string, unknown> | null>(null);
  const [nba001, setNba001] = useState<Record<string, unknown> | null>(null);
  const [tradeId, setTradeId] = useState("f84fd059fc0e1429");
  const [orchestra, setOrchestra] = useState<Record<string, unknown> | null>(null);
  const [traces, setTraces] = useState<Array<Record<string, string>>>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    const [
      healthBody,
      systemsBody,
      connectionsBody,
      treeBody,
      graphBody,
      datasetsBody,
      artifactsBody,
      actionsBody,
      agentsBody,
    ] = await Promise.all([
      api.health(),
      api.systems(),
      api.connections(),
      api.tree(),
      api.graph(),
      api.datasets(),
      api.artifacts(),
      api.actions(),
      api.agents(),
    ]);
    setHealth(healthBody);
    setSystems(systemsBody.systems);
    setConnections(connectionsBody.connections);
    setTree(treeBody);
    setGraph(graphBody);
    setDatasets(datasetsBody.datasets);
    setArtifacts(artifactsBody.artifacts);
    setActions(actionsBody.actions);
    setAgents(agentsBody.agents);
    setAgentRuns(agentsBody.runs ?? []);
    const tracesBody = await api.traces().catch(() => ({ traces: [] as Array<Record<string, string>> }));
    setTraces(tracesBody.traces ?? []);
    if (!selectedEdge && connectionsBody.connections.length) {
      setSelectedEdge(connectionsBody.connections[0].connection_id);
    }
  }, [selectedEdge]);

  useEffect(() => {
    load().catch((err: Error) => setError(err.message));
  }, [load]);

  const selected = useMemo(
    () => systems.find((row) => row.system_id === selectedSystem) ?? null,
    [systems, selectedSystem],
  );
  const edge = useMemo(
    () => connections.find((row) => row.connection_id === selectedEdge) ?? null,
    [connections, selectedEdge],
  );

  async function refreshNow() {
    setBusy(true);
    setError("");
    try {
      await api.refresh();
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function runOrchestra() {
    setBusy(true);
    setError("");
    try {
      setOrchestra(await api.orchestra(tradeId));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function runQuery() {
    setBusy(true);
    setError("");
    try {
      const extra: Record<string, string> = {};
      if (queryType === "paths") {
        extra.from = pathFrom;
        extra.to = pathTo;
      }
      if (queryType === "ORCHESTRA_CONTEXT" || queryType === "TRANSITION_TRACE" || queryType === "POSITMAN_PLAN" || queryType === "DREVO_DECISION") {
        extra.trade_id = tradeId;
      }
      const body = await api.query(queryType, querySubject, extra);
      setQueryResult(body);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function saveArtifact() {
    if (!queryResult) return;
    setBusy(true);
    try {
      await api.saveArtifact(queryResult.query_id, "json");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function dryRun(actionId: string) {
    setBusy(true);
    try {
      await api.dryRun(actionId);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  const domains = tree?.domains ?? {};

  return (
    <div className="desk">
      <header className="mast">
        <div>
          <h1>Systimo</h1>
          <p>System Maintenance data tunnel. Registers connections and the transition audit loop.</p>
        </div>
        <div className="status">
          <div>LIVE EXECUTION = FALSE</div>
          <div>
            csv {health?.csv_valid ? "valid" : "unknown"} · drift {health?.drift.length ?? 0} · PM{" "}
            {health?.position_management}
          </div>
          <div className="row">
            <button className={workspace === "registry" ? "primary" : ""} onClick={() => setWorkspace("registry")} type="button">
              Registry
            </button>
            <button className={workspace === "trace" ? "primary" : ""} onClick={() => setWorkspace("trace")} type="button">
              Transition trace
            </button>
            <button className={workspace === "orchestra" ? "primary" : ""} onClick={() => setWorkspace("orchestra")} type="button">
              Orchestra context
            </button>
            <button
              className={workspace === "control" ? "primary" : ""}
              onClick={() => {
                setWorkspace("control");
                const params = new URLSearchParams(window.location.search);
                const node = params.get("scope") === "quad-1" ? "node:quad-1:system_maintenance" : "node:global:system_maintenance";
                void api.session(node).then(async (session) => {
                  sessionStorage.setItem("momento_scope", session.session_id);
                  const [plan, endpoints, bots] = await Promise.all([
                    api.plan(session.scope_level === "global" ? "all" : session.quadrant_id),
                    api.endpoints(session.session_id),
                    api.bots(session.session_id),
                  ]);
                  setControl({ session, plan, endpoints, bots });
                }).catch((exc: Error) => setError(exc.message));
              }}
              type="button"
            >
              Control
            </button>
            <button
              className={workspace === "nba001" ? "primary" : ""}
              onClick={() => {
                setWorkspace("nba001");
                void api.nba001V1().then(setNba001).catch((exc: Error) => setError(exc.message));
              }}
              type="button"
            >
              NBA 001 V1
            </button>
          </div>
          <button className="primary" disabled={busy} onClick={() => void refreshNow()} type="button">
            Refresh now
          </button>
        </div>
      </header>
      {error ? <div className="error">{error}</div> : null}
      <main className="grid">
        <section className="panel">
          <h2>Registry tree</h2>
          {Object.entries(domains).map(([domain, rows]) => (
            <DomainTree
              key={domain}
              domain={domain}
              rows={rows}
              selected={selectedSystem}
              onSelect={setSelectedSystem}
            />
          ))}
          <h2>Connections</h2>
          {connections.map((row) => (
            <button
              key={row.connection_id}
              className={`edge-btn${selectedEdge === row.connection_id ? " active" : ""}`}
              onClick={() => setSelectedEdge(row.connection_id)}
              type="button"
            >
              {row.source_system_id} → {row.target_system_id}
            </button>
          ))}
        </section>
        <section className="panel">
          <h2>System inspector</h2>
          {selected ? (
            <div className="kv">
              <span>system_id</span>
              <div>{selected.system_id}</div>
              <span>display</span>
              <div>{selected.name}</div>
              <span>domain</span>
              <div>{selected.domain}</div>
              <span>role</span>
              <div>{selected.canonical_role}</div>
              <span>frontend</span>
              <div>{selected.frontend_url || "—"}</div>
              <span>api</span>
              <div>{selected.api_namespace || "—"}</div>
              <span>notes</span>
              <div>{selected.description}</div>
            </div>
          ) : (
            <p>Select a system from the tree.</p>
          )}
          <h2>Connection inspector</h2>
          {edge ? (
            <div className="kv">
              <span>id</span>
              <div>{edge.connection_id}</div>
              <span>transport</span>
              <div>{edge.transport}</div>
              <span>permission</span>
              <div>{edge.permission}</div>
              <span>lifecycle</span>
              <div>
                <span className={`badge ${badgeClass(edge.lifecycle)}`}>{edge.lifecycle}</span>
              </div>
              <span>health</span>
              <div>
                <span className={`badge ${badgeClass(edge.health)}`}>{edge.health}</span>
              </div>
              <span>lock</span>
              <div>{edge.expected_lock || "—"}</div>
              <span>notes</span>
              <div>{edge.notes}</div>
            </div>
          ) : null}
          <h2>Graph edges</h2>
          <pre>{JSON.stringify(graph?.edges ?? [], null, 2)}</pre>
          <h2>Datasets</h2>
          <pre>{JSON.stringify(datasets, null, 2)}</pre>
        </section>
        <section className="panel">
          <h2>Query terminal</h2>
          {workspace === "trace" ? (
            <>
              <h2>TRANSITION TRACE</h2>
              <p>Hash-chain audit. Systimo stores references, not Ballhog/TK/Positman/Drevo as SSOT.</p>
              {traces.length ? (
                traces.map((row) => (
                  <div key={row.trace_id} className="agent-run">
                    {row.trace_id} · {row.trade_id} · {row.current_stage} · {row.integrity_status}
                  </div>
                ))
              ) : (
                <p>No traces yet. Compose a Positman plan to append the chain.</p>
              )}
            </>
          ) : null}
          {workspace === "control" && control ? (
            <>
              <h2>CONTROL</h2>
              <p>Process running, autostart, and trading armed are separate. Trading armed stays false.</p>
              <pre>{JSON.stringify(control, null, 2)}</pre>
            </>
          ) : null}
          {workspace === "nba001" ? (
            <>
              <h2>NBA 001 FIRST78 LIVE V1</h2>
              <p>Projection only. Drevo/Positman are UNAVAILABLE observations. Missing equity is never $0. ARMED stays blocked.</p>
              <button
                disabled={busy}
                onClick={() => {
                  void api.nba001V1().then(setNba001).catch((exc: Error) => setError(exc.message));
                }}
                type="button"
              >
                Reload projection
              </button>
              {nba001 ? <pre>{JSON.stringify(nba001, null, 2)}</pre> : <p>UNAVAILABLE until the V1 control room is written.</p>}
            </>
          ) : null}
          {workspace === "orchestra" ? (
            <>
              <h2>ORCHESTRA CONTEXT</h2>
              <div className="row">
                <input value={tradeId} onChange={(event) => setTradeId(event.target.value)} />
                <button disabled={busy} onClick={() => void runOrchestra()} type="button">
                  Load context
                </button>
              </div>
              {orchestra ? <pre>{JSON.stringify(orchestra, null, 2)}</pre> : <p>QUERY only. CONTROL DENY.</p>}
            </>
          ) : null}
          <div className="row">
            <select value={queryType} onChange={(event) => setQueryType(event.target.value)}>
              {QUERY_TYPES.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
            <input value={querySubject} onChange={(event) => setQuerySubject(event.target.value)} />
            <input value={tradeId} onChange={(event) => setTradeId(event.target.value)} />
            {queryType === "paths" ? (
              <>
                <input value={pathFrom} onChange={(event) => setPathFrom(event.target.value)} />
                <input value={pathTo} onChange={(event) => setPathTo(event.target.value)} />
              </>
            ) : null}
            <button disabled={busy} onClick={() => void runQuery()} type="button">
              Run
            </button>
            <button disabled={busy || !queryResult} onClick={() => void saveArtifact()} type="button">
              Save artifact
            </button>
          </div>
          {queryResult ? <pre>{JSON.stringify(queryResult.result, null, 2)}</pre> : <p>No query yet.</p>}
          <h2>Artifacts</h2>
          {artifacts.length ? (
            artifacts.map((row) => (
              <div key={row.artifact_id} className="agent-run">
                {row.artifact_id} · {row.format} · {row.checksum.slice(0, 12)}
              </div>
            ))
          ) : (
            <p>None.</p>
          )}
          <h2>Agents</h2>
          {agents.map((row) => (
            <div key={row.agent_id} className="agent-run">
              {row.name}: {row.allowed_action_types}
            </div>
          ))}
          {agentRuns.slice(-6).map((row) => (
            <div key={row.run_id} className="agent-run">
              {row.started_at} {row.agent_id} {row.status}
            </div>
          ))}
          <h2>Allowlisted actions</h2>
          {actions.map((row) => (
            <div key={row.action_id} className="row">
              <span>{row.action_type}</span>
              {row.dry_run_supported === "true" ? (
                <button disabled={busy} onClick={() => void dryRun(row.action_id)} type="button">
                  Dry-run
                </button>
              ) : null}
            </div>
          ))}
        </section>
      </main>
      <footer className="footer">
        Systimo registers and operates the tunnel. Austin 604 and Choosin 936 stay canonical. Positman is
        a QUERY compositor. Orchestra queries Systimo only. Momento LS remains the live-host observe adapter.
      </footer>
    </div>
  );
}
