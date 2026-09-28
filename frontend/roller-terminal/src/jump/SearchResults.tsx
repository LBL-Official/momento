import type { SearchHit } from "./api/jumpApi";

type Props = {
  hits: SearchHit[];
  onOpen: (hit: SearchHit) => void;
};

export default function SearchResults({ hits, onOpen }: Props) {
  if (!hits.length) {
    return <p className="ju-drive-meta">No matching research objects.</p>;
  }
  return (
    <ul className="ju-drive-search-list">
      {hits.map((hit) => (
        <li key={`${hit.kind}-${hit.artifact_id}`}>
          <button type="button" onClick={() => onOpen(hit)}>
            <span className="ju-drive-name">{hit.title}</span>
            <span className="ju-drive-meta">
              {hit.folder}
              {hit.sport ? ` · ${hit.sport}` : ""}
              {hit.kind ? ` · ${hit.kind}` : ""}
            </span>
            {hit.snippet ? <span className="ju-drive-snippet">{hit.snippet}</span> : null}
          </button>
        </li>
      ))}
    </ul>
  );
}
