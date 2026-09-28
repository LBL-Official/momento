import PackageLedger from "./PackageLedger";
import type { LibraryItem } from "./types/superasi";

type Props = {
  importNote?: string | null;
  packageId?: string | null;
  packages: LibraryItem[];
  busy?: boolean;
  decompBusy?: boolean;
  error?: string | null;
  onSeed: () => void;
  onOpen: (id: string) => void;
  onGoLabs: () => void;
  onGoDecompose: () => void;
};

export default function QuickStart({
  importNote,
  packageId,
  packages,
  busy,
  decompBusy,
  error,
  onSeed,
  onOpen,
  onGoLabs,
  onGoDecompose,
}: Props) {
  return (
    <div className="sa-page">
      <section className="mm-identity sa-identity-plate" aria-label="Momento Systems SUPERASI Research Operating System">
        <img
          className="mm-identity-owl"
          src="/brand/momento-owl.png"
          alt="Momento Systems"
          decoding="async"
        />
        <p className="mm-identity-org">
          Momento Systems <span className="mm-identity-suffix">LLC</span>
        </p>
        <h1 className="mm-identity-product">Superasi</h1>
        <p className="mm-identity-role">Research Operating System</p>
        <p className="mm-identity-lede">ROLLER measures. SuperASI decomposes. Neither submits orders.</p>
      </section>

      {importNote ? (
        <section className="sa-import-banner" role="status">
          <p className="ws-kicker">MEASUREMENT IMPORTED</p>
          <p>{importNote}</p>
          {packageId ? <p className="evidence">{packageId}</p> : null}
          <button
            type="button"
            className="btn-primary"
            onClick={onGoDecompose}
            disabled={!packageId || decompBusy}
          >
            {decompBusy ? "Decomposing…" : "Decompose →"}
          </button>
        </section>
      ) : null}

      <section className="stax-strategies">
        <header className="stax-count-head">
          <p className="ws-kicker">Library</p>
          <h2 className="stax-count">{String(packages.length).padStart(2, "0")} PACKAGES</h2>
          <p className="muted small">
            Disk packages under research/superasi/library. Import from ROLLER Results or seed
            asked-six. SuperASI does not rescan a completed generic run.
          </p>
        </header>
        <PackageLedger packages={packages} activeId={packageId} onOpen={onOpen} />
        <div className="stax-toolbar stax-toolbar-stack">
          <button type="button" className="btn-primary" onClick={onSeed} disabled={busy}>
            {busy ? "Materializing…" : "Materialize asked-six"}
          </button>
          <button type="button" className="btn-secondary" onClick={onGoLabs}>
            Open Labs
          </button>
          <button
            type="button"
            className="btn-secondary"
            onClick={onGoDecompose}
            disabled={!packageId}
          >
            Decompose →
          </button>
        </div>
      </section>

      {error ? <p className="sa-error">{error}</p> : null}
    </div>
  );
}
