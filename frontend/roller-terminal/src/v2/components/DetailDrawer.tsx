import { useEffect, type ReactNode } from "react";

export type InspectionContainment = {
  parentLabel: string;
  parentN: number | null;
  currentLabel: string;
  currentN: number | null;
};

export type DetailPayload = {
  title: string;
  subtitle?: string;
  value?: string;
  containment?: InspectionContainment;
  sections: { heading: string; body: ReactNode }[];
};

type Props = {
  detail: DetailPayload | null;
  onClose: () => void;
};

export default function DetailDrawer({ detail, onClose }: Props) {
  useEffect(() => {
    if (!detail) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [detail, onClose]);

  if (!detail) return null;
  return (
    <aside className="v2-detail-drawer" aria-label="Detail">
      <div className="v2-detail-head">
        <div>
          <div className="v2-detail-kicker">Detail</div>
          <h2 className="v2-detail-title">{detail.title}</h2>
          {detail.subtitle ? <p className="muted">{detail.subtitle}</p> : null}
        </div>
        <button type="button" className="btn-secondary" onClick={onClose}>
          Close
        </button>
      </div>
      {detail.containment ? (
        <div className="v2-detail-containment">
          <div>
            <div className="v2-kicker">Parent population</div>
            <p>
              {detail.containment.parentLabel}
              {detail.containment.parentN != null ? ` · N = ${detail.containment.parentN}` : ""}
            </p>
          </div>
          <div>
            <div className="v2-kicker">Current object</div>
            <p>
              {detail.containment.currentLabel}
              {detail.containment.currentN != null ? ` · n = ${detail.containment.currentN}` : ""}
            </p>
          </div>
        </div>
      ) : null}
      {detail.value ? (
        <div className="v2-detail-value evidence">{detail.value}</div>
      ) : null}
      {detail.sections.map((s) => (
        <section key={s.heading} className="v2-detail-section">
          <h3>{s.heading}</h3>
          <div className="v2-detail-body">{s.body}</div>
        </section>
      ))}
    </aside>
  );
}
