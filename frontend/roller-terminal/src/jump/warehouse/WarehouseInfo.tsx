import WarehouseProperties from "./WarehouseProperties";
import type { WarehouseRecord } from "./warehouseApi";

type Props = {
  warehouse: WarehouseRecord;
  validation?: Record<string, unknown> | null;
};

export default function WarehouseInfo({ warehouse, validation }: Props) {
  return (
    <section>
      <WarehouseProperties warehouse={warehouse} />
      {validation ? (
        <p className="ju-drive-meta">
          validate={String(validation.status)} · games={String(validation.games_present)} · manifest=
          {String(validation.manifest_present)}
        </p>
      ) : null}
      <p className="ju-drive-meta">Candle path is not a fill. Live execution is false.</p>
    </section>
  );
}
