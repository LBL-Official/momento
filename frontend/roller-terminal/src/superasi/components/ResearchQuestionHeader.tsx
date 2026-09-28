import { packageHash, packageQuestion, packageTitle } from "../packagePresentation";
import type { Decomp, LibraryItem, PackageIdentity } from "../types/superasi";

type Props = {
  pkg?: PackageIdentity | LibraryItem | null;
  decomp?: Decomp | null;
};

export default function ResearchQuestionHeader({ pkg, decomp }: Props) {
  if (!pkg) return null;
  const title = packageTitle(pkg);
  const hash = packageHash(pkg, decomp);
  const question = packageQuestion(pkg);
  return (
    <section className="sa-research-head" aria-label="ROLLER research question">
      <h2 className="sa-research-title">{title}</h2>
      <p className="sa-research-hash evidence mono">{hash || "—"}</p>
      {question ? (
        <p className="ws-question-hero sa-research-question">{question}</p>
      ) : (
        <p className="muted small">
          ROLLER research question unavailable — this package has no stored draft.
        </p>
      )}
    </section>
  );
}
