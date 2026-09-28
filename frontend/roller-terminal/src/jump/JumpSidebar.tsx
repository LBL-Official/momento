import type { DriveArtifact, SportInfo } from "./api/jumpApi";
import SportSelector from "./SportSelector";

type Props = {
  sports: SportInfo[];
  sport: string;
  tree: DriveArtifact[];
  onSport: (sport: string) => void;
  onOpen: (row: DriveArtifact) => void;
};

function Tree({ nodes, onOpen }: { nodes: DriveArtifact[]; onOpen: (row: DriveArtifact) => void }) {
  return (
    <ul>
      {nodes.map((node) => (
        <li key={node.artifact_id}>
          <button type="button" onClick={() => onOpen(node)}>
            {node.display_name || node.name}
          </button>
          {node.children?.length ? <Tree nodes={node.children} onOpen={onOpen} /> : null}
        </li>
      ))}
    </ul>
  );
}

export default function JumpSidebar({ sports, sport, tree, onSport, onOpen }: Props) {
  const current = tree.find((node) => node.sport?.toLowerCase() === sport.toLowerCase());
  return (
    <aside className="ju-drive-nav">
      <h2>Sports</h2>
      <SportSelector sports={sports} current={sport} onSelect={onSport} />
      <button type="button" className="ju-drive-quiet" onClick={() => onOpen({
        artifact_id: "research-data",
        name: "DATA / RESEARCH",
        artifact_type: "FOLDER",
        system_owner: "data_modeling",
      })}>
        DATA / RESEARCH
      </button>
      <button type="button" className="ju-drive-quiet" onClick={() => onOpen({
        artifact_id: "databases",
        name: "Warehouses",
        artifact_type: "FOLDER",
        system_owner: "database",
      })}>
        Warehouses
      </button>
      {current?.children?.length ? (
        <>
          <h2>{current.name}</h2>
          <Tree nodes={current.children} onOpen={onOpen} />
        </>
      ) : null}
    </aside>
  );
}
