import { useMemo, useRef } from 'react';
import type { PlatformId, PlatformOption, WorkspaceRegistryEntry } from '../../api/types';
import { LiveEvidencePanel } from './components/LiveEvidencePanel';
import { OperationComposer } from './components/OperationComposer';
import { RunTimeline } from './components/RunTimeline';
import { TargetToolbar } from './components/TargetToolbar';
import { useDeviceWorkspace } from './hooks/useDeviceWorkspace';

interface DevicesPageProps {
  workspaces: readonly WorkspaceRegistryEntry[];
  selectedWorkspaceName: string | null;
  onWorkspaceChange: (workspaceName: string | null) => void;
  renderShell: (toolbar: React.ReactNode, content: React.ReactNode) => React.ReactNode;
}

const platformLabels: Record<PlatformId, string> = { android: 'Android', web: 'Web', windows: 'Windows', macos: 'macOS' };

export function DevicesPage({ workspaces, selectedWorkspaceName, onWorkspaceChange, renderShell }: DevicesPageProps) {
  const selectedWorkspace = workspaces.find((item) => item.name === selectedWorkspaceName) ?? null;
  const platforms = useMemo<PlatformOption[]>(() => (selectedWorkspace?.platforms ?? [])
    .filter((item) => item.status === 'available')
    .map((item) => ({ id: item.platform, label: platformLabels[item.platform] })), [selectedWorkspace]);
  const workspace = useDeviceWorkspace({
    workspaceName: selectedWorkspaceName,
    platforms,
    onWorkspaceChange,
  });
  const primaryInputRef = useRef<HTMLTextAreaElement | HTMLSelectElement>(null);
  const resultHeadingRef = useRef<HTMLHeadingElement>(null);
  const terminal = workspace.snapshot?.terminal === true;
  const hasRun = Boolean(workspace.requestId);
  const pageError = workspace.bootstrap.error || workspace.readiness.error || workspace.targets.error || workspace.cases.error || workspace.streamError;

  const newRun = () => {
    void workspace.newRun().then(() => window.setTimeout(() => primaryInputRef.current?.focus(), 0));
  };

  const toolbar = <TargetToolbar
    workspaces={workspaces} workspaceName={selectedWorkspaceName ?? ''} platforms={platforms} platform={workspace.platform} targetId={workspace.targetId} targets={workspace.targets.data}
    locked={workspace.controlsLocked} loading={workspace.targets.state === 'loading'} connectionLabel={workspace.connectionLabel}
    onWorkspaceChange={(name) => onWorkspaceChange(name || null)} onPlatformChange={workspace.setPlatform} onTargetChange={workspace.setTargetId} onRefresh={workspace.refresh}
  />;
  const content = <>
    <div className="visually-hidden" aria-live="polite" aria-atomic="true">
      {workspace.startError ? workspace.startError.message : terminal ? `Run ${workspace.snapshot?.status}: ${workspace.snapshot?.summary}` : hasRun ? `Run ${workspace.snapshot?.status ?? 'preparing'}. ${workspace.snapshot?.summary ?? ''} ${workspace.connectionLabel}.` : `${workspace.connectionLabel}.`}
    </div>
    {pageError && <div className="page-notice" role="alert">
      <strong>{pageError.message}</strong>
      <span>{pageError.action}</span>
    </div>}
    <div className="devices-workbench">
      <section className="operation-card" aria-labelledby="operation-title">
        <header className="card-header"><div><h1 id="operation-title">FSQ operation</h1><p>Target: {workspace.selectedTarget?.label ?? 'Not selected'}</p></div><span className={`status-badge status-badge--${workspace.snapshot?.status ?? 'idle'}`}>{workspace.snapshot?.status ?? 'idle'}</span></header>
        <div className="operation-body">
          {hasRun ? <RunTimeline snapshot={workspace.snapshot} connection={workspace.connection} selectedStepId={workspace.selectedStepId} resultHeadingRef={resultHeadingRef} onSelectStep={workspace.setSelectedStepId} onCancel={() => void workspace.cancel()} onNewRun={newRun} /> : <OperationComposer
            mode={workspace.mode} goal={workspace.goal} casePath={workspace.casePath} cases={workspace.cases.data?.cases ?? []} casesState={workspace.cases.state}
            readiness={workspace.readiness.data} discoveryLoading={workspace.readiness.state === 'loading' || workspace.targets.state === 'loading' || workspace.cases.state === 'loading'}
            canStart={workspace.canStart} errorMessage={workspace.startError?.message} errorAction={workspace.startError?.action} primaryInputRef={primaryInputRef}
            onModeChange={workspace.setMode} onGoalChange={workspace.setGoal} onCaseChange={workspace.setCasePath} onStart={() => void workspace.start()}
          />}
        </div>
      </section>
      <LiveEvidencePanel tab={workspace.evidenceTab} snapshot={workspace.snapshot} selectedStepId={workspace.selectedStepId} platform={workspace.platform || null} targetLabel={workspace.selectedTarget?.label ?? workspace.targetId} onTabChange={workspace.setEvidenceTab} onClearStep={() => workspace.setSelectedStepId(null)} />
    </div>
  </>;
  return <>{renderShell(toolbar, content)}</>;
}
