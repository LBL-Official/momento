type Props = {
  open: boolean;
  name: string;
  description: string;
  busy?: boolean;
  error?: string | null;
  onChangeName: (value: string) => void;
  onChangeDescription: (value: string) => void;
  onCancel: () => void;
  onSave: () => void;
};

export default function StaxSaveModal({
  open,
  name,
  description,
  busy,
  error,
  onChangeName,
  onChangeDescription,
  onCancel,
  onSave,
}: Props) {
  if (!open) return null;
  return (
    <div className="stax-picker-overlay" role="dialog" aria-label="Save STAX">
      <div className="stax-picker">
        <p className="ws-kicker">Save STAX</p>
        <h2 className="ws-title">Library object</h2>
        <label className="stax-field">
          <span>STAX NAME</span>
          <input value={name} onChange={(e) => onChangeName(e.target.value)} placeholder="NBA Q3 Path Research" />
        </label>
        <label className="stax-field">
          <span>DESCRIPTION (optional)</span>
          <textarea value={description} onChange={(e) => onChangeDescription(e.target.value)} rows={3} />
        </label>
        {error ? <p className="stax-error">{error}</p> : null}
        <div className="stax-actions">
          <button type="button" className="btn-secondary" onClick={onCancel}>
            Cancel
          </button>
          <button type="button" className="btn-primary" onClick={onSave} disabled={busy || !name.trim()}>
            {busy ? "Saving…" : "Save STAX"}
          </button>
        </div>
      </div>
    </div>
  );
}
