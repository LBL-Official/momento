import { useMemo, useState } from "react";
import type { DriveArtifact } from "./api/jumpApi";
import FileRow from "./FileRow";

type SortKey = "name" | "type" | "sport" | "source" | "status";

type Props = {
  rows: DriveArtifact[];
  onOpen: (row: DriveArtifact) => void;
};

function value(row: DriveArtifact, key: SortKey): string {
  if (key === "name") return String(row.display_name || row.name || "").toLowerCase();
  if (key === "type") return String(row.artifact_type || "").toLowerCase();
  if (key === "sport") return String(row.sport || "").toLowerCase();
  if (key === "source") return String(row.source_path || row.system_owner || "").toLowerCase();
  return String(row.status || "").toLowerCase();
}

export default function FileTable({ rows, onOpen }: Props) {
  const [sort, setSort] = useState<SortKey>("name");
  const [dir, setDir] = useState<1 | -1>(1);

  function toggle(next: SortKey) {
    if (next === sort) {
      setDir(dir === 1 ? -1 : 1);
      return;
    }
    setSort(next);
    setDir(1);
  }

  const ordered = useMemo(() => {
    const copy = [...rows];
    copy.sort((a, b) => {
      const left = value(a, sort);
      const right = value(b, sort);
      if (left < right) return -1 * dir;
      if (left > right) return 1 * dir;
      return 0;
    });
    return copy;
  }, [rows, sort, dir]);

  return (
    <table className="ju-drive-table">
      <thead>
        <tr>
          <th>
            <button type="button" onClick={() => toggle("name")}>
              Name
            </button>
          </th>
          <th>
            <button type="button" onClick={() => toggle("type")}>
              Type
            </button>
          </th>
          <th>
            <button type="button" onClick={() => toggle("sport")}>
              Sport
            </button>
          </th>
          <th>
            <button type="button" onClick={() => toggle("source")}>
              Source
            </button>
          </th>
          <th>
            <button type="button" onClick={() => toggle("status")}>
              Status
            </button>
          </th>
        </tr>
      </thead>
      <tbody>
        {ordered.map((row) => (
          <FileRow key={row.artifact_id} row={row} onOpen={onOpen} />
        ))}
      </tbody>
    </table>
  );
}
