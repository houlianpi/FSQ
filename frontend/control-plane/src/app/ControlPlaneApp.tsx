import { useEffect, useRef, useState } from 'react';
import { ControlPlaneShell } from './shell/ControlPlaneShell';
import type { ControlPlanePageId, WorkspaceNavigationItem } from './shell/navigation';
import { controlPlaneClient, toApiError } from '../api/controlPlaneClient';
import type { ApiErrorBody, WorkspaceRegistryEntry } from '../api/types';
import { ConfigPage } from '../features/config/ConfigPage';
import { DevicesPage, type DevicesLaunchIntent } from '../features/devices/DevicesPage';
import { OverviewPage, type OverviewProviderState } from '../features/overview/OverviewPage';
import { WorkspacePage, WorkspaceTitlebar } from '../features/workspace/WorkspacePage';

type DevicesLaunchRequest =
  | Omit<Extract<DevicesLaunchIntent, { mode: 'explore' }>, 'id'>
  | Omit<Extract<DevicesLaunchIntent, { mode: 'strict' }>, 'id'>;

export function ControlPlaneApp() {
  const [activePage, setActivePage] = useState<'overview' | 'workspace' | 'devices' | 'config'>('overview');
  const [configDirty, setConfigDirty] = useState(false);
  const [workspaceDirty, setWorkspaceDirty] = useState(false);
  const [workspaces, setWorkspaces] = useState<WorkspaceRegistryEntry[]>([]);
  const [workspaceRegistryLoading, setWorkspaceRegistryLoading] = useState(true);
  const [workspaceRegistryError, setWorkspaceRegistryError] = useState<ApiErrorBody | null>(null);
  const [overviewProvider, setOverviewProvider] = useState<OverviewProviderState>({ status: 'loading' });
  const [selectedWorkspaceName, setSelectedWorkspaceName] = useState<string | null>(null);
  const [createRequested, setCreateRequested] = useState(false);
  const [workspaceConfigurationOpen, setWorkspaceConfigurationOpen] = useState(false);
  const [workspaceOutletPresentation, setWorkspaceOutletPresentation] = useState<'default' | 'full-bleed'>('default');
  const [devicesLaunchIntent, setDevicesLaunchIntent] = useState<DevicesLaunchIntent | null>(null);
  const workspaceRegistryRequest = useRef(0);
  const providerRequest = useRef(0);
  const devicesLaunchSequence = useRef(0);
  const workspaceCreateInitiator = useRef<{ element: HTMLElement; id: string | null } | null>(null);
  const workspaceCreateFocusRestore = useRef<(() => void) | null>(null);
  const workspaceCreatePreviousSelection = useRef<string | null>(null);
  const focusCreatedWorkspace = useRef(false);
  const workspaceRegistryReady = !workspaceRegistryLoading && workspaceRegistryError === null;
  const authoritativeWorkspaces = workspaceRegistryReady ? workspaces : [];
  const selectedWorkspace = authoritativeWorkspaces.find((workspace) => workspace.name === selectedWorkspaceName && workspace.status !== 'unavailable') ?? null;

  const refreshWorkspaces = (signal?: AbortSignal) => {
    const request = ++workspaceRegistryRequest.current;
    setWorkspaceRegistryLoading(true);
    setWorkspaceRegistryError(null);
    return controlPlaneClient.workspaces(signal).then((response) => {
      if (request === workspaceRegistryRequest.current && !signal?.aborted) {
        setWorkspaces(response.workspaces);
        setSelectedWorkspaceName((current) => current && response.workspaces.some((workspace) => workspace.name === current && workspace.status !== 'unavailable') ? current : null);
      }
    }).catch((error) => {
      if (request === workspaceRegistryRequest.current && !signal?.aborted) {
        setWorkspaceRegistryError(toApiError(error));
        setSelectedWorkspaceName(null);
      }
    }).finally(() => {
      if (request === workspaceRegistryRequest.current && !signal?.aborted) setWorkspaceRegistryLoading(false);
    });
  };

  const refreshOverviewProvider = (signal?: AbortSignal) => {
    const request = ++providerRequest.current;
    setOverviewProvider({ status: 'loading' });
    return controlPlaneClient.config(signal).then((response) => {
      if (request !== providerRequest.current || signal?.aborted) return;
      if (!response.configured) {
        setOverviewProvider({ status: 'unconfigured' });
      } else if (response.provider.type === 'github_copilot') {
        setOverviewProvider({ status: 'configured', provider: 'GitHub Copilot', modelName: response.provider.modelName, authenticated: true });
      } else {
        setOverviewProvider({ status: 'configured', provider: 'Azure OpenAI', modelName: response.provider.modelName });
      }
    }).catch((error) => {
      if (request === providerRequest.current && !signal?.aborted) {
        const safeError = toApiError(error);
        setOverviewProvider({ status: 'error', error: { message: safeError.message, action: safeError.action } });
      }
    });
  };

  useEffect(() => {
    const controller = new AbortController();
    void refreshWorkspaces(controller.signal);
    void refreshOverviewProvider(controller.signal);
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
    setDevicesLaunchIntent(null);
    if (page === 'workspace') {
      setSelectedWorkspaceName(null);
      setCreateRequested(false);
      setWorkspaceConfigurationOpen(false);
    }
    if (page === 'overview') void refreshOverviewProvider();
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

  const launchDevices = (intent: DevicesLaunchRequest) => {
    if (!canDiscardDraft('devices')) return;
    setConfigDirty(false);
    setWorkspaceDirty(false);
    setWorkspaceOutletPresentation('default');
    setDevicesLaunchIntent({ ...intent, id: ++devicesLaunchSequence.current } as DevicesLaunchIntent);
    setActivePage('devices');
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

  const workspaceNavigation: WorkspaceNavigationItem[] = authoritativeWorkspaces.map((workspace) => ({
    id: workspace.name,
    label: workspace.name,
    description: workspace.platforms.map((item) => `${item.platform}${item.status === 'available' ? '' : ` ${item.status}`}`).join(', ')
      || (workspace.status === 'unavailable' ? 'unavailable' : 'No configured platforms'),
    available: workspace.status !== 'unavailable',
    message: workspace.status === 'unavailable' ? `${workspace.message} ${workspace.action}` : undefined,
  }));
  const shellWorkspaceProps = {
    workspaces: workspaceNavigation,
    selectedWorkspaceId: selectedWorkspace?.name ?? null,
    workspaceRegistryStatus: workspaceRegistryLoading ? 'loading' as const : workspaceRegistryError ? 'error' as const : 'ready' as const,
    workspaceRegistryError: workspaceRegistryError?.message,
    onRetryWorkspaces: refreshWorkspaces,
    onCreateWorkspace: requestCreateWorkspace,
    onSelectWorkspace: selectWorkspace,
  };
  if (activePage === 'overview') return <ControlPlaneShell
    activePage="overview" title="Overview" description="Set up this Workspace and complete your first evidence-backed run."
    onNavigate={navigate} {...shellWorkspaceProps}
  ><OverviewPage
      workspaces={authoritativeWorkspaces}
      selectedWorkspace={selectedWorkspace}
      registryStatus={workspaceRegistryLoading ? 'loading' : workspaceRegistryError ? 'error' : 'ready'}
      registryError={workspaceRegistryError?.message}
      provider={overviewProvider}
      onNavigate={navigate}
      onCreateWorkspace={requestCreateWorkspace}
      onSelectWorkspace={(name) => { setSelectedWorkspaceName(name); setActivePage('overview'); }}
      onClearWorkspace={() => setSelectedWorkspaceName(null)}
      onOpenWorkspace={selectWorkspace}
      onConfigureWorkspace={(name) => { setSelectedWorkspaceName(name); setCreateRequested(false); setWorkspaceConfigurationOpen(true); setWorkspaceOutletPresentation('default'); setActivePage('workspace'); }}
      onRetryWorkspaces={refreshWorkspaces}
      onRetryProvider={refreshOverviewProvider}
    /></ControlPlaneShell>;

  if (activePage === 'workspace') return <ControlPlaneShell
    activePage="workspace" title="Workspace" description="Manage registered workspace targets and inspect cases and knowledge without exposing private configuration."
    outletPresentation={workspaceOutletPresentation}
    titleContent={selectedWorkspace && !createRequested ? <WorkspaceTitlebar workspace={selectedWorkspace} onConfigure={() => { setWorkspaceOutletPresentation('default'); setWorkspaceConfigurationOpen(true); }} /> : undefined}
    onNavigate={navigate} {...shellWorkspaceProps}
  ><WorkspacePage
      selectedName={selectedWorkspace?.name ?? null}
      createRequested={createRequested}
      configurationOpen={workspaceConfigurationOpen}
      registryError={workspaceRegistryError}
      onRetryRegistry={refreshWorkspaces}
      onRequestCreate={requestCreateWorkspace}
      onCancelCreate={cancelWorkspaceCreation}
      onConfigurationOpenChange={setWorkspaceConfigurationOpen}
      onPresentationChange={setWorkspaceOutletPresentation}
      onRecordCase={() => selectedWorkspace && launchDevices({ mode: 'explore', workspaceName: selectedWorkspace.name })}
      onReplayCase={(platform, casePath) => selectedWorkspace && launchDevices({ mode: 'strict', workspaceName: selectedWorkspace.name, platform, casePath })}
      onCreated={(detail) => { workspaceCreateInitiator.current = null; workspaceCreateFocusRestore.current = null; workspaceCreatePreviousSelection.current = null; focusCreatedWorkspace.current = true; setCreateRequested(false); setSelectedWorkspaceName(detail.name); setWorkspaceDirty(false); setWorkspaceOutletPresentation('default'); refreshWorkspaces(); }}
      onRegistryChanged={() => { setCreateRequested(false); setWorkspaceDirty(false); setWorkspaceOutletPresentation('default'); refreshWorkspaces(); }}
      onDirtyChange={setWorkspaceDirty}
    /></ControlPlaneShell>;

  if (activePage === 'config') return <ControlPlaneShell
    activePage="config" title="Config" description="Manage the active model provider used by the next complete FSQ task."
    onNavigate={navigate} {...shellWorkspaceProps}
  ><ConfigPage onDirtyChange={setConfigDirty} /></ControlPlaneShell>;

  return <DevicesPage workspaces={authoritativeWorkspaces} workspaceRegistryReady={workspaceRegistryReady} selectedWorkspaceName={selectedWorkspace?.name ?? null} onWorkspaceChange={setSelectedWorkspaceName}
    launchIntent={devicesLaunchIntent}
    onLaunchIntentConsumed={(intentId) => setDevicesLaunchIntent((current) => current?.id === intentId ? null : current)}
    renderShell={(toolbar, content) => <ControlPlaneShell
    activePage="devices" title="Device workspace"
    description="Select a target, choose how FSQ should test it, and follow real evidence while the run progresses."
    titleActions={toolbar} onNavigate={navigate} {...shellWorkspaceProps}
  >{content}</ControlPlaneShell>} />;
}
