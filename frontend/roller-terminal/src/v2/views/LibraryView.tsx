import { useMemo, useState } from "react";
import {
  addLibraryFolder,
  deleteLibraryEntry,
  duplicateLibraryEntry,
  libraryEntryKind,
  loadLibrary,
  moveLibraryEntry,
  renameLibraryEntry,
  type LibraryEntry,
} from "../researchLibrary";

type Props = {
  entries: LibraryEntry[];
  folders: string[];
  onRefresh: () => void;
  onOpen: (entry: LibraryEntry) => void;
  onSaveCurrent: () => void;
};

export default function LibraryView({
  entries,
  folders,
  onRefresh,
  onOpen,
  onSaveCurrent,
}: Props) {
  const [folderFilter, setFolderFilter] = useState<string>("ALL");
  const [newFolder, setNewFolder] = useState("");

  const filtered = useMemo(() => {
    if (folderFilter === "ALL") return entries;
    return entries.filter((e) => e.folder === folderFilter);
  }, [entries, folderFilter]);

  return (
    <div className="v2-library">
      <header className="v2-view-header">
        <h1 className="v2-page-title">Labs</h1>
        <p className="v2-lede">
          Local research library plus API disk saves. Questions restore the workflow. Completed
          snapshots restore Results from the terminal API when a server save id exists. Deleting
          here never deletes warehouse artifacts.
        </p>
      </header>

      <div className="v2-filter-row">
        <button type="button" className="btn-primary" onClick={onSaveCurrent}>
          Save current object
        </button>
        <select
          value={folderFilter}
          onChange={(e) => setFolderFilter(e.target.value)}
          aria-label="Folder"
        >
          <option value="ALL">All folders</option>
          {folders.map((f) => (
            <option key={f} value={f}>
              {f}
            </option>
          ))}
        </select>
        <input
          value={newFolder}
          onChange={(e) => setNewFolder(e.target.value)}
          placeholder="New folder path…"
        />
        <button
          type="button"
          className="btn-secondary"
          onClick={() => {
            if (!newFolder.trim()) return;
            addLibraryFolder(newFolder.trim());
            setNewFolder("");
            onRefresh();
          }}
        >
          New folder
        </button>
      </div>

      {!filtered.length ? (
        <p className="muted">No saved research objects yet. Start with a template →</p>
      ) : (
        <ul className="v2-library-list">
          {filtered.map((e) => (
            <li key={e.id} className="v2-library-item">
              <div className="v2-library-main">
                <button type="button" className="v2-text-link" onClick={() => onOpen(e)}>
                  {e.name}
                </button>
                <div className="muted">{e.folder}</div>
                <div className="evidence small">{e.updated_at}</div>
                <div className="v2-badge">
                  {libraryEntryKind(e) === "COMPLETE" ? "STATUS: COMPLETE" : "STATUS: QUESTION"}
                </div>
                {e.last_result?.population_n != null ? (
                  <div className="evidence">
                    n = {e.last_result.population_n}
                    {e.last_result.t40_rate != null ? ` · t40 ${e.last_result.t40_rate}` : ""}
                    {e.last_result.kalshi_yes_rate != null
                      ? ` · yes ${e.last_result.kalshi_yes_rate}`
                      : ""}
                    {e.last_result.execution_status
                      ? ` · ${e.last_result.execution_status}`
                      : ""}
                  </div>
                ) : (
                  <div className="muted small">No run saved yet</div>
                )}
                {e.saved_snapshot?.saved_at ? (
                  <div className="muted small">Snapshot {e.saved_snapshot.saved_at}</div>
                ) : null}
              </div>
              <div className="v2-library-actions">
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => {
                    const name = window.prompt("Rename", e.name);
                    if (!name) return;
                    renameLibraryEntry(e.id, name);
                    onRefresh();
                  }}
                >
                  Rename
                </button>
                <select
                  aria-label="Move"
                  defaultValue=""
                  onChange={(ev) => {
                    if (!ev.target.value) return;
                    moveLibraryEntry(e.id, ev.target.value);
                    onRefresh();
                    ev.target.value = "";
                  }}
                >
                  <option value="">Move…</option>
                  {folders.map((f) => (
                    <option key={f} value={f}>
                      {f}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => {
                    duplicateLibraryEntry(e.id);
                    onRefresh();
                  }}
                >
                  Duplicate
                </button>
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => {
                    if (!window.confirm(`Delete local save “${e.name}”?`)) return;
                    deleteLibraryEntry(e.id);
                    onRefresh();
                  }}
                >
                  Delete
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
      <p className="muted small">
        Storage key: roller.v2.research_library.v1 · entries now: {loadLibrary().entries.length}
      </p>
    </div>
  );
}
