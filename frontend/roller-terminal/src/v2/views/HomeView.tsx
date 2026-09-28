import type { CatalogTemplate } from "../templateCatalog";
import type { LibraryEntry } from "../researchLibrary";
import type { Freshness } from "../../researchFreshness";

type Props = {
  library: LibraryEntry[];
  validationFreshness: Freshness;
  executionFreshness: Freshness;
  populationN: number | null;
  objectName: string;
  onContinueResearch: () => void;
  onOpenTemplates: () => void;
  onOpenExplore: () => void;
  onOpenLibrary: () => void;
  onUseTemplateId: (id: string) => void;
  implementedTemplates: CatalogTemplate[];
};

function greeting(): string {
  const h = new Date().getHours();
  if (h < 12) return "Good morning";
  if (h < 18) return "Good afternoon";
  return "Good evening";
}

export default function HomeView({
  library,
  validationFreshness,
  executionFreshness,
  populationN,
  objectName,
  onContinueResearch,
  onOpenTemplates,
  onOpenExplore,
  onOpenLibrary,
  onUseTemplateId,
  implementedTemplates,
}: Props) {
  return (
    <div className="v2-home">
      <header className="v2-home-hero">
        <p className="v2-kicker">{greeting()}</p>
        <h1 className="v2-page-title">Research System</h1>
        <p className="v2-lede">Phase 0–6 operational. Discover → define → measure → inspect.</p>
      </header>

      <section className="v2-home-section">
        <h2>Continue research</h2>
        <div className="v2-home-cards">
          <button type="button" className="v2-home-card" onClick={onContinueResearch}>
            <div className="v2-home-card-title">{objectName || "Current object"}</div>
            <div className="muted">
              Validation {validationFreshness}
              {executionFreshness !== "NONE" ? ` · Last execution ${executionFreshness}` : ""}
            </div>
            {populationN != null ? (
              <div className="evidence">Last result: n = {populationN}</div>
            ) : (
              <div className="muted">No empirical result yet</div>
            )}
          </button>
          {implementedTemplates.map((t) => (
            <button
              key={t.id}
              type="button"
              className="v2-home-card"
              onClick={() => onUseTemplateId(t.id)}
            >
              <div className="v2-home-card-title">{t.name}</div>
              <div className="muted">
                {t.sport} · {t.status}
              </div>
              <div className="evidence">
                {t.id === "FIRST80_Q3"
                  ? "Locked expectation n = 290"
                  : t.id === "NCAAB_FIRST80_P5"
                    ? "Locked expectation n = 721"
                    : t.measurements.join(" · ") || "Open template"}
              </div>
            </button>
          ))}
        </div>
      </section>

      <section className="v2-home-section">
        <h2>Start something new</h2>
        <div className="v2-home-links">
          <button type="button" className="v2-text-link" onClick={onOpenTemplates}>
            Browse templates →
          </button>
          <button type="button" className="v2-text-link" onClick={onOpenExplore}>
            Explore point-in-time data →
          </button>
          <button type="button" className="v2-text-link" onClick={onOpenLibrary}>
            Open research library →
          </button>
        </div>
        {!library.length ? (
          <p className="muted v2-home-empty">
            No saved research objects yet. Start with a template →
          </p>
        ) : (
          <p className="muted">
            {library.length} locally saved object{library.length === 1 ? "" : "s"} (UI library only —
            not authoritative warehouse artifacts).
          </p>
        )}
      </section>
    </div>
  );
}
