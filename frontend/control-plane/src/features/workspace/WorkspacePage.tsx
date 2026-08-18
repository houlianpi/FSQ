import { useEffect, useRef, useState } from 'react';
import { AlertCircle, ArrowLeft, Edit3, FolderKanban, Plus, RefreshCw, Settings, ShieldCheck } from 'lucide-react';
import { controlPlaneClient, toApiError } from '../../api/controlPlaneClient';
import type {
  ApiErrorBody,
  PlatformId,
  WorkspaceDetail,
  WorkspacePlatformDetail,
  WorkspacePlatformSummary,
  WorkspaceRegistryEntry,
  WorkspaceTarget,
} from '../../api/types';
import { WorkspaceBrowser } from './WorkspaceBrowser';
import { WorkspaceForm } from './WorkspaceForm';
import './workspace.css';

interface WorkspacePageProps {
  selectedName: string | null;
  createRequested: boolean;
  configurationOpen: boolean;
  registryError?: ApiErrorBody | null;
  onRetryRegistry: () => void;
  onRequestCreate: () => void;
  onCancelCreate: () => void;
  onConfigurationOpenChange: (open: boolean) => void;
  onCreated: (detail: WorkspaceDetail) => void;
  onRegistryChanged: () => void;
  onDirtyChange?: (dirty: boolean) => void;
}

const allPlatforms: PlatformId[] = ['android', 'web', 'windows', 'macos'];
const platformLabels: Record<PlatformId, string> = { android: 'Android', web: 'Web', windows: 'Windows', macos: 'macOS' };

export function WorkspaceTitlebar({ workspace, onConfigure }: { workspace: WorkspaceRegistryEntry; onConfigure: () => void }) {
  return <div className="cp-workspace-titlebar">
    <div><div className="cp-workspace-title-row"><h1 id="workspace-heading" tabIndex={-1}>{workspace.name}</h1><div className="cp-workspace-platforms" aria-label="Workspace platforms">{workspace.platforms.length ? workspace.platforms.map((platform) => <span key={platform.platform} className={`cp-workspace-platform cp-workspace-platform--${platform.status}`} aria-label={`${platformLabels[platform.platform]} ${platform.status}`}><strong>{platformLabels[platform.platform]}</strong></span>) : <span>No configured platforms</span>}</div></div><p className="mono">{workspace.rootPath}</p></div>
    <button className="button" type="button" aria-label="Configure workspace" title="Configure workspace" onClick={onConfigure}><Settings aria-hidden="true" /><span>Configure</span></button>
  </div>;
}

function targetRows(target?: WorkspaceTarget): [string, string][] {
  if (!target) return [];
  if ('appId' in target) return [['App ID', target.appId]];
  if ('browserExecutablePath' in target) return [['Web path', target.browserExecutablePath]];
  if ('windowTitleRe' in target || 'launchArgs' in target) return [
    ['App path', target.appPath],
    ['Window title regex', target.windowTitleRe || 'Not configured'],
    ['Launch args', target.launchArgs || 'None'],
  ];
  return [['Bundle ID', target.bundleId || 'Not configured'], ['App path', target.appPath || 'Not configured']];
}

function platformRevision(detail: WorkspaceDetail): string {
  return detail.platforms.map((platform) => `${platform.platform}:${platform.revision ?? platform.status}`).join('|');
}

