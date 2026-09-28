import type { WarehouseRecord } from "./warehouseApi";

type Props = {
  warehouse: WarehouseRecord;
};

export default function WarehouseProperties({ warehouse }: Props) {
  return (
    <dl>
      <dt>Id</dt>
      <dd className="ju-drive-mono">{warehouse.id}</dd>
      <dt>Status</dt>
      <dd>{warehouse.status}</dd>
      <dt>Source</dt>
      <dd className="ju-drive-mono">{warehouse.source_uri}</dd>
      <dt>Storage</dt>
      <dd>{warehouse.storage_type}</dd>
      <dt>Adapter</dt>
      <dd>{warehouse.query_adapter}</dd>
      <dt>Season</dt>
      <dd>{warehouse.season}</dd>
      <dt>Read only</dt>
      <dd>{warehouse.read_only ? "true" : "false"}</dd>
      <dt>Description</dt>
      <dd>{warehouse.description}</dd>
    </dl>
  );
}
