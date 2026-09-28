import type { DriveArtifact, JumpObject, SourceRef } from "./api/jumpApi";

type Props = {
  selected?: DriveArtifact | null;
  object?: JumpObject | null;
  onOpenRoller?: () => void;
  onOpenSuperASI?: () => void;
};

export default function DetailsPanel({ selected, object, onOpenRoller, onOpenSuperASI }: Props) {
  const row = selected;
  const sources: SourceRef[] = object?.sources || row?.provenance || [];
  if (!row && !object) {
    return (
      <aside className="ju-drive-detail">
        <h2>Details</h2>
        <p className="ju-drive-meta">Select a folder or document.</p>
      </aside>
    );
  }
  const title = object?.display_name || row?.display_name || row?.name || "Details";
  const owner = row?.system_owner;
  return (
    <aside className="ju-drive-detail">
      <h2>{title}</h2>
      {object?.needs_resolution ? (
        <p className="ju-drive-warn">NEEDS_RESOLUTION — duplicate SuperASI folders were not merged.</p>
      ) : null}
      <dl>
        <dt>Canonical key</dt>
        <dd className="ju-drive-mono">{object?.canonical_key || row?.canonical_key || "—"}</dd>
        <dt>UUID</dt>
        <dd className="ju-drive-mono">{object?.uuid || row?.uuid || "—"}</dd>
        <dt>Sports</dt>
        <dd>{object?.sports?.join(", ") || row?.sport || "—"}</dd>
        <dt>Population</dt>
        <dd>{object?.population_label || row?.description || "—"}</dd>
        <dt>Status</dt>
        <dd>{object?.status || row?.status || "—"}</dd>
        <dt>Source</dt>
        <dd className="ju-drive-mono">{row?.source_path || object?.package_folder || "—"}</dd>
        <dt>Owner</dt>
        <dd>{owner || "data_modeling"}</dd>
      </dl>
      {sources.length ? (
        <>
          <h3>Provenance</h3>
          <ul>
            {sources.map((src) => (
              <li key={`${src.owner}-${src.path}`}>
                {src.role} · <span className="ju-drive-mono">{src.path}</span>
              </li>
            ))}
          </ul>
        </>
      ) : null}
      {owner === "database" || sources.some((src) => src.owner === "roller") ? (
        <button type="button" className="ju-drive-quiet" onClick={onOpenRoller}>
          Open source in ROLLER
        </button>
      ) : null}
      {owner === "data_analysis" || sources.some((src) => src.owner === "superasi") ? (
        <button type="button" className="ju-drive-quiet" onClick={onOpenSuperASI}>
          Open source in SuperASI
        </button>
      ) : null}
    </aside>
  );
}
