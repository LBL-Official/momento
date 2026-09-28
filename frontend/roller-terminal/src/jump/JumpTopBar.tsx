import type { FormEvent } from "react";
import Breadcrumbs from "./Breadcrumbs";

type Crumb = { artifact_id: string; name: string };

type Props = {
  crumbs: Crumb[];
  query: string;
  onQuery: (value: string) => void;
  onSearch: (event: FormEvent) => void;
  onOpenCrumb: (id: string) => void;
  onRefresh: () => void;
};

export default function JumpTopBar({ crumbs, query, onQuery, onSearch, onOpenCrumb, onRefresh }: Props) {
  return (
    <header className="ju-drive-bar">
      <div className="ju-drive-brand">Jump</div>
      <Breadcrumbs items={crumbs} onOpen={onOpenCrumb} />
      <form className="ju-drive-search" onSubmit={onSearch}>
        <input
          value={query}
          onChange={(event) => onQuery(event.target.value)}
          placeholder="Search names, sports, sources, documents"
          aria-label="Search Jump"
        />
      </form>
      <button type="button" className="ju-drive-quiet" onClick={onRefresh}>
        Refresh index
      </button>
    </header>
  );
}
