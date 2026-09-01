import { AlertTriangle, ArrowLeft, Bot, Check, ChevronRight, Folder, Play, Plus, RefreshCw, Settings } from 'lucide-react';
import type { WorkspaceRegistryEntry } from '../../api/types';
import type { ControlPlanePageId } from '../../app/shell/navigation';
import './overview.css';

export type OverviewProviderState =
  | { status: 'loading' }
  | { status: 'unconfigured' }
  | { status: 'configured'; provider: 'Azure OpenAI' | 'GitHub Copilot'; modelName: string; authenticated?: true }
  | { status: 'error'; error: { message: string; action: string } };

interface OverviewPageProps {
  workspaces: readonly WorkspaceRegistryEntry[];
  selectedWorkspace: WorkspaceRegistryEntry | null;
  registryStatus: 'loading' | 'ready' | 'error';
  registryError?: string;
  provider: OverviewProviderState;
  onNavigate: (page: ControlPlanePageId) => void;
  onCreateWorkspace: () => void;
  onSelectWorkspace: (name: string) => void;
  onClearWorkspace: () => void;
  onOpenWorkspace: (name: string) => void;
  onConfigureWorkspace: (name: string) => void;
  onRetryWorkspaces: () => void;
  onRetryProvider: () => void;
}

function ProviderSummary({ provider, onManage, onRetry }: { provider: OverviewProviderState; onManage: () => void; onRetry: () => void }) {
  return <section className="cp-overview-card cp-provider-card" aria-labelledby="provider-heading">
    <div className="cp-overview-card-heading"><span className="cp-overview-icon"><Bot aria-hidden="true" /></span><div><p className="cp-overview-eyebrow">Global AI configuration</p><h2 id="provider-heading">AI Provider</h2><p>Loaded from <code>~/.fsq</code> and shared by every Workspace.</p></div></div>
    <div className="cp-provider-state">
      {provider.status === 'loading' && <p role="status">Loading Provider configuration…</p>}
      {provider.status === 'unconfigured' && <><span className="cp-status-pill">Not configured</span><p>Configure a Provider to enable AI-assisted Case workflows.</p></>}
      {provider.status === 'configured' && <><span className="cp-status-pill cp-status-pill--success"><Check aria-hidden="true" /> Configured</span><dl><div><dt>Provider</dt><dd>{provider.provider}</dd></div><div><dt>Model</dt><dd>{provider.modelName}</dd></div>{provider.authenticated && <div><dt>Status</dt><dd>Authenticated</dd></div>}</dl></>}
      {provider.status === 'error' && <div className="cp-inline-error" role="alert"><strong>{provider.error.message}</strong><span>{provider.error.action}</span><button className="button" type="button" onClick={onRetry}><RefreshCw aria-hidden="true" /> Retry</button></div>}
    </div>
    <button className="button" type="button" onClick={onManage}><Settings aria-hidden="true" /> Manage Provider</button>
  </section>;
}

