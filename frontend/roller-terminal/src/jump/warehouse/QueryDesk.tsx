import { useEffect, useRef, useState } from "react";
import type { SavedQuery, WarehouseTable } from "./warehouseApi";
import {
  createSavedQuery,
  deleteSavedQuery,
  listSavedQueries,
  listViews,
  patchSavedQuery,
  runWarehouseQuery,
} from "./warehouseApi";
import QueryBuilder from "./QueryBuilder";
import QueryEditor from "./QueryEditor";
import QueryResults from "./QueryResults";
import SavedQueries from "./SavedQueries";
import { looksLikeReadonlySql, readQueryDraft, writeQueryDraft } from "./queryDraft";

type SaveState = "idle" | "saving" | "saved" | "local" | "error";

type Props = {
  warehouseId: string;
  tables: WarehouseTable[];
  queryId?: string | null;
  onQueryId: (id: string | null) => void;
};

export default function QueryDesk({ warehouseId, tables, queryId, onQueryId }: Props) {
  const [sql, setSql] = useState("SELECT internal_game_id, sport, season FROM games LIMIT 20");
  const [saveName, setSaveName] = useState("untitled query");
  const [saved, setSaved] = useState<SavedQuery[]>([]);
  const [views, setViews] = useState<SavedQuery[]>([]);
  const [queryCols, setQueryCols] = useState<string[]>([]);
  const [queryRows, setQueryRows] = useState<Record<string, unknown>[]>([]);
  const [queryError, setQueryError] = useState<string | null>(null);
  const [saveState, setSaveState] = useState<SaveState>("idle");
  const [saveDetail, setSaveDetail] = useState("Autosave on");
  const dirty = useRef(false);
  const seq = useRef(0);
  const activeId = useRef<string | null>(queryId || null);

  useEffect(() => {
    activeId.current = queryId || null;
  }, [queryId]);

  useEffect(() => {
    listSavedQueries(warehouseId)
      .then((body) => setSaved(body.queries))
      .catch(() => undefined);
    listViews(warehouseId)
      .then((body) => setViews(body.views))
      .catch(() => undefined);
    const draft = readQueryDraft(warehouseId);
    if (queryId) return;
    if (draft?.sql) {
      setSql(draft.sql);
      setSaveName(draft.name || "untitled query");
      if (draft.queryId) onQueryId(draft.queryId);
      setSaveState("local");
      setSaveDetail("Restored from this device");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [warehouseId]);

  useEffect(() => {
    if (!queryId) return;
    const row = saved.find((item) => item.id === queryId);
    if (!row) return;
    dirty.current = false;
    setSql(row.sql);
    setSaveName(row.name);
    setSaveState("saved");
    setSaveDetail("Saved to Jump");
  }, [queryId, saved]);

  useEffect(() => {
    if (!dirty.current) return;
    writeQueryDraft(warehouseId, {
      queryId: activeId.current,
      name: saveName,
      sql,
      updatedAt: new Date().toISOString(),
    });
    setSaveState("saving");
    setSaveDetail("Saving…");
    const mine = ++seq.current;
    const timer = window.setTimeout(() => {
      void flush(mine);
    }, 700);
    return () => window.clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sql, saveName, warehouseId]);

  useEffect(() => {
    function onLeave() {
      writeQueryDraft(warehouseId, {
        queryId: activeId.current,
        name: saveName,
        sql,
        updatedAt: new Date().toISOString(),
      });
    }
    window.addEventListener("beforeunload", onLeave);
    return () => {
      onLeave();
      window.removeEventListener("beforeunload", onLeave);
    };
  }, [warehouseId, saveName, sql]);

  async function flush(token: number) {
    if (!looksLikeReadonlySql(sql)) {
      if (token !== seq.current) return;
      setSaveState("local");
      setSaveDetail("Saved on this device · waiting for a valid SELECT");
      return;
    }
    try {
      let row: SavedQuery;
      if (activeId.current) {
        row = await patchSavedQuery(activeId.current, { name: saveName, sql });
      } else {
        row = await createSavedQuery({ warehouse_id: warehouseId, name: saveName || "untitled query", sql });
        activeId.current = row.id;
        onQueryId(row.id);
        setSaved((prev) => [row, ...prev.filter((item) => item.id !== row.id)]);
      }
      if (token !== seq.current) return;
      writeQueryDraft(warehouseId, {
        queryId: row.id,
        name: row.name,
        sql: row.sql,
        updatedAt: row.updated_at || new Date().toISOString(),
      });
      setSaved((prev) => prev.map((item) => (item.id === row.id ? row : item)));
      dirty.current = false;
      setSaveState("saved");
      setSaveDetail("Saved to Jump");
    } catch (err) {
      if (token !== seq.current) return;
      setSaveState("error");
      setSaveDetail(err instanceof Error ? err.message : "Could not sync");
    }
  }

  function editSql(next: string) {
    dirty.current = true;
    setSql(next);
  }

  function editName(next: string) {
    dirty.current = true;
    setSaveName(next);
  }

  return (
    <div className="ju-wh-sql">
      <p className={`ju-drive-save-status is-${saveState}`}>{saveDetail}</p>
      <QueryBuilder tables={tables} onApply={editSql} />
      <QueryEditor
        sql={sql}
        onChange={editSql}
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
        <input value={saveName} onChange={(event) => editName(event.target.value)} aria-label="Query name" />
        <button
          type="button"
          className="ju-drive-quiet"
          onClick={() => {
            createSavedQuery({ warehouse_id: warehouseId, name: `${saveName} copy`, sql }).then((row) => {
              setSaved((prev) => [row, ...prev]);
              activeId.current = row.id;
              onQueryId(row.id);
              setSaveState("saved");
              setSaveDetail("Saved to Jump");
            });
          }}
        >
          Save as new copy
        </button>
      </div>
      <SavedQueries
        queries={saved}
        active={queryId}
        onOpen={(row) => {
          dirty.current = false;
          activeId.current = row.id;
          setSql(row.sql);
          setSaveName(row.name);
          onQueryId(row.id);
          setSaveState("saved");
          setSaveDetail("Saved to Jump");
        }}
        onDelete={(id) =>
          deleteSavedQuery(id).then(() => {
            setSaved((prev) => prev.filter((row) => row.id !== id));
            if (activeId.current === id) {
              activeId.current = null;
              onQueryId(null);
            }
          })
        }
      />
      <h2>Logical views</h2>
      <SavedQueries queries={views} onOpen={(row) => editSql(row.sql)} onDelete={() => undefined} />
      <QueryResults columns={queryCols} rows={queryRows} error={queryError} />
    </div>
  );
}
