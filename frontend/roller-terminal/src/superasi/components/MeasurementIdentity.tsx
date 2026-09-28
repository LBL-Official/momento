import { useState } from "react";
import { shortHash } from "../format";
import type { Decomp, LibraryItem, PackageIdentity } from "../types/superasi";

type Props = {
  pkg?: PackageIdentity | LibraryItem | null;
  decomp?: Decomp | null;
  compact?: boolean;
};

export default function MeasurementIdentity({ pkg, decomp, compact }: Props) {
  const questionHash = pkg && "question_hash" in pkg ? pkg.question_hash : null;
  const datasetVersion =
    (pkg && "dataset_version" in pkg ? pkg.dataset_version : null) ?? decomp?.dataset_version;
  const tradeOrigin = pkg && "trade_origin" in pkg ? pkg.trade_origin : null;
  const tradesChecksum = decomp?.checksums?.trades;
  if (compact) {
    return (
      <div className="muted small sa-identity">
        ROLLER {shortHash(questionHash)}
        {datasetVersion ? ` · ds ${shortHash(datasetVersion, 8)}` : ""}
        {tradeOrigin ? ` · ${tradeOrigin}` : ""}
      </div>
    );
  }
  return (
    <section className="sa-identity" aria-label="ROLLER measurement identity">
      <p className="ws-kicker">ROLLER measurement identity — not SuperASI edge</p>
      <div className="stax-metric-row">
        <div>
          <div className="muted small">question_hash</div>
          <div className="evidence mono">
            {shortHash(questionHash)}
            <CopyHash value={questionHash} />
          </div>
        </div>
        <div>
          <div className="muted small">dataset_version</div>
          <div className="mono">{shortHash(datasetVersion)}</div>
        </div>
        <div>
          <div className="muted small">trade_origin</div>
          <div>{tradeOrigin || "—"}</div>
        </div>
        {tradesChecksum ? (
          <div>
            <div className="muted small">checksums.trades</div>
            <div className="mono">{shortHash(tradesChecksum)}</div>
          </div>
        ) : null}
      </div>
    </section>
  );
}

function CopyHash({ value }: { value?: string | null }) {
  const [copied, setCopied] = useState(false);
  if (!value) return null;
  return (
    <button
      type="button"
      className="v2-text-link sa-copy"
      onClick={(event) => {
        event.stopPropagation();
        void navigator.clipboard.writeText(value).then(() => {
          setCopied(true);
          window.setTimeout(() => setCopied(false), 1200);
        });
      }}
    >
      {copied ? "Copied" : "Copy"}
    </button>
  );
}
