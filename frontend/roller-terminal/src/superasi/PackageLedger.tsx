import {
  packageHashShort,
  packageQuestion,
  packageStatus,
  packageTitle,
} from "./packagePresentation";
import type { LibraryItem } from "./types/superasi";

type Props = {
  packages: LibraryItem[];
  activeId?: string | null;
  onOpen: (id: string) => void;
};

export { packageLabel, packageStatus } from "./packagePresentation";

export default function PackageLedger({ packages, activeId, onOpen }: Props) {
  if (!packages.length) {
    return <p className="stax-empty muted">No packages yet.</p>;
  }
  return (
    <ol className="stax-ledger sa-ledger">
      {packages.map((item, i) => {
        const question = packageQuestion(item);
        return (
          <li key={item.package_id}>
            <button
              type="button"
              className={`stax-ledger-row sa-ledger-btn${item.package_id === activeId ? " on" : ""}`}
              onClick={() => onOpen(item.package_id)}
            >
              <span className="stax-ledger-index">{String(i + 1).padStart(2, "0")}</span>
              <span className="stax-ledger-name">
                <span className="sa-ledger-title">{packageTitle(item)}</span>
                <span className="sa-ledger-hash">{packageHashShort(item) || "—"}</span>
                {question ? <span className="sa-ledger-question">{question}</span> : null}
              </span>
              <span className="sa-ledger-n">N = {item.population_n ?? "—"}</span>
              <span className="stax-ledger-status">{packageStatus(item)}</span>
            </button>
          </li>
        );
      })}
    </ol>
  );
}
