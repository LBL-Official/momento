type Crumb = { artifact_id: string; name: string; href?: string };

type Props = {
  items: Crumb[];
  onOpen: (id: string) => void;
};

export default function Breadcrumbs({ items, onOpen }: Props) {
  return (
    <nav className="ju-drive-crumbs" aria-label="Breadcrumb">
      {items.map((crumb, idx) => (
        <span key={`${crumb.artifact_id}-${idx}`}>
          {idx > 0 ? <span className="ju-drive-crumb-sep">/</span> : null}
          <button type="button" onClick={() => onOpen(crumb.artifact_id)}>
            {crumb.name}
          </button>
        </span>
      ))}
    </nav>
  );
}
