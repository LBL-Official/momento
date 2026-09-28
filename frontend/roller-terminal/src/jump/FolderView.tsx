import type { DriveArtifact } from "./api/jumpApi";
import EmptyState from "./EmptyState";
import FileTable from "./FileTable";

type Props = {
  title: string;
  rows: DriveArtifact[];
  emptyMessage?: string | null;
  onOpen: (row: DriveArtifact) => void;
};

export default function FolderView({ title, rows, emptyMessage, onOpen }: Props) {
  return (
    <section className="ju-drive-folder">
      <h1>{title}</h1>
      {rows.length ? <FileTable rows={rows} onOpen={onOpen} /> : <EmptyState message={emptyMessage || "No items."} />}
    </section>
  );
}