export function OverviewPage({ workspaces, selectedWorkspace, registryStatus, registryError, provider, onNavigate, onCreateWorkspace, onSelectWorkspace, onClearWorkspace, onOpenWorkspace, onConfigureWorkspace, onRetryWorkspaces, onRetryProvider }: OverviewPageProps) {
  const currentWorkspace = registryStatus === 'ready' && selectedWorkspace?.status !== 'unavailable' ? selectedWorkspace : null;
  const availablePlatforms = currentWorkspace?.platforms.filter((item) => item.status === 'available') ?? [];
  const hasAvailablePlatform = availablePlatforms.length > 0;
  const devicesBlockedReason = currentWorkspace ? 'Initialize or repair a platform in Workspace until at least one platform is available.' : 'Select an available Workspace before continuing.';
  const openWorkspace = () => currentWorkspace ? onOpenWorkspace(currentWorkspace.name) : onNavigate('workspace');

  return <div className="cp-overview">
    <header className="cp-overview-intro"><p className="cp-overview-eyebrow">Overview</p><h1>Start from a real Workspace</h1><p>Configure AI once, then create, run, and inspect tests in the Workspace that owns their evidence.</p></header>
    <ProviderSummary provider={provider} onManage={() => onNavigate('config')} onRetry={onRetryProvider} />
    <section className="cp-overview-card cp-workflow-card" aria-labelledby="workspace-flow-heading">
      <div className="cp-workspace-identity">{currentWorkspace && <button className="cp-workspace-back" type="button" onClick={onClearWorkspace} aria-label="Back to Workspaces" title="Back to Workspaces"><ArrowLeft aria-hidden="true" /></button>}<div className="cp-workspace-identity-copy"><p className="cp-overview-eyebrow">Current Workspace</p><h2 id="workspace-flow-heading">{currentWorkspace?.name ?? 'No Workspace selected'}</h2></div>{currentWorkspace && <button className="button cp-workspace-open" type="button" onClick={() => onConfigureWorkspace(currentWorkspace.name)}>Configure Workspace <ChevronRight aria-hidden="true" /></button>}</div>
      {registryStatus === 'loading' && <div className="cp-workspace-state" role="status">Loading registered Workspaces…</div>}
      {registryStatus === 'error' && <div className="cp-workspace-state cp-workspace-state--error" role="alert"><AlertTriangle aria-hidden="true" /><div><strong>Workspace registry unavailable</strong><span>{registryError || 'FSQ could not load registered Workspaces.'}</span></div><button className="button" type="button" onClick={onRetryWorkspaces}><RefreshCw aria-hidden="true" /> Retry</button></div>}
      {registryStatus === 'ready' && !currentWorkspace && <div className="cp-workspace-empty"><div><strong>Choose the Workspace you want to test.</strong><span>{workspaces.length ? 'Select an available Workspace below, or create another one.' : 'Create a Workspace with at least one platform to begin.'}</span></div>{workspaces.some((item) => item.status !== 'unavailable') && <div className="cp-workspace-choices">{workspaces.filter((item) => item.status !== 'unavailable').map((item) => <button type="button" key={item.name} onClick={() => onSelectWorkspace(item.name)}><Folder aria-hidden="true" /><span><strong>{item.name}</strong><small>{item.platforms.length ? item.platforms.map((platform) => `${platform.platform}${platform.status === 'available' ? '' : ` (${platform.status})`}`).join(', ') : 'No platforms configured'}</small></span></button>)}</div>}<button className="button button--primary" type="button" onClick={onCreateWorkspace}><Plus aria-hidden="true" /> Create Workspace</button></div>}
      {currentWorkspace && <div className="cp-platform-summary" aria-label="Configured platforms">{currentWorkspace.platforms.length ? currentWorkspace.platforms.map((item) => <span key={item.platform} className={item.status === 'available' ? 'is-available' : ''}><strong>{item.platform}</strong><small><i aria-hidden="true" />{item.status}</small></span>) : <span>No platforms configured</span>}</div>}
      <ol className="cp-workflow-steps" aria-label="Test this Workspace">
        <li><span className="cp-step-number">1</span><div><h3>Workspace and platform</h3><p>{currentWorkspace ? hasAvailablePlatform ? 'This Workspace has an available platform.' : 'This Workspace needs an available platform before testing.' : 'Create or select a Workspace with at least one platform.'}</p></div>{!hasAvailablePlatform && <span className="cp-step-status cp-status-pill">{currentWorkspace ? 'Needs attention' : 'Not started'}</span>}<button className="button cp-step-action" type="button" onClick={currentWorkspace ? openWorkspace : onCreateWorkspace}>{currentWorkspace ? 'Open Workspace' : 'Create Workspace'}</button></li>
        <li><span className="cp-step-number">2</span><div><h3>Create or run a Case</h3><p>Explore from a goal or replay a reviewed Case in Devices.</p></div><button className="button cp-step-action" type="button" onClick={() => onNavigate('devices')} disabled={!hasAvailablePlatform} aria-describedby={!hasAvailablePlatform ? 'case-step-blocked' : undefined}><Play aria-hidden="true" /> Open Devices</button>{!hasAvailablePlatform && <small id="case-step-blocked" className="cp-step-blocked">{devicesBlockedReason}</small>}</li>
        <li><span className="cp-step-number">3</span><div><h3>Inspect the latest Run</h3><p>Run history and evidence review will be available in a future release.</p></div><span className="cp-step-coming cp-status-pill">Coming soon</span></li>
      </ol>
    </section>
  </div>;
}
