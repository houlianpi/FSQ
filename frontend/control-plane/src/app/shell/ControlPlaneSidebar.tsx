import type { ControlPlanePageId, NavigationIcon, NavigationItem, WorkspaceNavigationItem } from './navigation';

interface ControlPlaneSidebarProps {
  activePage: ControlPlanePageId;
  navigation: readonly NavigationItem[];
  workspaces?: readonly WorkspaceNavigationItem[];
  onNavigate?: (page: ControlPlanePageId) => void;
}

function NavigationGlyph({ icon }: { icon: NavigationIcon }) {
  const paths: Record<NavigationIcon, React.ReactNode> = {
    overview: <><path d="M4 13h6V4H4zM14 20h6v-9h-6zM4 20h6v-3H4zM14 7h6V4h-6z" /></>,
    workspace: <><path d="M6 3h9l4 4v14H6z" /><path d="M15 3v5h4M9 12h7M9 16h7" /></>,
    devices: <><rect x="3" y="4" width="18" height="13" rx="1" /><path d="M8 21h8M12 17v4" /></>,
    runs: <><path d="M12 8v5l3 2" /><path d="M21 12a9 9 0 1 1-3.2-6.9M21 4v5h-5" /></>,
    config: <><circle cx="12" cy="12" r="3" /><path d="M19 12a7 7 0 0 0-.1-1l2-1.5-2-3.4-2.4 1A7 7 0 0 0 15 6l-.3-2.6h-4L10.4 6A7 7 0 0 0 9 7.1l-2.5-1-2 3.4 2.1 1.5a7 7 0 0 0 0 2L4.5 14.5l2 3.4 2.5-1A7 7 0 0 0 10.4 18l.3 2.6h4L15 18a7 7 0 0 0 1.5-1.1l2.4 1 2-3.4-2-1.5a7 7 0 0 0 .1-1z" /></>,
    settings: <><path d="M12 18h.01M9.1 9a3 3 0 1 1 5.6 1.5c-.9 1.1-2.7 1.5-2.7 3" /><circle cx="12" cy="12" r="9" /></>,
  };
  return <svg aria-hidden="true" viewBox="0 0 24 24">{paths[icon]}</svg>;
}

function NavGroup({ items, activePage, onNavigate }: Pick<ControlPlaneSidebarProps, 'activePage' | 'onNavigate'> & { items: readonly NavigationItem[] }) {
  return items.map((item) => item.available ? (
    <button
      key={item.id}
      className="cp-nav-item"
      type="button"
      aria-current={item.id === activePage ? 'page' : undefined}
      onClick={() => onNavigate?.(item.id)}
    >
      <NavigationGlyph icon={item.icon} /><span>{item.label}</span>
    </button>
  ) : (
    <span key={item.id} className="cp-nav-item cp-nav-item--unavailable" aria-disabled="true">
      <NavigationGlyph icon={item.icon} /><span>{item.label}</span><small>Unavailable</small>
    </span>
  ));
}

export function ControlPlaneSidebar({ activePage, navigation, workspaces = [], onNavigate }: ControlPlaneSidebarProps) {
  return (
    <div className="cp-sidebar-inner">
      <div className="cp-brand"><span className="cp-mark">FSQ</span><span><strong>Control Plane</strong><small>Local automation workspace</small></span></div>
      <nav className="cp-primary-nav" aria-label="Primary navigation">
        <NavGroup items={navigation.filter((item) => item.section === 'primary')} activePage={activePage} onNavigate={onNavigate} />
        {workspaces.length > 0 && <div className="cp-workspaces" aria-label="Workspaces">
          <p>Workspaces</p>
          {workspaces.map((workspace) => <span key={workspace.id} className="cp-workspace" aria-disabled={workspace.available === false}>
            <strong>{workspace.label}</strong>{workspace.description && <small>{workspace.description}</small>}
          </span>)}
        </div>}
      </nav>
      <nav className="cp-footer-nav" aria-label="Configuration navigation">
        <NavGroup items={navigation.filter((item) => item.section === 'footer')} activePage={activePage} onNavigate={onNavigate} />
      </nav>
    </div>
  );
}
