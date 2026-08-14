import { useState, type ComponentType } from 'react';
import { AlertTriangle, ChevronDown, CircleHelp, Clock3, FilePlus2, FolderKanban, Gauge, LoaderCircle, Monitor, RefreshCw, Settings, SlidersHorizontal } from 'lucide-react';
import type { ControlPlanePageId, NavigationIcon, NavigationItem, WorkspaceNavigationItem } from './navigation';

interface ControlPlaneSidebarProps {
  activePage: ControlPlanePageId;
  navigation: readonly NavigationItem[];
  workspaces?: readonly WorkspaceNavigationItem[];
  selectedWorkspaceId?: string | null;
  workspaceRegistryStatus?: 'loading' | 'ready' | 'error';
  workspaceRegistryError?: string;
  onNavigate?: (page: ControlPlanePageId) => void;
  onRetryWorkspaces?: () => void;
  onCreateWorkspace?: () => void;
  onSelectWorkspace?: (workspaceId: string) => void;
}

function NavigationGlyph({ icon }: { icon: NavigationIcon }) {
  const icons: Record<NavigationIcon, ComponentType<{ 'aria-hidden': true }>> = {
    overview: Gauge,
    workspace: FolderKanban,
    devices: Monitor,
    runs: Clock3,
    config: SlidersHorizontal,
    settings: Settings,
  };
  const Icon = icons[icon];
  return <Icon aria-hidden={true} />;
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

export function ControlPlaneSidebar({ activePage, navigation, workspaces = [], selectedWorkspaceId, workspaceRegistryStatus = 'ready', workspaceRegistryError, onNavigate, onRetryWorkspaces, onCreateWorkspace, onSelectWorkspace }: ControlPlaneSidebarProps) {
  const [workspacesExpanded, setWorkspacesExpanded] = useState(true);
  const primary = navigation.filter((item) => item.section === 'primary' && item.id !== 'workspace');
  return (
    <div className="cp-sidebar-inner">
      <div className="cp-brand"><span className="cp-mark">FSQ</span><span><strong>Control Plane</strong><small>Local automation workspace</small></span></div>
      <nav className="cp-primary-nav" aria-label="Primary navigation">
        <NavGroup items={primary} activePage={activePage} onNavigate={onNavigate} />
        <div className="cp-workspaces" aria-label="Workspaces">
          <div className="cp-workspaces-heading">
            <button className="cp-nav-item cp-workspaces-link" type="button" aria-current={activePage === 'workspace' && !selectedWorkspaceId ? 'page' : undefined} onClick={() => onNavigate?.('workspace')}>
              <NavigationGlyph icon="workspace" /><span>Workspace</span>
            </button>
            <button className="cp-workspaces-toggle" type="button" aria-label={`${workspacesExpanded ? 'Collapse' : 'Expand'} workspaces`} aria-expanded={workspacesExpanded} onClick={() => setWorkspacesExpanded((expanded) => !expanded)}>
              <ChevronDown aria-hidden="true" />
            </button>
          </div>
          {workspacesExpanded && <div className="cp-workspace-children">
            <button id="workspace-create-sidebar" className="cp-workspace cp-workspace--create" type="button" onClick={onCreateWorkspace}><FilePlus2 aria-hidden="true" /><span>Create workspace</span></button>
            {workspaces.map((workspace) => workspace.available === false ? (
              <span key={workspace.id} className="cp-workspace cp-workspace--unavailable" aria-disabled="true" title={workspace.message}>
                <AlertTriangle aria-hidden="true" /><span><strong>{workspace.label}</strong>{workspace.description && <small>{workspace.description}</small>}</span>
              </span>
            ) : (
              <button key={workspace.id} className="cp-workspace" type="button" aria-current={workspace.id === selectedWorkspaceId ? 'page' : undefined} onClick={() => onSelectWorkspace?.(workspace.id)}>
                <FolderKanban aria-hidden="true" /><span><strong>{workspace.label}</strong>{workspace.description && <small>{workspace.description}</small>}</span>
              </button>
            ))}
            {workspaceRegistryStatus === 'loading' && <span className="cp-workspaces-empty"><LoaderCircle aria-hidden="true" />Loading workspaces…</span>}
            {workspaceRegistryStatus === 'error' && <span className="cp-workspaces-empty cp-workspaces-error"><AlertTriangle aria-hidden="true" /><span>{workspaceRegistryError || 'Workspace registry unavailable.'}</span><button className="cp-workspace-retry" type="button" aria-label="Retry workspace registry" onClick={onRetryWorkspaces}><RefreshCw aria-hidden="true" /></button></span>}
            {workspaceRegistryStatus === 'ready' && workspaces.length === 0 && <span className="cp-workspaces-empty"><CircleHelp aria-hidden="true" />No registered workspaces</span>}
          </div>}
        </div>
      </nav>
      <nav className="cp-footer-nav" aria-label="Configuration navigation">
        <NavGroup items={navigation.filter((item) => item.section === 'footer')} activePage={activePage} onNavigate={onNavigate} />
      </nav>
    </div>
  );
}
