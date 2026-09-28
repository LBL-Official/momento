import SuperasiBResults from "./SuperasiBResults";
import type { SuperasiDebaseInspect } from "./types/superasi";

type Props = {
  inspect: SuperasiDebaseInspect | null;
  busy?: boolean;
  onOpenFinal: () => void;
};

export default function DebaseRun({ inspect, busy, onOpenFinal }: Props) {
  if (busy) {
    return (
      <div className="sa-page">
        <h1 className="v2-page-title">SuperASI B — Debase</h1>
        <p className="v2-lede">Ingesting Roller + SuperasiABase and writing SuperasiBDeBase.</p>
      </div>
    );
  }
  if (!inspect) {
    return (
      <div className="sa-page">
        <h1 className="v2-page-title">SuperASI B — Debase</h1>
        <p className="v2-lede">
          Select a Phase A folder and run SuperASI B — Debase. Strategy EV and R:R come from the Roller header, not the
          +20/−40 desk instrument.
        </p>
      </div>
    );
  }
  return (
    <div className="sa-page">
      <SuperasiBResults inspect={inspect} />
      <button type="button" className="btn-secondary" onClick={onOpenFinal}>
        Open SuperASI Final Results
      </button>
    </div>
  );
}
