import { useState, type ComponentType } from 'react';
import { AlertTriangle, ChevronDown, CircleHelp, FileText, History, LayoutDashboard, LoaderCircle, Monitor, Plus, RefreshCw, Settings } from 'lucide-react';
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
    overview: LayoutDashboard,
    workspace: FileText,
    devices: Monitor,
    runs: History,
    config: Settings,
    settings: CircleHelp,
  };
  const Icon = icons[icon];
  return <Icon aria-hidden={true} />;
}

function workspaceInitials(label: string) {
  const words = label.trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) return '?';
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
  return words.slice(0, 2).map((word) => word[0]).join('').toUpperCase();
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
  const primary = navigation.filter((item) => item.section === 'primary');
  const workspaceIndex = primary.findIndex((item) => item.id === 'workspace');
  const workspaceNavigation = workspaceIndex >= 0 ? primary[workspaceIndex] : null;
  const beforeWorkspace = workspaceIndex >= 0 ? primary.slice(0, workspaceIndex) : primary;
  const afterWorkspace = workspaceIndex >= 0 ? primary.slice(workspaceIndex + 1) : [];
  return (
    <div className="cp-sidebar-inner">
      <div className="cp-brand"><span className="cp-mark">FSQ</span><span><strong>Control Plane</strong><small>Local automation workspace</small></span></div>
      <nav className="cp-primary-nav" aria-label="Primary navigation">
        <NavGroup items={beforeWorkspace} activePage={activePage} onNavigate={onNavigate} />
        {workspaceNavigation && <div className="cp-workspaces" aria-label="Workspaces">
          {workspaceNavigation.available ? <button
            className="cp-nav-item cp-workspaces-trigger"
            type="button"
            aria-current={activePage === workspaceNavigation.id && !selectedWorkspaceId ? 'page' : undefined}
            aria-expanded={workspacesExpanded}
            data-active={activePage === workspaceNavigation.id ? 'true' : undefined}
            onClick={() => {
              onNavigate?.(workspaceNavigation.id);
              setWorkspacesExpanded((expanded) => !expanded);
            }}
          >
            <NavigationGlyph icon={workspaceNavigation.icon} /><span>{workspaceNavigation.label}</span><ChevronDown className="cp-workspaces-chevron" aria-hidden="true" />
          </button> : <span className="cp-nav-item cp-nav-item--unavailable" aria-disabled="true"><NavigationGlyph icon={workspaceNavigation.icon} /><span>{workspaceNavigation.label}</span><small>Unavailable</small></span>}
          {workspaceNavigation.available && workspacesExpanded && <div className="cp-workspace-children">
            <button id="workspace-create-sidebar" className="cp-workspace cp-workspace--create" type="button" onClick={onCreateWorkspace}><Plus aria-hidden="true" /><span>Create workspace</span></button>
            {workspaces.map((workspace) => workspace.available === false ? (
              <span key={workspace.id} className="cp-workspace cp-workspace--unavailable" aria-disabled="true" title={workspace.message}>
                <AlertTriangle aria-hidden="true" /><span><strong>{workspace.label}</strong>{workspace.description && <small>{workspace.description}</small>}</span>
              </span>
            ) : (
              <button key={workspace.id} className="cp-workspace" type="button" aria-current={workspace.id === selectedWorkspaceId ? 'page' : undefined} onClick={() => onSelectWorkspace?.(workspace.id)}>
                <span className="cp-project-glyph" aria-hidden="true">{workspaceInitials(workspace.label)}</span><span><strong>{workspace.label}</strong>{workspace.description && <small>{workspace.description}</small>}</span>
              </button>
            ))}
            {workspaceRegistryStatus === 'loading' && <span className="cp-workspaces-empty"><LoaderCircle aria-hidden="true" />Loading workspaces…</span>}
            {workspaceRegistryStatus === 'error' && <span className="cp-workspaces-empty cp-workspaces-error"><AlertTriangle aria-hidden="true" /><span>{workspaceRegistryError || 'Workspace registry unavailable.'}</span><button className="cp-workspace-retry" type="button" aria-label="Retry workspace registry" onClick={onRetryWorkspaces}><RefreshCw aria-hidden="true" /></button></span>}
            {workspaceRegistryStatus === 'ready' && workspaces.length === 0 && <span className="cp-workspaces-empty"><CircleHelp aria-hidden="true" />No registered workspaces</span>}
          </div>}
        </div>}
        <NavGroup items={afterWorkspace} activePage={activePage} onNavigate={onNavigate} />
      </nav>
      <nav className="cp-footer-nav" aria-label="Configuration navigation">
        <NavGroup items={navigation.filter((item) => item.section === 'footer')} activePage={activePage} onNavigate={onNavigate} />
      </nav>
    </div>
  );
}
