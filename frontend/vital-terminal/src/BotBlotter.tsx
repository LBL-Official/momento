import type { VitalBot } from "./api/vitalApi";
import { activationLabel, bookLabel, sportLabel } from "./desk";
import { toneForLifecycle } from "./format";

type Props = {
  bots: VitalBot[];
  selectedId?: string;
  onOpen: (botId: string) => void;
};

export default function BotBlotter({ bots, selectedId, onOpen }: Props) {
  return (
    <div className="stax-table-wrap">
      <table className="stax-table vital-blotter">
        <thead>
          <tr>
            <th>Id</th>
            <th>Name</th>
            <th>Sport</th>
            <th>Book</th>
            <th>Lifecycle</th>
            <th>Unit</th>
            <th>Lineage</th>
          </tr>
        </thead>
        <tbody>
          {bots.length === 0 ? (
            <tr>
              <td colSpan={7} className="muted small">
                No Vital bots registered.
              </td>
            </tr>
          ) : (
            bots.map((bot) => {
              const life = activationLabel(bot);
              return (
                <tr
                  key={bot.bot_id}
                  className={`stax-click${selectedId === bot.bot_id ? " is-selected" : ""}`}
                  onClick={() => onOpen(bot.bot_id)}
                >
                  <td>{bot.bot_id}</td>
                  <td>{bot.name || bot.bot_id}</td>
                  <td>{sportLabel(bot)}</td>
                  <td>{bookLabel(bot)}</td>
                  <td>
                    <span className={`vital-tone ${toneForLifecycle(life)}`}>{life}</span>
                  </td>
                  <td>{bot.aws_runtime_id || "UNREAD"}</td>
                  <td>{bot.engine_pointer || bot.iti_lineage || "—"}</td>
                </tr>
              );
            })
          )}
        </tbody>
      </table>
    </div>
  );
}
