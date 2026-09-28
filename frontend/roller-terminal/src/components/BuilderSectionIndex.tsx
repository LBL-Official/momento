import { useEffect, useState } from "react";

const SECTIONS: { id: string; label: string }[] = [
  { id: "A", label: "A IDENTITY" },
  { id: "B", label: "B POPULATION" },
  { id: "C", label: "C ANCHOR" },
  { id: "D", label: "D INFORMATION" },
  { id: "E", label: "E STATE" },
  { id: "F", label: "F PATH" },
  { id: "G", label: "G TERMINAL" },
  { id: "H", label: "H MEASUREMENTS" },
  { id: "I", label: "I BINDINGS" },
];

/** Navigation only — not a wizard; does not encode research dependencies. */
export default function BuilderSectionIndex({
  onEnsureOpen,
}: {
  onEnsureOpen?: (id: string) => void;
}) {
  const [active, setActive] = useState("A");

  useEffect(() => {
    const nodes = SECTIONS.map((s) => document.querySelector(`[data-section="${s.id}"]`)).filter(
      Boolean,
    ) as Element[];
    if (!nodes.length) return;

    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        if (visible[0]?.target) {
          const id = (visible[0].target as HTMLElement).dataset.section;
          if (id) setActive(id);
        }
      },
      { rootMargin: "-20% 0px -55% 0px", threshold: [0, 0.25, 0.5] },
    );
    nodes.forEach((n) => observer.observe(n));
    return () => observer.disconnect();
  }, []);

  const scrollTo = (id: string) => {
    onEnsureOpen?.(id);
    // Allow expand before scroll
    requestAnimationFrame(() => {
      const el = document.querySelector(`[data-section="${id}"]`);
      el?.scrollIntoView({ behavior: "smooth", block: "start" });
      setActive(id);
    });
  };

  return (
    <nav className="section-index" aria-label="Builder sections">
      {SECTIONS.map((s) => (
        <button
          key={s.id}
          type="button"
          className={active === s.id ? "section-index-item on" : "section-index-item"}
          onClick={() => scrollTo(s.id)}
        >
          {s.label}
        </button>
      ))}
    </nav>
  );
}
