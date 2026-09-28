import { useMemo, useState } from "react";
import type { SuperasiLabSource } from "./types/superasi";

type Props = {
  labs: SuperasiLabSource[];
  folders: string[];
  selectedId: string | null;
  busy?: boolean;
  onSelect: (lab: SuperasiLabSource) => void;
  onRun: (lab: SuperasiLabSource) => void;
  onRefresh: () => void;
};

export default function Sources({ labs, folders, selectedId, busy, onSelect, onRun, onRefresh }: Props) {
  const [folder, setFolder] = useState("ALL");
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<"created" | "name">("name");

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

  const selected = visible.find((lab) => lab.lab_id === selectedId) ?? labs.find((lab) => lab.lab_id === selectedId);

  return (
    <div className="sa-page v2-library ws-results-labs">
      <header className="v2-view-header">
        <h1 className="v2-page-title">Roller CSVs</h1>
        <p className="v2-lede">
          Saved ROLLER Labs artifacts. SuperASI A — Base grades the evidence in the selected CSV. Candle path ≠ fill.
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
        <button type="button" className="btn-secondary" onClick={onRefresh}>
          Refresh
        </button>
      </div>
      <ul className="ws-labs-list">
        {visible.map((lab) => (
          <li key={lab.lab_id} className={lab.lab_id === selectedId ? "on" : undefined}>
            <button type="button" className="sa-ledger-btn" onClick={() => onSelect(lab)}>
              <strong>{lab.strategy_name}</strong>
              <p className="muted small">
                {lab.folder} · {lab.filename} · {lab.created_at || "—"}
              </p>
              <p className={lab.population_matches_rows === false ? "sa-error" : "muted small"}>
                rows={lab.rows ?? "—"} · header={lab.header_population ?? "—"}
                {lab.population_matches_rows === false ? " · population_matches_rows FAIL" : ""}
              </p>
            </button>
          </li>
        ))}
        {!visible.length ? <li className="muted">No saved Roller CSVs. Save a strategy from ROLLER Results Labs first.</li> : null}
      </ul>
      {selected ? (
        <section className="ws-labs-inspect" aria-label="Selected Roller CSV">
          <p className="v2-kicker">Selected</p>
          <h2>{selected.strategy_name}</h2>
          <p className="muted small">
            {selected.filename} · {selected.lab_id}
          </p>
          <button type="button" className="btn-primary" disabled={busy} onClick={() => onRun(selected)}>
            {busy ? "Warehouse Move is running SuperASI A…" : "Run SuperASI A — Base"}
          </button>
          {busy ? (
            <p className="muted small">
              Run stays off while Move owns A → B. Open 02 SuperASI A — Base to stop waiting, or wait for Final
              Results.
            </p>
          ) : null}
        </section>
      ) : null}
    </div>
  );
}
