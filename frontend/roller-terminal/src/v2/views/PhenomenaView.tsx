import { useMemo, useState } from "react";
import { PHENOMENA, type Phenomenon } from "../phenomenaCatalog";

type Props = {
  onOpenTemplate: (templateId: string) => void;
};

export default function PhenomenaView({ onOpenTemplate }: Props) {
  const [selected, setSelected] = useState<Phenomenon | null>(PHENOMENA[0] ?? null);
  const groups = useMemo(() => {
    const map = new Map<string, Phenomenon[]>();
    for (const p of PHENOMENA) {
      const list = map.get(p.group) ?? [];
      list.push(p);
      map.set(p.group, list);
    }
    return [...map.entries()];
  }, []);

  return (
    <div className="v2-phenomena">
      <header className="v2-view-header">
        <h1 className="v2-page-title">Phenomena</h1>
        <p className="v2-lede">
          Concept catalog — separate from runnable research objects. Constructibility is honest.
        </p>
      </header>
      <div className="v2-phenomena-layout">
        <div className="v2-phenomena-tree">
          {groups.map(([group, items]) => (
            <div key={group} className="v2-phenomena-group">
              <div className="v2-kicker">{group}</div>
              {items.map((p) => (
                <button
                  key={p.id}
                  type="button"
                  className={selected?.id === p.id ? "v2-dict-row on" : "v2-dict-row"}
                  onClick={() => setSelected(p)}
                >
                  {p.name}
                </button>
              ))}
            </div>
          ))}
        </div>
        {selected ? (
          <article className="research-object v2-phenomena-detail">
            <h2>{selected.name}</h2>
            <p>{selected.plainEnglish}</p>
            <h3>Formal definition</h3>
            <p className="evidence">{selected.formalDefinition}</p>
            <h3>Available fields</h3>
            <p className="evidence">
              {selected.availableFields.length
                ? selected.availableFields.join(" · ")
                : "None declared"}
            </p>
            <h3>Compatible populations</h3>
            <p className="evidence">
              {selected.compatiblePopulations.length
                ? selected.compatiblePopulations.join(" · ")
                : "—"}
            </p>
            <h3>Known templates</h3>
            <div className="v2-home-links">
              {selected.knownTemplates.map((tid) => (
                <button
                  key={tid}
                  type="button"
                  className="v2-text-link"
                  onClick={() => onOpenTemplate(tid)}
                >
                  {tid} →
                </button>
              ))}
            </div>
            <h3>Constructibility</h3>
            <p className="evidence">{selected.constructibility}</p>
          </article>
        ) : null}
      </div>
    </div>
  );
}
