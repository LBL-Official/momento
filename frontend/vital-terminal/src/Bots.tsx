import { useMemo, useState } from "react";
import BotBlotter from "./BotBlotter";
import type { VitalBot } from "./api/vitalApi";
import { filterBots, sportLabel } from "./desk";

type Props = {
  bots: VitalBot[];
  error: string | null;
  selectedId?: string;
  onOpenDetail: (botId: string) => void;
};

export default function Bots({ bots, error, selectedId, onOpenDetail }: Props) {
  const [sport, setSport] = useState("all");
  const [environment, setEnvironment] = useState("all");
  const sports = useMemo(() => {
    const found = new Set<string>();
    for (const bot of bots) {
      const value = sportLabel(bot).toLowerCase();
      if (value && value !== "—") found.add(value);
    }
    return ["all", ...Array.from(found).sort()];
  }, [bots]);
  const rows = filterBots(bots, sport, environment);
  return (
    <div className="sa-page vital-desk">
      <header className="vital-desk-head">
        <div>
          <p className="ws-kicker">Bots</p>
          <h1 className="v2-page-title">Units</h1>
        </div>
        <p className="muted small">
          MLB 001 pinned. Isolated ITI units sort RUNNING, RUNNING_DEMO, then DEPLOY_REQUIRED.
        </p>
      </header>
      {error ? <p className="sa-error">{error}</p> : null}
      <div className="vital-toolbar">
        <label>
          Sport
          <select value={sport} onChange={(event) => setSport(event.target.value)}>
            {sports.map((item) => (
              <option key={item} value={item}>
                {item === "all" ? "All sports" : item.toUpperCase()}
              </option>
            ))}
          </select>
        </label>
        <label>
          Book
          <select value={environment} onChange={(event) => setEnvironment(event.target.value)}>
            <option value="all">All books</option>
            <option value="PRODUCTION">PRODUCTION</option>
            <option value="DEMO">DEMO</option>
          </select>
        </label>
        <p className="muted small">{rows.length} shown</p>
      </div>
      <BotBlotter bots={rows} selectedId={selectedId} onOpen={onOpenDetail} />
    </div>
  );
}
