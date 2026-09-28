import PackageLedger from "./PackageLedger";
import type { LibraryItem } from "./types/superasi";

type Props = {
  packages: LibraryItem[];
  activeId?: string | null;
  onOpen: (id: string) => void;
};

export default function Labs({ packages, activeId, onOpen }: Props) {
  return (
    <div className="sa-page">
      <header className="stax-count-head">
        <p className="ws-kicker">SuperASI library</p>
        <h2 className="stax-count">{String(packages.length).padStart(2, "0")} PACKAGES</h2>
        <p className="muted small">
          Disk packages under research/superasi/library. Not Strategies. Invalid packages fail
          closed — no silent repair.
        </p>
      </header>
      <PackageLedger packages={packages} activeId={activeId} onOpen={onOpen} />
    </div>
  );
}
