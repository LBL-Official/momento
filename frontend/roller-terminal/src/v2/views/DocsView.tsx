import { useMemo, useState } from "react";
import { DOC_PAGES, type DocPage } from "../docsContent";

type Props = {
  initialId?: string;
};

export default function DocsView({ initialId }: Props) {
  const [id, setId] = useState(initialId ?? "getting-started");
  const page: DocPage | undefined = useMemo(
    () => DOC_PAGES.find((p) => p.id === id) ?? DOC_PAGES[0],
    [id],
  );

  if (!page) return null;

  return (
    <div className="v2-docs">
      <aside className="v2-docs-nav">
        <h1 className="v2-section-title">Docs</h1>
        <ul>
          {DOC_PAGES.map((p) => (
            <li key={p.id}>
              <button
                type="button"
                className={p.id === page.id ? "v2-nav-item on" : "v2-nav-item"}
                onClick={() => setId(p.id)}
              >
                {p.title}
              </button>
            </li>
          ))}
        </ul>
      </aside>
      <article className="v2-docs-article research-object">
        <h1 className="v2-page-title">{page.title}</h1>
        <p className="v2-lede">{page.summary}</p>
        <h2>What is this?</h2>
        <p>{page.what}</p>
        <h2>Why does it exist?</h2>
        <p>{page.why}</p>
        <h2>What can I do here?</h2>
        <ul>
          {page.can.map((x) => (
            <li key={x}>{x}</li>
          ))}
        </ul>
        <h2>What can I not do here?</h2>
        <ul>
          {page.cannot.map((x) => (
            <li key={x}>{x}</li>
          ))}
        </ul>
        <h2>Example</h2>
        <p className="evidence">{page.example}</p>
        {page.repoPath ? (
          <p className="muted">
            Source: <span className="evidence">{page.repoPath}</span>
          </p>
        ) : null}
      </article>
    </div>
  );
}
