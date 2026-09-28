import type { SavedQuery } from "./warehouseApi";

type Props = {
  queries: SavedQuery[];
  active?: string | null;
  onOpen: (row: SavedQuery) => void;
  onDelete: (id: string) => void;
};

export default function SavedQueries({ queries, active, onOpen, onDelete }: Props) {
  if (!queries.length) return <p className="ju-drive-meta">No saved queries.</p>;
  return (
    <ul className="ju-wh-saved">
      {queries.map((row) => (
        <li key={row.id} className={row.id === active ? "is-active" : undefined}>
          <button type="button" onClick={() => onOpen(row)}>
            {row.name}
          </button>
          <button type="button" className="ju-drive-quiet" onClick={() => onDelete(row.id)}>
            Delete
          </button>
        </li>
      ))}
    </ul>
  );
}
