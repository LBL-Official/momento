import { FormEvent, useEffect, useState } from "react";
import {
  DEFAULT_TRADE,
  getDataContext,
  getLineage,
  postDataQuery,
  postExport,
  type DataNode,
  type JumpContext,
} from "./dataApi";

type Props = {
  tradeId?: string;
  onTrade: (tradeId: string) => void;
};

function Tree({
  nodes,
  selected,
  onSelect,
}: {
  nodes: DataNode[];
  selected: string;
  onSelect: (node: DataNode) => void;
}) {
  return (
    <ul>
      {nodes.map((node) => (
        <li key={node.id}>
          <button type="button" className={selected === node.id ? "is-active" : ""} onClick={() => onSelect(node)}>
            {node.label} · {node.owner} · {node.availability}
          </button>
          {node.children?.length ? <Tree nodes={node.children} selected={selected} onSelect={onSelect} /> : null}
        </li>
      ))}
    </ul>
  );
}

export default function DataExplorer({ tradeId, onTrade }: Props) {
  const [trade, setTrade] = useState(tradeId || DEFAULT_TRADE);
  const [asOf, setAsOf] = useState("");
  const [context, setContext] = useState<JumpContext | null>(null);
  const [selected, setSelected] = useState<DataNode | null>(null);
  const [lineage, setLineage] = useState<unknown>(null);
  const [queryResult, setQueryResult] = useState<unknown>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function load(nextTrade = trade, nextAsOf = asOf) {
    setBusy(true);
    setError("");
    try {
      const body = await getDataContext(nextTrade, nextAsOf || undefined);
      setContext(body);
      setSelected(body.tree?.nodes?.[0] ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    void load(tradeId || DEFAULT_TRADE, asOf);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tradeId]);

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    onTrade(trade);
    void load(trade, asOf);
  }

  async function showSource() {
    setBusy(true);
    try {
      const body = await getLineage("austin", {
        capability: "AUSTIN_QUERY_AT",
        trade_id: trade,
        as_of: asOf,
      });
      setLineage(body);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function queryUpstream(capability: string) {
    setBusy(true);
    try {
      const body = await postDataQuery(capability, { trade_id: trade, as_of: asOf || undefined, ticker: context?.identity?.ticker });
      setQueryResult(body);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function exportAustin() {
    setBusy(true);
    try {
      const body = await postExport("austin_nba_2q3q_604");
      setQueryResult(body);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  const austin = context?.Austin || {};
  const inspect = selected?.payload ?? selected;

  return (
    <section className="ju-drive-folder">
      <h1>DATA / RESEARCH</h1>
      <p>Jump queries the stack. Sources keep ownership. LIVE EXECUTION = FALSE.</p>
      <form className="ju-drive-search" onSubmit={onSubmit}>
        <input value={trade} onChange={(event) => setTrade(event.target.value)} aria-label="trade_id" />
        <input value={asOf} onChange={(event) => setAsOf(event.target.value)} placeholder="as_of" aria-label="as_of" />
        <button type="submit" disabled={busy}>
          Load
        </button>
        <button type="button" disabled={busy} onClick={() => void showSource()}>
          SHOW SOURCE
        </button>
        <button type="button" disabled={busy} onClick={() => void exportAustin()}>
          EXPORT Austin 604
        </button>
      </form>
      {error ? <p className="banner is-bad">{error}</p> : null}
      <div className="ju-drive-body">
        <nav className="ju-drive-nav">
          <h2>Resource tree</h2>
          {context?.tree?.nodes ? (
            <Tree nodes={context.tree.nodes} selected={selected?.id || ""} onSelect={setSelected} />
          ) : (
            <p>No tree.</p>
          )}
          <h2>Universes</h2>
          <p>Austin {String((context?.universes as { austin?: { n?: number } } | undefined)?.austin?.n ?? 604)} ≠ Choosin {String((context?.universes as { choosin_texas?: { n?: number } } | undefined)?.choosin_texas?.n ?? 936)}</p>
        </nav>
        <div className="ju-drive-main">
          <h2>{selected?.label || "Inspector"}</h2>
          <p>
            owner {selected?.owner || "—"} · {selected?.availability || String(austin.availability || "—")}
          </p>
          <div className="ju-drive-search">
            <button type="button" onClick={() => void queryUpstream("AUSTIN_QUERY_AT")}>
              Query Austin
            </button>
            <button type="button" onClick={() => void queryUpstream("CHOOSIN_TRADE_CONTEXT")}>
              Query Choosin
            </button>
            <button type="button" onClick={() => void queryUpstream("BALLHOG_INTENT")}>
              Query Ballhog
            </button>
            <button type="button" onClick={() => void queryUpstream("TK_ULTRA_ASSESSMENT")}>
              Query TK Ultra
            </button>
            <button type="button" onClick={() => void queryUpstream("ROLLER_OBSERVATIONS")}>
              Query ROLLER observations
            </button>
          </div>
          <pre>{JSON.stringify(inspect, null, 2)}</pre>
          {queryResult ? (
            <>
              <h2>Query / export</h2>
              <pre>{JSON.stringify(queryResult, null, 2)}</pre>
            </>
          ) : null}
          {lineage ? (
            <>
              <h2>Lineage</h2>
              <pre>{JSON.stringify(lineage, null, 2)}</pre>
            </>
          ) : null}
        </div>
      </div>
    </section>
  );
}
