import { useMemo, useState } from "react";
import TemplateCard from "../components/TemplateCard";
import {
  TEMPLATE_CATALOG,
  catalogStats,
  mergeBackendTemplates,
  type CatalogTemplate,
} from "../templateCatalog";

type Props = {
  backendTemplateIds: string[];
  onUse: (template: CatalogTemplate) => void;
  onInspect?: (template: CatalogTemplate) => void;
};

export default function TemplatesView({ backendTemplateIds, onUse, onInspect }: Props) {
  const [sport, setSport] = useState<string>("ALL");
  const [category, setCategory] = useState<string>("ALL");
  const [usability, setUsability] = useState<string>("ALL");
  const [q, setQ] = useState("");

  const catalog = useMemo(
    () => mergeBackendTemplates(TEMPLATE_CATALOG, new Set(backendTemplateIds)),
    [backendTemplateIds],
  );
  const stats = catalogStats(catalog);

  const filtered = useMemo(() => {
    return catalog.filter((t) => {
      if (sport !== "ALL" && t.sport !== sport) return false;
      if (category !== "ALL" && t.category !== category) return false;
      if (usability !== "ALL" && t.usability !== usability) return false;
      if (q.trim()) {
        const hay = `${t.name} ${t.id} ${t.description} ${t.category} ${t.usability}`.toLowerCase();
        if (!hay.includes(q.trim().toLowerCase())) return false;
      }
      return true;
    });
  }, [catalog, sport, category, usability, q]);

  return (
    <div className="v2-templates">
      <header className="v2-view-header">
        <h1 className="v2-page-title">Templates</h1>
        <p className="v2-lede">
          Honest catalog. <strong>IMPLEMENTED</strong> templates are runnable after validate.
          <strong> CONFIGURABLE</strong> are starting points. <strong>REGISTERED</strong> are
          not constructible routes.
        </p>
        <p className="evidence">
          TOTAL {stats.total} · IMPLEMENTED {stats.implemented} · CONFIGURABLE {stats.configurable} ·
          REGISTERED {stats.registered} · RUNNABLE {stats.runnable}
        </p>
      </header>

      <div className="v2-filter-row">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search templates…"
          aria-label="Search templates"
        />
        <select value={sport} onChange={(e) => setSport(e.target.value)} aria-label="Sport">
          <option value="ALL">All sports</option>
          <option value="NBA">NBA</option>
          <option value="NCAAB">NCAAB</option>
          <option value="WNBA">WNBA</option>
          <option value="MLB">MLB</option>
          <option value="MULTI">MULTI</option>
        </select>
        <select
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          aria-label="Category"
        >
          <option value="ALL">All categories</option>
          <option value="PRICE TOUCH">Price touch</option>
          <option value="PATH">Path</option>
          <option value="TERMINAL">Terminal</option>
          <option value="TIME">Time</option>
          <option value="GAME STATE">Game state</option>
          <option value="INFORMATION">Information</option>
          <option value="BASIS">Basis</option>
          <option value="VOLATILITY">Volatility</option>
        </select>
        <select
          value={usability}
          onChange={(e) => setUsability(e.target.value)}
          aria-label="Usability"
        >
          <option value="ALL">All usability</option>
          <option value="IMPLEMENTED">Implemented</option>
          <option value="CONFIGURABLE">Configurable</option>
          <option value="REGISTERED">Registered</option>
        </select>
      </div>

      <div className="v2-template-grid">
        {filtered.map((t) => (
          <TemplateCard key={t.id} template={t} onUse={onUse} onInspect={onInspect} />
        ))}
      </div>
    </div>
  );
}
