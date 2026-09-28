import { useCallback, useEffect, useState } from "react";
import type { JumpLocation, TableTab, WarehousePage } from "../routing";
import { warehouseSport } from "../routing";
import DatabaseTabs from "./DatabaseTabs";
import DataDictionary from "./DataDictionary";
import PhysicalFiles from "./PhysicalFiles";
import QueryBuilder from "./QueryBuilder";
import QueryEditor from "./QueryEditor";
import QueryResults from "./QueryResults";
import RelationshipView from "./RelationshipView";
import SavedQueries from "./SavedQueries";
import TableBrowser from "./TableBrowser";
import WarehouseInfo from "./WarehouseInfo";
import WarehouseToolbar from "./WarehouseToolbar";
import WarehouseTree from "./WarehouseTree";
import WarehouseUnavailable from "./WarehouseUnavailable";
import type {
  RelationshipGraph,
  SavedQuery,
  WarehouseRecord,
  WarehouseTable,
} from "./warehouseApi";
import {
  createSavedQuery,
  createView,
  deleteSavedQuery,
  getDictionary,
  getPhysicalFiles,
  getRelationships,
  getWarehouse,
  listSavedQueries,
  listViews,
  listWarehouses,
  refreshWarehouse,
  runWarehouseQuery,
  validateWarehouse,
} from "./warehouseApi";

type Props = {
  location: JumpLocation;
  onGo: (next: JumpLocation) => void;
};

