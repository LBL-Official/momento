import { FormEvent, useState } from "react";
import type { WarehouseTable } from "./warehouseApi";

type Props = {
  tables: WarehouseTable[];
  onApply: (sql: string) => void;
};

export default function QueryBuilder({ tables, onApply }: Props) {
  const [table, setTable] = useState(tables[0]?.name || "games");
  const [columns, setColumns] = useState("*");
  const [whereCol, setWhereCol] = useState("");
  const [whereOp, setWhereOp] = useState("eq");
  const [whereVal, setWhereVal] = useState("");

  function submit(event: FormEvent) {
    event.preventDefault();
    const proj = columns.trim() || "*";
    let sql = `SELECT ${proj} FROM ${table}`;
    if (whereCol.trim()) {
      const op = whereOp === "eq" ? "=" : whereOp === "gt" ? ">" : whereOp === "lt" ? "<" : "=";
      sql += ` WHERE ${whereCol.trim()} ${op} '${whereVal.replace(/'/g, "''")}'`;
    }
    sql += " LIMIT 100";
    onApply(sql);
  }

  return (
    <form className="ju-wh-builder" onSubmit={submit}>
      <label>
        Table
        <select value={table} onChange={(event) => setTable(event.target.value)}>
          {tables.map((row) => (
            <option key={row.name} value={row.name}>
              {row.name}
            </option>
          ))}
        </select>
      </label>
      <label>
        Columns
        <input value={columns} onChange={(event) => setColumns(event.target.value)} />
      </label>
      <label>
        Where
        <input value={whereCol} onChange={(event) => setWhereCol(event.target.value)} placeholder="column" />
      </label>
      <select value={whereOp} onChange={(event) => setWhereOp(event.target.value)}>
        <option value="eq">=</option>
        <option value="gt">&gt;</option>
        <option value="lt">&lt;</option>
      </select>
      <input value={whereVal} onChange={(event) => setWhereVal(event.target.value)} placeholder="value" />
      <button type="submit" className="ju-drive-quiet">
        Build SELECT
      </button>
    </form>
  );
}
