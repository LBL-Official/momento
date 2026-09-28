import { FormEvent, useEffect, useState } from "react";
import ColumnInspector from "./ColumnInspector";
import DatabaseTabs from "./DatabaseTabs";
import RowInspector from "./RowInspector";
import TableGrid from "./TableGrid";
import TableStatistics from "./TableStatistics";
import TableStructure from "./TableStructure";
import type { RowFilter, RowPage, TableDetail, WarehouseColumn } from "./warehouseApi";
import { getTableLineage, getTableRows, getTableStats, getWarehouseTable } from "./warehouseApi";

type Tab = "data" | "structure" | "properties" | "stats";

type Props = {
  warehouseId: string;
  tableName: string;
  tab: Tab;
  onTab: (tab: Tab) => void;
};

export default function TableBrowser({ warehouseId, tableName, tab, onTab }: Props) {
  const [detail, setDetail] = useState<TableDetail | null>(null);
  const [page, setPage] = useState<RowPage | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sort, setSort] = useState<string>("");
  const [order, setOrder] = useState<"asc" | "desc">("asc");
  const [pageN, setPageN] = useState(1);
  const [filterCol, setFilterCol] = useState("");
  const [filterOp, setFilterOp] = useState("eq");
  const [filterVal, setFilterVal] = useState("");
  const [filters, setFilters] = useState<RowFilter[]>([]);
  const [selectedRow, setSelectedRow] = useState<Record<string, unknown> | null>(null);
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);
  const [selectedCol, setSelectedCol] = useState<WarehouseColumn | null>(null);
  const [stats, setStats] = useState<Record<string, unknown> | null>(null);
  const [statsLoading, setStatsLoading] = useState(false);
  const [lineage, setLineage] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    setSelectedRow(null);
    setSelectedIndex(null);
    getWarehouseTable(warehouseId, tableName)
      .then((body) => {
        if (!cancelled) setDetail(body);
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message);
      });
    return () => {
      cancelled = true;
    };
  }, [warehouseId, tableName]);

  useEffect(() => {
    if (tab !== "data") return;
    let cancelled = false;
    getTableRows(warehouseId, tableName, {
      page: pageN,
      limit: 100,
      sort: sort || undefined,
      order,
      filters,
    })
      .then((body) => {
        if (!cancelled) setPage(body);
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message);
      });
    return () => {
      cancelled = true;
    };
  }, [warehouseId, tableName, tab, pageN, sort, order, filters]);

  useEffect(() => {
    if (tab !== "stats") return;
    getTableStats(warehouseId, tableName, false)
      .then(setStats)
      .catch((err: Error) => setError(err.message));
  }, [warehouseId, tableName, tab]);

  useEffect(() => {
    if (tab !== "properties") return;
    getTableLineage(warehouseId, tableName)
      .then(setLineage)
      .catch((err: Error) => setError(err.message));
  }, [warehouseId, tableName, tab]);

  function applyFilter(event: FormEvent) {
    event.preventDefault();
    if (!filterCol.trim()) {
      setFilters([]);
      setPageN(1);
      return;
    }
    setFilters([{ column: filterCol.trim(), op: filterOp, value: filterVal }]);
    setPageN(1);
  }

  function onSort(column: string) {
    if (sort === column) setOrder(order === "asc" ? "desc" : "asc");
    else {
      setSort(column);
      setOrder("asc");
    }
    setPageN(1);
  }

  const columns = detail?.columns || [];

  return (
    <section className="ju-wh-table">
      <header>
        <h1>{detail?.logical_name || tableName}</h1>
        <p className="ju-drive-meta">
          {detail?.kind} · {detail?.row_count?.toLocaleString()} rows · PIT {detail?.pit_status || "UNKNOWN"} · used_by{" "}
          {(detail?.used_by || []).join(", ") || "none"}
        </p>
      </header>
      <DatabaseTabs
        tabs={[
          { id: "data", label: "Data" },
          { id: "structure", label: "Structure" },
          { id: "properties", label: "Properties" },
          { id: "stats", label: "Statistics" },
        ]}
        active={tab}
        onSelect={(id) => onTab(id as Tab)}
      />
      {error ? <p className="ju-drive-error">{error}</p> : null}
      {tab === "data" ? (
        <div className="ju-wh-data">
          <form className="ju-wh-filters" onSubmit={applyFilter}>
            <select value={filterCol} onChange={(event) => setFilterCol(event.target.value)}>
              <option value="">No filter</option>
              {columns.map((col) => (
                <option key={col.name} value={col.name}>
                  {col.name}
                </option>
              ))}
            </select>
            <select value={filterOp} onChange={(event) => setFilterOp(event.target.value)}>
              <option value="eq">=</option>
              <option value="ne">!=</option>
              <option value="lt">&lt;</option>
              <option value="gt">&gt;</option>
              <option value="contains">contains</option>
              <option value="is_null">is null</option>
              <option value="not_null">not null</option>
            </select>
            <input value={filterVal} onChange={(event) => setFilterVal(event.target.value)} />
            <button type="submit" className="ju-drive-quiet">
              Apply
            </button>
          </form>
          {page ? (
            <>
              <TableGrid
                columns={page.columns}
                rows={page.rows}
                sort={sort}
                order={order}
                selectedIndex={selectedIndex}
                onSort={onSort}
                onSelectRow={(index, row) => {
                  setSelectedIndex(index);
                  setSelectedRow(row);
                }}
              />
              <div className="ju-wh-pager">
                <button type="button" className="ju-drive-quiet" disabled={pageN <= 1} onClick={() => setPageN(pageN - 1)}>
                  Previous
                </button>
                <span>
                  page {page.page} · showing {page.returned} of {page.filtered_row_count.toLocaleString()} (table{" "}
                  {page.table_row_count.toLocaleString()})
                </span>
                <button
                  type="button"
                  className="ju-drive-quiet"
                  disabled={page.offset + page.returned >= page.filtered_row_count}
                  onClick={() => setPageN(pageN + 1)}
                >
                  Next
                </button>
              </div>
            </>
          ) : (
            <p className="ju-drive-meta">Loading rows.</p>
          )}
          <aside>
            <h2>Row inspector</h2>
            <RowInspector row={selectedRow} />
          </aside>
        </div>
      ) : null}
      {tab === "structure" ? (
        <div className="ju-wh-split">
          <TableStructure
            columns={columns}
            active={selectedCol?.name}
            onSelect={(name) => setSelectedCol(columns.find((col) => col.name === name) || null)}
          />
          <ColumnInspector column={selectedCol} />
        </div>
      ) : null}
      {tab === "properties" ? (
        <dl>
          <dt>Source URI</dt>
          <dd className="ju-drive-mono">{String(lineage?.source_uri || detail?.source_uri || "")}</dd>
          <dt>Confirm & Run</dt>
          <dd>{String(lineage?.confirm_and_run || "canonical CSV, not this parquet desk")}</dd>
          <dt>used_by</dt>
          <dd>{((lineage?.used_by as string[]) || detail?.used_by || []).join(", ") || "none"}</dd>
          <dt>PIT</dt>
          <dd>
            {String(lineage?.pit_field || detail?.pit_field || "UNKNOWN")} / {String(lineage?.pit_status || detail?.pit_status)}
          </dd>
        </dl>
      ) : null}
      {tab === "stats" ? (
        <TableStatistics
          stats={stats}
          loading={statsLoading}
          onCompute={() => {
            setStatsLoading(true);
            getTableStats(warehouseId, tableName, true)
              .then(setStats)
              .catch((err: Error) => setError(err.message))
              .finally(() => setStatsLoading(false));
          }}
        />
      ) : null}
    </section>
  );
}
