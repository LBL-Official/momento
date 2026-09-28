import { useEffect, useMemo, useState } from "react";
import {
  downloadWarehouseLabCsv,
  getWarehouseLab,
  listWarehouseLabs,
  type WarehouseLab,
} from "../../api/warehouseResearch";

export default function ResultsLabsView() {
  const [labs, setLabs] = useState<WarehouseLab[]>([]);
  const [folders, setFolders] = useState<string[]>([]);
  const [folder, setFolder] = useState("ALL");
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<"created" | "name">("created");
  const [inspect, setInspect] = useState<WarehouseLab | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = () => {
    listWarehouseLabs(folder === "ALL" ? undefined : folder)
      .then((body) => {
        setLabs(body.labs);
        setFolders(body.folders);
        setError(null);
      })
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  };

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [folder]);

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    const rows = labs.filter((lab) => {
      if (folder !== "ALL" && lab.folder !== folder) return false;
      if (!q) return true;
      return `${lab.strategy_name} ${lab.folder} ${lab.result_hash || ""}`.toLowerCase().includes(q);
    });
    return [...rows].sort((a, b) => {
      if (sort === "name") return a.strategy_name.localeCompare(b.strategy_name);
      return String(b.created_at || "").localeCompare(String(a.created_at || ""));
    });
  }, [folder, labs, query, sort]);

  return (
    <div className="v2-library ws-results-labs">
      <header className="v2-view-header">
        <h1 className="v2-page-title">ROLLER Results Labs</h1>
        <p className="v2-lede">
          Saved warehouse strategies. Canonical CSV is a lab artifact, not the warehouse. Candle-path ≠ fill.
        </p>
      </header>
      <div className="ws-labs-toolbar">
        <label>
          Folder
          <select value={folder} onChange={(e) => setFolder(e.target.value)}>
            <option value="ALL">All</option>
            {folders.map((f) => (
              <option key={f} value={f}>
                {f}
              </option>
            ))}
          </select>
        </label>
        <label>
          Sort
          <select value={sort} onChange={(e) => setSort(e.target.value as "created" | "name")}>
            <option value="created">Newest</option>
            <option value="name">Name</option>
          </select>
        </label>
        <input
          type="search"
          placeholder="Filter name or hash"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <button type="button" className="btn-secondary" onClick={refresh}>
          Refresh
        </button>
      </div>
      {error ? <p className="muted small">{error}</p> : null}
      <ul className="ws-labs-list">
        {visible.map((lab) => (
          <li key={lab.lab_id}>
            <div>
              <strong>{lab.strategy_name}</strong>
              <p className="muted small">
                {lab.folder} · {lab.filename} · {lab.created_at || "—"}
              </p>
            </div>
            <div className="ws-labs-actions">
              <button
                type="button"
                className="v2-text-link"
                onClick={() => {
                  void getWarehouseLab(lab.lab_id).then(setInspect).catch((e) => setError(String(e)));
                }}
              >
                Inspect
              </button>
              <button
                type="button"
                className="v2-text-link"
                onClick={() => void downloadWarehouseLabCsv(lab.lab_id, lab.filename)}
              >
                Download CSV
              </button>
            </div>
          </li>
        ))}
        {!visible.length ? <li className="muted">No saved warehouse strategies in this folder.</li> : null}
      </ul>
      {inspect ? (
        <section className="ws-labs-inspect" aria-label="Lab specification">
          <p className="v2-kicker">Inspect</p>
          <h2>{inspect.strategy_name}</h2>
          <pre className="spec-json">{JSON.stringify(inspect, null, 2)}</pre>
        </section>
      ) : null}
    </div>
  );
}
