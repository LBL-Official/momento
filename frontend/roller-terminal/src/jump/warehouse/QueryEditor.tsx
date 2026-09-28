type Props = {
  sql: string;
  onChange: (sql: string) => void;
  onRun: () => void;
};

export default function QueryEditor({ sql, onChange, onRun }: Props) {
  return (
    <div className="ju-wh-editor">
      <textarea
        value={sql}
        onChange={(event) => onChange(event.target.value)}
        spellCheck={false}
        rows={8}
      />
      <button type="button" className="ju-drive-quiet" onClick={onRun}>
        Run SELECT
      </button>
    </div>
  );
}
