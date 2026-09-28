import type { CatalogTemplate } from "../templateCatalog";

type Props = {
  template: CatalogTemplate;
  onUse: (template: CatalogTemplate) => void;
  onInspect?: (template: CatalogTemplate) => void;
};

function actionLabel(t: CatalogTemplate): string {
  if (t.usability === "IMPLEMENTED" && t.runnable) return "Use · runnable";
  if (t.usability === "CONFIGURABLE") return "Load as starting point";
  return "Inspect only";
}

export default function TemplateCard({ template, onUse, onInspect }: Props) {
  const inspectOnly = template.usability === "REGISTERED";
  return (
    <article className={`v2-template-card usability-${template.usability.toLowerCase()}`}>
      <div className="v2-template-card-top">
        <h3>{template.name}</h3>
        <span
          className={`v2-badge ${
            template.usability === "IMPLEMENTED" ? "ok" : template.usability === "CONFIGURABLE" ? "warn" : ""
          }`}
        >
          {template.sport} · {template.usability}
        </span>
      </div>
      <p>{template.description}</p>
      {template.measurements.length ? (
        <div className="v2-template-measures">
          <span className="v2-kicker">Measurements</span>
          <div className="evidence">{template.measurements.join(" · ")}</div>
        </div>
      ) : (
        <div className="muted small">No measurement requests declared.</div>
      )}
      {template.usability !== "IMPLEMENTED" ? (
        <p className="v2-template-warn muted">
          {template.notes ??
            (template.usability === "REGISTERED"
              ? "REGISTERED — not constructible as an executable route."
              : "CONFIGURABLE starting point — not a finished empirical claim.")}
        </p>
      ) : null}
      <div className="v2-template-actions">
        {inspectOnly ? (
          <button
            type="button"
            className="btn-secondary"
            onClick={() => (onInspect ? onInspect(template) : onUse(template))}
          >
            Inspect only
          </button>
        ) : (
          <button type="button" className="btn-primary" onClick={() => onUse(template)}>
            {actionLabel(template)}
          </button>
        )}
        {onInspect && !inspectOnly ? (
          <button type="button" className="v2-text-link" onClick={() => onInspect(template)}>
            Details
          </button>
        ) : null}
      </div>
    </article>
  );
}
