type Props = {
  warehouseId: string;
  readOnly?: boolean;
  onRefresh: () => void;
  onValidate: () => void;
};

export default function WarehouseToolbar({ warehouseId, readOnly = true, onRefresh, onValidate }: Props) {
  return (
    <div className="ju-wh-toolbar">
      <strong>{warehouseId} warehouse</strong>
      <span className="ju-drive-meta">{readOnly ? "read-only" : ""} · Phase 8 parquet</span>
      <button type="button" className="ju-drive-quiet" onClick={onRefresh}>
        Refresh metadata
      </button>
      <button type="button" className="ju-drive-quiet" onClick={onValidate}>
        Validate
      </button>
    </div>
  );
}
