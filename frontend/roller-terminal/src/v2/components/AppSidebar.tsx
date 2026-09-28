import { NAV_ITEMS, type AppRoute } from "../navigation";

type Props = {
  route: AppRoute;
  collapsed: boolean;
  onNavigate: (route: AppRoute) => void;
  onToggleCollapse: () => void;
};

export default function AppSidebar({
  route,
  collapsed,
  onNavigate,
  onToggleCollapse,
}: Props) {
  return (
    <aside className={`v2-sidebar ${collapsed ? "collapsed" : ""}`} aria-label="ROLLER">
      <div className="v2-sidebar-brand">
        <img
          className="brand-mark"
          src="/brand/roller-mark-a3.png"
          alt=""
          width={28}
          height={28}
          decoding="async"
        />
        {!collapsed ? (
          <div className="v2-sidebar-brand-text">
            <div className="brand">ROLLER</div>
            <div className="sub">Research V2</div>
          </div>
        ) : null}
        <button
          type="button"
          className="v2-sidebar-collapse"
          onClick={onToggleCollapse}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? "»" : "«"}
        </button>
      </div>
      <nav className="v2-sidebar-nav">
        {NAV_ITEMS.map((item) => (
          <button
            key={item.id}
            type="button"
            className={route === item.id ? "v2-nav-item on" : "v2-nav-item"}
            onClick={() => onNavigate(item.id)}
            title={item.hint}
          >
            <span className="v2-nav-label">{item.label}</span>
            {!collapsed ? <span className="v2-nav-hint">{item.hint}</span> : null}
          </button>
        ))}
      </nav>
      {!collapsed ? (
        <div className="v2-sidebar-foot muted">
          Phase 0–6 · MEASUREMENT ≠ EDGE
        </div>
      ) : null}
    </aside>
  );
}
