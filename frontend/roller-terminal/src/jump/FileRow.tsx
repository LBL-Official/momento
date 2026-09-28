import type { DriveArtifact } from "./api/jumpApi";

type Props = {
  row: DriveArtifact;
  onOpen: (row: DriveArtifact) => void;
};

function kindLabel(row: DriveArtifact): string {
  if (row.artifact_type === "FOLDER") return "Folder";
  if (row.artifact_type === "DOCUMENT") return "Document";
  if (row.artifact_type === "WAREHOUSE") return "Warehouse";
  if (row.artifact_type === "TABLE") return "Table";
  if (row.kind) return row.kind;
  return row.artifact_type;
}

export default function FileRow({ row, onOpen }: Props) {
  return (
    <tr onClick={() => onOpen(row)}>
      <td className="ju-drive-name">{row.display_name || row.name}</td>
      <td>{kindLabel(row)}</td>
      <td>{row.sport || "—"}</td>
      <td className="ju-drive-mono">{row.source_path || row.system_owner}</td>
      <td>{row.status}</td>
    </tr>
  );
}
