import { formatDiffValue, type ResearchSpecDiff } from "../researchDiff";

export default function ResearchSpecDiffView({
  title,
  diff,
  defaultOpen = true,
}: {
  title: string;
  diff: ResearchSpecDiff;
  defaultOpen?: boolean;
}) {
  if (diff.equal) {
    return (
      <div className="spec-diff panel-inset">
        <div className="muted small">{title}: no structural differences</div>
      </div>
    );
  }

  return (
    <details className="spec-diff panel-inset" open={defaultOpen}>
      <summary>
        {title} · {diff.changed_count} CHANGE{diff.changed_count === 1 ? "" : "S"}
      </summary>
      <ul className="diff-list">
        {diff.entries.map((e) => (
          <li key={`${e.status}-${e.path}`} className={`diff-${e.status.toLowerCase()}`}>
            <div className="diff-status">{e.status}</div>
            <div className="mono diff-path">{e.path}</div>
            {e.status === "CHANGED" ? (
              <div className="diff-values mono small">
                <span>{formatDiffValue(e.snapshot)}</span>
                <span className="muted"> → </span>
                <span>{formatDiffValue(e.current)}</span>
              </div>
            ) : e.status === "ADDED" ? (
              <div className="diff-values mono small">{formatDiffValue(e.current)}</div>
            ) : (
              <div className="diff-values mono small">{formatDiffValue(e.snapshot)}</div>
            )}
          </li>
        ))}
      </ul>
    </details>
  );
}
