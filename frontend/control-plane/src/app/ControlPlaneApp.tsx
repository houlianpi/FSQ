import { useEffect, useRef, useState } from 'react';
import { ControlPlaneShell } from './shell/ControlPlaneShell';
import type { ControlPlanePageId, WorkspaceNavigationItem } from './shell/navigation';
import { controlPlaneClient, toApiError } from '../api/controlPlaneClient';
import type { ApiErrorBody, WorkspaceRegistryEntry } from '../api/types';
import { ConfigPage } from '../features/config/ConfigPage';
import { DevicesPage } from '../features/devices/DevicesPage';
import { OverviewPage } from '../features/overview/OverviewPage';
import { WorkspacePage, WorkspaceTitlebar } from '../features/workspace/WorkspacePage';

function parentPath(rootPath: string): string {
  const normalized = rootPath.replace(/[\\/]+$/, '');
  const index = Math.max(normalized.lastIndexOf('/'), normalized.lastIndexOf('\\'));
  return index > 0 ? normalized.slice(0, index) : normalized;
}

export function ControlPlaneApp() {
  const [activePage, setActivePage] = useState<'overview' | 'workspace' | 'devices' | 'config'>('overview');
  const [configDirty, setConfigDirty] = useState(false);
  const [workspaceDirty, setWorkspaceDirty] = useState(false);
  const [workspaces, setWorkspaces] = useState<WorkspaceRegistryEntry[]>([]);
  const [workspaceRegistryLoading, setWorkspaceRegistryLoading] = useState(true);
  const [workspaceRegistryError, setWorkspaceRegistryError] = useState<ApiErrorBody | null>(null);
  const [selectedWorkspaceName, setSelectedWorkspaceName] = useState<string | null>(null);
  const [createRequested, setCreateRequested] = useState(false);
  const [workspaceConfigurationOpen, setWorkspaceConfigurationOpen] = useState(false);
  const [workspaceOutletPresentation, setWorkspaceOutletPresentation] = useState<'default' | 'full-bleed'>('default');
  const workspaceRegistryRequest = useRef(0);
  const workspaceCreateInitiator = useRef<{ element: HTMLElement; id: string | null } | null>(null);
  const workspaceCreateFocusRestore = useRef<(() => void) | null>(null);
  const workspaceCreatePreviousSelection = useRef<string | null>(null);
  const focusCreatedWorkspace = useRef(false);
  const selectedWorkspace = workspaces.find((workspace) => workspace.name === selectedWorkspaceName) ?? null;

  const refreshWorkspaces = (signal?: AbortSignal) => {
    const request = ++workspaceRegistryRequest.current;
    setWorkspaceRegistryLoading(true);
    setWorkspaceRegistryError(null);
    return controlPlaneClient.workspaces(signal).then((response) => {
      if (request === workspaceRegistryRequest.current && !signal?.aborted) setWorkspaces(response.workspaces);
    }).catch((error) => {
      if (request === workspaceRegistryRequest.current && !signal?.aborted) setWorkspaceRegistryError(toApiError(error));
    }).finally(() => {
      if (request === workspaceRegistryRequest.current && !signal?.aborted) setWorkspaceRegistryLoading(false);
    });
  };

  useEffect(() => {
    const controller = new AbortController();
    void refreshWorkspaces(controller.signal);
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (!focusCreatedWorkspace.current || !selectedWorkspaceName || !selectedWorkspace) return;
    focusCreatedWorkspace.current = false;
    requestAnimationFrame(() => document.getElementById('workspace-heading')?.focus());
  }, [selectedWorkspaceName, selectedWorkspace]);

  const canDiscardDraft = (destination: ControlPlanePageId) => {
    if (activePage === 'config' && destination !== 'config' && configDirty && !window.confirm('Discard unsaved Azure changes?')) return false;
    if (activePage === 'workspace' && workspaceDirty && !window.confirm('Discard unsaved workspace changes?')) return false;
    return true;
  };

  const navigate = (page: ControlPlanePageId) => {
    if (page !== 'overview' && page !== 'workspace' && page !== 'devices' && page !== 'config') return;
    if (!canDiscardDraft(page)) return;
    setConfigDirty(false);
    setWorkspaceDirty(false);
    workspaceCreateInitiator.current = null;
    workspaceCreateFocusRestore.current = null;
    workspaceCreatePreviousSelection.current = null;
    setWorkspaceOutletPresentation('default');
    if (page === 'workspace') {
      setSelectedWorkspaceName(null);
      setCreateRequested(false);
      setWorkspaceConfigurationOpen(false);
    }
    setActivePage(page);
  };

  const requestCreateWorkspace = (restoreFocus?: () => void) => {
    if (!canDiscardDraft('workspace')) return;
    const activeElement = document.activeElement;
    workspaceCreateInitiator.current = activeElement instanceof HTMLElement
      ? { element: activeElement, id: activeElement.id || null }
      : null;
    workspaceCreateFocusRestore.current = restoreFocus ?? null;
    workspaceCreatePreviousSelection.current = selectedWorkspaceName;
    setWorkspaceDirty(false);
    setWorkspaceOutletPresentation('default');
    setSelectedWorkspaceName(null);
    setCreateRequested(true);
    setWorkspaceConfigurationOpen(false);
    setActivePage('workspace');
  };

  const cancelWorkspaceCreation = () => {
    setCreateRequested(false);
    setWorkspaceDirty(false);
    setWorkspaceOutletPresentation('default');
    setSelectedWorkspaceName(workspaceCreatePreviousSelection.current);
    void refreshWorkspaces();
    requestAnimationFrame(() => {
      const restoreFocus = workspaceCreateFocusRestore.current;
      const initiator = workspaceCreateInitiator.current;
      if (restoreFocus) restoreFocus();
      else {
        const target = initiator?.element.isConnected
          ? initiator.element
          : initiator?.id ? document.getElementById(initiator.id) : null;
        target?.focus();
      }
      workspaceCreateInitiator.current = null;
      workspaceCreateFocusRestore.current = null;
      workspaceCreatePreviousSelection.current = null;
    });
  };

  const selectWorkspace = (name: string) => {
    if (!canDiscardDraft('workspace')) return;
    setWorkspaceDirty(false);
    workspaceCreateInitiator.current = null;
    workspaceCreateFocusRestore.current = null;
    workspaceCreatePreviousSelection.current = null;
    setWorkspaceOutletPresentation('default');
    setCreateRequested(false);
    setSelectedWorkspaceName(name);
    setWorkspaceConfigurationOpen(false);
    setActivePage('workspace');
  };

  const workspaceNavigation: WorkspaceNavigationItem[] = workspaces.map((workspace) => ({
    id: workspace.name,
    label: workspace.name,
    description: workspace.status !== 'unavailable'
      ? `${workspace.platforms.filter((item) => item.status === 'available').map((item) => item.platform).join(', ') || 'No available platforms'} · ${parentPath(workspace.rootPath)}`
      : `${parentPath(workspace.rootPath)} · unavailable`,
    available: workspace.status !== 'unavailable',
    message: workspace.status === 'unavailable' ? `${workspace.message} ${workspace.action}` : undefined,
  }));
  const shellWorkspaceProps = {
    workspaces: workspaceNavigation,
    selectedWorkspaceId: selectedWorkspaceName,
    workspaceRegistryStatus: workspaceRegistryLoading ? 'loading' as const : workspaceRegistryError ? 'error' as const : 'ready' as const,
    workspaceRegistryError: workspaceRegistryError?.message,
    onRetryWorkspaces: refreshWorkspaces,
    onCreateWorkspace: requestCreateWorkspace,
    onSelectWorkspace: selectWorkspace,
  };
  if (activePage === 'overview') return <ControlPlaneShell
    activePage="overview" title="" description=""
    onNavigate={navigate} {...shellWorkspaceProps}
  ><OverviewPage onNavigate={navigate} /></ControlPlaneShell>;

  if (activePage === 'workspace') return <ControlPlaneShell
    activePage="workspace" title="Workspace" description="Manage registered workspace targets and inspect cases and knowledge without exposing private configuration."
    outletPresentation={workspaceOutletPresentation}
    titleContent={selectedWorkspace && !createRequested ? <WorkspaceTitlebar workspace={selectedWorkspace} onConfigure={() => { setWorkspaceOutletPresentation('default'); setWorkspaceConfigurationOpen(true); }} /> : undefined}
    onNavigate={navigate} {...shellWorkspaceProps}
  ><WorkspacePage
      selectedName={selectedWorkspaceName}
      createRequested={createRequested}
      configurationOpen={workspaceConfigurationOpen}
      registryError={workspaceRegistryError}
      onRetryRegistry={refreshWorkspaces}
      onRequestCreate={requestCreateWorkspace}
      onCancelCreate={cancelWorkspaceCreation}
      onConfigurationOpenChange={setWorkspaceConfigurationOpen}
      onPresentationChange={setWorkspaceOutletPresentation}
      onCreated={(detail) => { workspaceCreateInitiator.current = null; workspaceCreateFocusRestore.current = null; workspaceCreatePreviousSelection.current = null; focusCreatedWorkspace.current = true; setCreateRequested(false); setSelectedWorkspaceName(detail.name); setWorkspaceDirty(false); setWorkspaceOutletPresentation('default'); refreshWorkspaces(); }}
      onRegistryChanged={() => { setCreateRequested(false); setWorkspaceDirty(false); setWorkspaceOutletPresentation('default'); refreshWorkspaces(); }}
      onDirtyChange={setWorkspaceDirty}
    /></ControlPlaneShell>;

  if (activePage === 'config') return <ControlPlaneShell
    activePage="config" title="Config" description="Manage the active model provider used by the next complete FSQ task."
    onNavigate={navigate} {...shellWorkspaceProps}
  ><ConfigPage onDirtyChange={setConfigDirty} /></ControlPlaneShell>;

  return <DevicesPage workspaces={workspaces} selectedWorkspaceName={selectedWorkspaceName} onWorkspaceChange={setSelectedWorkspaceName} renderShell={(toolbar, content) => <ControlPlaneShell
    activePage="devices" title="Device workspace"
    description="Select a target, choose how FSQ should test it, and follow real evidence while the run progresses."
    titleActions={toolbar} onNavigate={navigate} {...shellWorkspaceProps}
  >{content}</ControlPlaneShell>} />;
}
