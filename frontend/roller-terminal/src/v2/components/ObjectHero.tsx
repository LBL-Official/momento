import type { ReactNode } from "react";

type Props = {
  title: string;
  subtitle?: string;
  meta?: string[];
  badges?: { label: string; tone?: "ok" | "warn" | "neutral" }[];
  actions?: ReactNode;
};

export default function ObjectHero({ title, subtitle, meta, badges, actions }: Props) {
  return (
    <header className="v2-object-hero">
      <div className="v2-object-hero-main">
        <h1 className="v2-page-title">{title}</h1>
        {subtitle ? <p className="v2-object-subtitle">{subtitle}</p> : null}
        {meta?.length ? (
          <div className="v2-object-meta">
            {meta.map((m) => (
              <span key={m} className="evidence">
                {m}
              </span>
            ))}
          </div>
        ) : null}
        {badges?.length ? (
          <div className="v2-badge-row">
            {badges.map((b) => (
              <span key={b.label} className={`v2-badge ${b.tone ?? "neutral"}`}>
                {b.label}
              </span>
            ))}
          </div>
        ) : null}
      </div>
      {actions ? <div className="v2-object-hero-actions">{actions}</div> : null}
    </header>
  );
}
