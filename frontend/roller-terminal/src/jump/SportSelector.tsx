import type { SportInfo } from "./api/jumpApi";
import { sportLabel } from "./routing";

type Props = {
  sports: SportInfo[];
  current: string;
  onSelect: (sport: string) => void;
};

export default function SportSelector({ sports, current, onSelect }: Props) {
  return (
    <div className="ju-drive-sports">
      {sports.map((sport) => {
        const active = sport.id.toLowerCase() === current.toLowerCase();
        return (
          <button
            key={sport.id}
            type="button"
            className={active ? "is-active" : undefined}
            onClick={() => onSelect(sport.id.toLowerCase())}
          >
            <span>{sportLabel(sport.id)}</span>
            <span className="ju-drive-count">{sport.object_count}</span>
          </button>
        );
      })}
    </div>
  );
}
