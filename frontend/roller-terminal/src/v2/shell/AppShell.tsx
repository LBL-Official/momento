import type { ReactNode } from "react";

type Props = {
  sidebarCollapsed: boolean;
  onToggleSidebar: () => void;
  sidebar: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
};

/** Layout-only shell — header/nav live above this in App. */
export default function AppShell({
  sidebarCollapsed,
  onToggleSidebar,
  sidebar,
  children,
  footer,
}: Props) {
  return (
    <div className={`ws-body ${sidebarCollapsed ? "sidebar-collapsed" : ""}`}>
      {sidebar}
      <div className="ws-main-col">
        <button
          type="button"
          className="ws-sidebar-toggle"
          onClick={onToggleSidebar}
          aria-label={sidebarCollapsed ? "Expand research map" : "Collapse research map"}
        >
          {sidebarCollapsed ? "Show map" : "Hide map"}
        </button>
        <div className="ws-main-scroll">{children}</div>
        {footer}
      </div>
    </div>
  );
}