export default function WarehouseShell({ location, onGo }: Props) {
  const warehouseId = location.warehouseId;
  const [catalog, setCatalog] = useState<WarehouseRecord[]>([]);
  const [warehouse, setWarehouse] = useState<(WarehouseRecord & { tables?: WarehouseTable[] }) | null>(null);
  const [tables, setTables] = useState<WarehouseTable[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [validation, setValidation] = useState<Record<string, unknown> | null>(null);
  const [graph, setGraph] = useState<RelationshipGraph | null>(null);
  const [dictionary, setDictionary] = useState<Record<string, unknown> | null>(null);
  const [files, setFiles] = useState<Record<string, unknown> | null>(null);
  const [sql, setSql] = useState("SELECT internal_game_id, sport, season FROM games LIMIT 20");
  const [queryCols, setQueryCols] = useState<string[]>([]);
  const [queryRows, setQueryRows] = useState<Record<string, unknown>[]>([]);
  const [queryError, setQueryError] = useState<string | null>(null);
  const [saved, setSaved] = useState<SavedQuery[]>([]);
  const [views, setViews] = useState<SavedQuery[]>([]);
  const [saveName, setSaveName] = useState("untitled query");

  const loadWarehouse = useCallback((id: string) => {
    setError(null);
    getWarehouse(id)
      .then((body) => {
        setWarehouse(body);
        setTables(body.tables || []);
      })
      .catch((err: Error) => setError(err.message));
  }, []);

  useEffect(() => {
    listWarehouses()
      .then((body) => setCatalog(body.warehouses))
      .catch((err: Error) => setError(err.message));
  }, []);

  useEffect(() => {
    if (!warehouseId) return;
    loadWarehouse(warehouseId);
  }, [warehouseId, loadWarehouse]);

  const page: WarehousePage = location.warehousePage || "tables";

  useEffect(() => {
    if (!warehouseId || warehouse?.status !== "AVAILABLE") return;
    if (page === "relationships") {
      getRelationships(warehouseId).then(setGraph).catch((err: Error) => setError(err.message));
    }
    if (page === "dictionary") {
      getDictionary(warehouseId).then(setDictionary).catch((err: Error) => setError(err.message));
    }
    if (page === "files") {
      getPhysicalFiles(warehouseId).then(setFiles).catch((err: Error) => setError(err.message));
    }
    if (page === "queries") {
      listSavedQueries(warehouseId).then((body) => setSaved(body.queries)).catch((err: Error) => setError(err.message));
      listViews(warehouseId).then((body) => setViews(body.views)).catch((err: Error) => setError(err.message));
    }
  }, [warehouseId, page, warehouse?.status]);

  function goWarehouse(id: string, next: Partial<JumpLocation> = {}) {
    onGo({
      sport: warehouseSport(id),
      warehouseId: id,
      warehousePage: "tables",
      ...next,
    });
  }

  if (location.databases) {
    return (
      <section className="ju-wh-shell">
        <h1>Warehouses</h1>
        <p className="ju-drive-meta">Global catalog. NBA landing remains the research library.</p>
        <table className="ju-drive-table">
          <thead>
            <tr>
              <th>Id</th>
              <th>Sport</th>
              <th>Status</th>
              <th>Source</th>
            </tr>
          </thead>
          <tbody>
            {catalog.map((row) => (
              <tr key={row.id} onClick={() => goWarehouse(row.id)}>
                <td className="ju-drive-name">{row.display_name}</td>
                <td>{row.sport}</td>
                <td>{row.status}</td>
                <td className="ju-drive-mono">{row.source_uri}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    );
  }

  if (!warehouseId) return null;
  if (error && !warehouse) return <WarehouseUnavailable message={error} />;
  if (warehouse && warehouse.status !== "AVAILABLE") {
    return (
      <WarehouseUnavailable
        message={warehouse.unavailable_reason || warehouse.status}
        sourceUri={warehouse.source_uri}
      />
    );
  }

  const tab: TableTab = location.tableTab || "data";

  return (
    <section className="ju-wh-shell">
      <WarehouseToolbar
        warehouseId={warehouseId}
        onRefresh={() => {
          refreshWarehouse(warehouseId).then(() => loadWarehouse(warehouseId));
        }}
        onValidate={() => {
          validateWarehouse(warehouseId).then(setValidation);
        }}
      />
      <DatabaseTabs
        tabs={[
          { id: "tables", label: "Tables" },
          { id: "relationships", label: "Relationships" },
          { id: "queries", label: "SQL" },
          { id: "dictionary", label: "Dictionary" },
          { id: "files", label: "Physical files" },
          { id: "info", label: "Warehouse info" },
        ]}
        active={location.tableName ? "tables" : page}
        onSelect={(id) =>
          goWarehouse(warehouseId, { warehousePage: id as WarehousePage, tableName: undefined, tableTab: undefined, queryId: undefined })
        }
      />
      <div className="ju-wh-body">
        {page === "tables" || location.tableName ? (
          <div className="ju-wh-tables">
            <WarehouseTree
              tables={tables}
              active={location.tableName}
              onOpen={(name) => goWarehouse(warehouseId, { tableName: name, tableTab: "data", warehousePage: "tables" })}
            />
            {location.tableName ? (
              <TableBrowser
                key={location.tableName}
                warehouseId={warehouseId}
                tableName={location.tableName}
                tab={tab}
                onTab={(next) =>
                  goWarehouse(warehouseId, { tableName: location.tableName, tableTab: next, warehousePage: "tables" })
                }
              />
            ) : (
              <p className="ju-drive-meta">Select a table. Observations paginate at 100 rows. Candle path is not a fill.</p>
            )}
          </div>
        ) : null}
        {page === "relationships" ? (
          <RelationshipView warehouseId={warehouseId} graph={graph} onChange={setGraph} />
        ) : null}
        {page === "queries" ? (
          <div className="ju-wh-sql">
            <QueryBuilder tables={tables} onApply={setSql} />
            <QueryEditor
              sql={sql}
              onChange={setSql}
              onRun={() => {
                setQueryError(null);
                runWarehouseQuery(warehouseId, sql, 100)
                  .then((body) => {
                    setQueryCols(body.columns);
                    setQueryRows(body.rows);
                  })
                  .catch((err: Error) => setQueryError(err.message));
              }}
            />
            <div className="ju-wh-save">
              <input value={saveName} onChange={(event) => setSaveName(event.target.value)} />
              <button
                type="button"
                className="ju-drive-quiet"
                onClick={() => {
                  createSavedQuery({ warehouse_id: warehouseId, name: saveName, sql }).then((row) => {
                    setSaved((prev) => [row, ...prev]);
                    goWarehouse(warehouseId, { warehousePage: "queries", queryId: row.id });
                  });
                }}
              >
                Save query
              </button>
              <button
                type="button"
                className="ju-drive-quiet"
                onClick={() => {
                  createView(warehouseId, { name: saveName, sql }).then((row) => setViews((prev) => [row, ...prev]));
                }}
              >
                Save logical view
              </button>
            </div>
            <SavedQueries
              queries={saved}
              active={location.queryId}
              onOpen={(row) => {
                setSql(row.sql);
                goWarehouse(warehouseId, { warehousePage: "queries", queryId: row.id });
              }}
              onDelete={(id) => deleteSavedQuery(id).then(() => setSaved((prev) => prev.filter((row) => row.id !== id)))}
            />
            <h2>Logical views</h2>
            <SavedQueries queries={views} onOpen={(row) => setSql(row.sql)} onDelete={() => undefined} />
            <QueryResults columns={queryCols} rows={queryRows} error={queryError} />
          </div>
        ) : null}
        {page === "dictionary" ? <DataDictionary dictionary={dictionary} /> : null}
        {page === "files" ? <PhysicalFiles files={files} /> : null}
        {page === "info" && warehouse ? <WarehouseInfo warehouse={warehouse} validation={validation} /> : null}
      </div>
    </section>
  );
}
