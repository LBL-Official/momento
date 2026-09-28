import { useState } from "react";
import { DEFAULT_FOLDERS } from "../researchLibrary";

type Props = {
  defaultName: string;
  defaultFolder: string;
  defaultDescription: string;
  busy?: boolean;
  error?: string | null;
  onCancel: () => void;
  onSave: (input: { name: string; folder: string; description: string }) => void;
};

export default function SaveResultsModal({
  defaultName,
  defaultFolder,
  defaultDescription,
  busy,
  error,
  onCancel,
  onSave,
}: Props) {
  const [name, setName] = useState(defaultName);
  const [folder, setFolder] = useState(defaultFolder);
  const [description, setDescription] = useState(defaultDescription);

  return (
    <div className="ws-modal-backdrop" role="presentation" onClick={onCancel}>
      <div
        className="ws-modal"
        role="dialog"
        aria-labelledby="save-results-title"
        onClick={(e) => e.stopPropagation()}
      >
        <p className="v2-kicker">Saved result snapshot · local</p>
        <h2 id="save-results-title">Save results</h2>
        <p className="muted small">
          Stores the full measurement on the terminal API disk. The browser library keeps a
          compact pointer so Save does not fail on localStorage quota.
        </p>
        {error ? <p className="sa-error">{error}</p> : null}
        <label>
          Name
          <input value={name} onChange={(e) => setName(e.target.value)} />
        </label>
        <label>
          Folder
          <select value={folder} onChange={(e) => setFolder(e.target.value)}>
            {DEFAULT_FOLDERS.map((f) => (
              <option key={f} value={f}>
                {f}
              </option>
            ))}
          </select>
        </label>
        <label>
          Description
          <textarea rows={3} value={description} onChange={(e) => setDescription(e.target.value)} />
        </label>
        <div className="ws-modal-actions">
          <button type="button" className="btn-secondary" onClick={onCancel}>
            Cancel
          </button>
          <button
            type="button"
            className="btn-primary"
            disabled={!name.trim() || busy}
            onClick={() =>
              onSave({
                name: name.trim(),
                folder,
                description: description.trim(),
              })
            }
          >
            {busy ? "Saving…" : "Save results"}
          </button>
        </div>
      </div>
    </div>
  );
}