export function WorkspacePage({ selectedName, createRequested, configurationOpen, registryError, onRetryRegistry, onRequestCreate, onCancelCreate, onConfigurationOpenChange, onCreated, onRegistryChanged, onDirtyChange }: WorkspacePageProps) {
  const [detail, setDetail] = useState<WorkspaceDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<ApiErrorBody | null>(null);
  const [selectedPlatform, setSelectedPlatform] = useState<PlatformId | null>(null);
  const [formMode, setFormMode] = useState<'add' | 'edit' | null>(null);
  const [platformDetail, setPlatformDetail] = useState<WorkspacePlatformDetail | null>(null);
  const [platformLoading, setPlatformLoading] = useState(false);
  const [platformError, setPlatformError] = useState<ApiErrorBody | null>(null);
  const platformDetailController = useRef<AbortController | null>(null);
  const loadDetail = () => {
    if (!selectedName) return undefined;
    setLoading(true);
    setError(null);
    const controller = new AbortController();
    void controlPlaneClient.workspace(selectedName, controller.signal).then((response) => {
      setDetail(response);
      setSelectedPlatform((current) => response.platforms.some((item) => item.platform === current) ? current : (response.platforms[0]?.platform ?? null));
    }).catch((reason) => {
      if (!controller.signal.aborted) setError(toApiError(reason));
    }).finally(() => {
      if (!controller.signal.aborted) setLoading(false);
    });
    return controller;
  };

  const loadPlatformDetail = (platform: PlatformId) => {
    if (!selectedName) return;
    platformDetailController.current?.abort();
    const controller = new AbortController();
    platformDetailController.current = controller;
    setPlatformLoading(true);
    setPlatformError(null);
    void controlPlaneClient.workspacePlatform(selectedName, platform, controller.signal).then((response) => {
      if (controller.signal.aborted || platformDetailController.current !== controller) return;
      setPlatformDetail(response);
      setFormMode('edit');
    }).catch((reason) => {
      if (!controller.signal.aborted && platformDetailController.current === controller) setPlatformError(toApiError(reason));
    }).finally(() => {
      if (!controller.signal.aborted && platformDetailController.current === controller) setPlatformLoading(false);
    });
  };

  useEffect(() => {
    platformDetailController.current?.abort();
    platformDetailController.current = null;
    setDetail(null);
    onConfigurationOpenChange(false);
    setSelectedPlatform(null);
    setFormMode(null);
    setPlatformDetail(null);
    setError(null);
    setPlatformError(null);
    onDirtyChange?.(false);
    const controller = createRequested ? undefined : loadDetail();
    return () => {
      controller?.abort();
      platformDetailController.current?.abort();
    };
  }, [selectedName, createRequested]);

  useEffect(() => () => platformDetailController.current?.abort(), []);

  const closeForm = () => {
    platformDetailController.current?.abort();
    platformDetailController.current = null;
    setFormMode(null);
    setPlatformDetail(null);
    setPlatformError(null);
    onDirtyChange?.(false);
  };
  const acceptPlatformSave = (workspace: WorkspaceDetail, platform?: WorkspacePlatformDetail) => {
    setDetail(workspace);
    setSelectedPlatform(platform?.platform ?? selectedPlatform);
    closeForm();
    onRegistryChanged();
  };

  if (createRequested) return <div className="cp-workspace-page cp-workspace-page--form"><WorkspaceForm mode="create" onCancel={onCancelCreate} onSaved={(created) => { onRegistryChanged(); onCreated(created); }} onDirtyChange={onDirtyChange} /></div>;

  if (!selectedName) return <div className="cp-workspace-page"><section className="cp-workspace-zero"><span><FolderKanban aria-hidden="true" /></span><h1>Choose a workspace</h1><p>Select a registered workspace from the navigation or create a local workspace with independent platform targets, cases, knowledge, and runs.</p>{registryError && <div className="cp-inline-error"><AlertCircle aria-hidden="true" /><span><strong>{registryError.message}</strong><small>{registryError.action}</small></span><button className="cp-icon-button" type="button" aria-label="Retry workspace registry" onClick={onRetryRegistry}><RefreshCw aria-hidden="true" /></button></div>}<button id="workspace-create-empty" className="button button--primary" type="button" onClick={onRequestCreate}><Plus aria-hidden="true" />Create workspace</button></section></div>;

  if (loading) return <div className="cp-workspace-page"><p className="cp-workspace-loading">Loading workspace summary…</p></div>;
  if (error) return <div className="cp-workspace-page"><section className="cp-workspace-zero"><span className="cp-workspace-zero--error"><AlertCircle aria-hidden="true" /></span><h1>Workspace unavailable</h1><p>{error.message}</p><small>{error.action}</small><button className="button" type="button" onClick={loadDetail}><RefreshCw aria-hidden="true" />Retry</button></section></div>;
  if (!detail) return null;

  const selectedSummary: WorkspacePlatformSummary | null = detail.platforms.find((item) => item.platform === selectedPlatform) ?? null;
  const absentPlatforms = allPlatforms.filter((platform) => !detail.platforms.some((item) => item.platform === platform));

  if (formMode === 'edit' && platformDetail) return <div className="cp-workspace-page cp-workspace-page--form"><WorkspaceForm
    key={platformDetail.revision} mode="edit" detail={platformDetail} onCancel={closeForm} onSaved={acceptPlatformSave}
    onReloadLatest={() => selectedPlatform && loadPlatformDetail(selectedPlatform)} onDirtyChange={onDirtyChange}
  /></div>;
  if (formMode === 'add') return <div className="cp-workspace-page cp-workspace-page--form"><WorkspaceForm
    mode="add" workspace={detail} allowedPlatforms={absentPlatforms} onCancel={closeForm} onSaved={acceptPlatformSave} onDirtyChange={onDirtyChange}
  /></div>;

  if (configurationOpen) {
    const selectPlatformTab = (platform: PlatformId) => {
      platformDetailController.current?.abort();
      platformDetailController.current = null;
      setPlatformLoading(false);
      setPlatformDetail(null);
      setFormMode(null);
      setSelectedPlatform(platform);
      setPlatformError(null);
    };
    const handleTabKeyDown = (event: React.KeyboardEvent<HTMLButtonElement>, index: number) => {
      let nextIndex: number | null = null;
      if (event.key === 'ArrowRight') nextIndex = (index + 1) % detail.platforms.length;
      if (event.key === 'ArrowLeft') nextIndex = (index - 1 + detail.platforms.length) % detail.platforms.length;
      if (event.key === 'Home') nextIndex = 0;
      if (event.key === 'End') nextIndex = detail.platforms.length - 1;
      if (nextIndex === null) return;
      event.preventDefault();
      const next = detail.platforms[nextIndex];
      selectPlatformTab(next.platform);
      document.getElementById(`workspace-platform-tab-${next.platform}`)?.focus();
    };
    return <div className="cp-workspace-page"><section className="cp-workspace-configuration" aria-labelledby="workspace-configuration-heading">
    <button className="button cp-back-button" type="button" onClick={() => { platformDetailController.current?.abort(); onConfigurationOpenChange(false); }}><ArrowLeft aria-hidden="true" />Workspace</button>
    <header><div><span className="cp-kicker">Configuration</span><h1 id="workspace-configuration-heading">{detail.name}</h1><p className="mono">{detail.rootPath}</p></div>{absentPlatforms.length > 0 && <button className="button button--primary" type="button" onClick={() => setFormMode('add')}><Plus aria-hidden="true" />Add platform</button>}</header>
    <div className="cp-platform-tabs" role="tablist" aria-label="Configured platforms">{detail.platforms.map((platform, index) => <button id={`workspace-platform-tab-${platform.platform}`} key={platform.platform} type="button" role="tab" aria-selected={selectedPlatform === platform.platform} aria-controls="workspace-platform-panel" tabIndex={selectedPlatform === platform.platform ? 0 : -1} onKeyDown={(event) => handleTabKeyDown(event, index)} onClick={() => selectPlatformTab(platform.platform)}>{platformLabels[platform.platform]}<span className={`cp-platform-status cp-platform-status--${platform.status}`}>{platform.status}</span></button>)}</div>
    <div id="workspace-platform-panel" role="tabpanel" aria-labelledby={selectedPlatform ? `workspace-platform-tab-${selectedPlatform}` : undefined}>{!selectedSummary ? <div className="cp-pane-state">No platform configuration is available.</div> : selectedSummary.status === 'unavailable' ? <div className="cp-platform-unavailable" role="status"><AlertCircle aria-hidden="true" /><div><strong>{platformLabels[selectedSummary.platform]} configuration unavailable</strong><p>{selectedSummary.message}</p><small>{selectedSummary.action}</small></div></div> : <div className="cp-platform-summary">
      <div className="cp-platform-summary-heading"><div><h2>{platformLabels[selectedSummary.platform]} target</h2><p>Revision <code>{selectedSummary.revision}</code></p></div><button className="button" type="button" disabled={platformLoading} onClick={() => loadPlatformDetail(selectedSummary.platform)}><Edit3 aria-hidden="true" />{platformLoading ? 'Loading…' : 'Edit'}</button></div>
      {platformError && <div className="cp-inline-error" role="alert"><AlertCircle aria-hidden="true" /><span><strong>{platformError.message}</strong><small>{platformError.action}</small></span></div>}
      <div className="cp-workspace-facts"><dl>{targetRows(selectedSummary.target).map(([label, value]) => <div key={label}><dt>{label}</dt><dd className={label.toLowerCase().includes('path') ? 'mono' : undefined}>{value}</dd></div>)}</dl><div className="cp-secret-summary"><ShieldCheck aria-hidden="true" /><div><strong>Runtime environment</strong>{selectedSummary.env?.length ? <ul>{selectedSummary.env.map((item) => <li key={item.name}><code>{item.name}</code><span>Configured</span></li>)}</ul> : <p>No private environment values configured.</p>}</div></div></div>
    </div>}</div>
  </section></div>;
  }

  return <div className="cp-workspace-page"><WorkspaceBrowser key={platformRevision(detail)} workspaceName={detail.name} /></div>;
}