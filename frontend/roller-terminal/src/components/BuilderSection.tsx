import type { ReactNode } from "react";

export default function BuilderSection({
  id,
  title,
  summary,
  open,
  onToggle,
  children,
}: {
  id: string;
  title: string;
  summary: string;
  open: boolean;
  onToggle: () => void;
  children: ReactNode;
}) {
  return (
    <section className={`builder-section ${open ? "open" : "closed"}`} data-section={id}>
      <button type="button" className="builder-section-head" onClick={onToggle}>
        <span className="builder-section-title">{title}</span>
        <span className="builder-section-summary muted">{summary}</span>
        <span className="builder-section-chevron">{open ? "▾" : "▸"}</span>
      </button>
      {open ? <div className="builder-section-body">{children}</div> : null}
    </section>
  );
}
