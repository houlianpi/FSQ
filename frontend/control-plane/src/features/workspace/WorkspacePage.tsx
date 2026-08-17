import { useEffect, useRef, useState } from 'react';
import { AlertCircle, CheckCircle2, Edit3, FolderKanban, Plus, RefreshCw, ShieldCheck } from 'lucide-react';
import { controlPlaneClient, toApiError } from '../../api/controlPlaneClient';
import type { ApiErrorBody, WorkspaceDetail } from '../../api/types';
import { WorkspaceBrowser } from './WorkspaceBrowser';
import { WorkspaceForm } from './WorkspaceForm';
import './workspace.css';

interface WorkspacePageProps {
  selectedName: string | null;
  createRequested: boolean;
  registryError?: ApiErrorBody | null;
  onRetryRegistry: () => void;
  onRequestCreate: () => void;
  onCancelCreate: () => void;
  onCreated: (detail: WorkspaceDetail) => void;
  onRegistryChanged: () => void;
  onDirtyChange?: (dirty: boolean) => void;
}

function targetRows(detail: WorkspaceDetail): [string, string][] {
  const target = detail.target;
  if ('appId' in target) return [['App ID', target.appId]];
  if ('browserExecutablePath' in target) return [['Web path', target.browserExecutablePath]];
  if ('windowTitleRe' in target || 'launchArgs' in target) return [
    ['App path', target.appPath],
    ['Window title regex', target.windowTitleRe || 'Not configured'],
    ['Launch args', target.launchArgs || 'None'],
  ];
  return [['Bundle ID', target.bundleId || 'Not configured'], ['App path', target.appPath || 'Not configured']];
}

export function WorkspacePage({ selectedName, createRequested, registryError, onRetryRegistry, onRequestCreate, onCancelCreate, onCreated, onRegistryChanged, onDirtyChange }: WorkspacePageProps) {
  const [detail, setDetail] = useState<WorkspaceDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<ApiErrorBody | null>(null);
  const [editing, setEditing] = useState(false);
  const heading = useRef<HTMLHeadingElement>(null);

  const loadDetail = () => {
    if (!selectedName) return undefined;
    setLoading(true);
    setError(null);
    const controller = new AbortController();
    controlPlaneClient.workspace(selectedName, controller.signal).then((response) => {
      setDetail(response);
      setEditing(false);
      requestAnimationFrame(() => heading.current?.focus());
    }).catch((reason) => {
      if (!controller.signal.aborted) setError(toApiError(reason));
    }).finally(() => {
      if (!controller.signal.aborted) setLoading(false);
    });
    return controller;
  };

  useEffect(() => {
    setDetail(null);
    setEditing(false);
    setError(null);
    onDirtyChange?.(false);
    const controller = createRequested ? undefined : loadDetail();
    return () => controller?.abort();
  }, [selectedName, createRequested]);

  if (createRequested) return <div className="cp-workspace-page cp-workspace-page--form"><WorkspaceForm mode="create" onCancel={onCancelCreate} onSaved={(created) => { onRegistryChanged(); onCreated(created); }} onDirtyChange={onDirtyChange} /></div>;

  if (!selectedName) return <div className="cp-workspace-page"><section className="cp-workspace-zero"><span><FolderKanban aria-hidden="true" /></span><h1>Choose a workspace</h1><p>Select a registered workspace from the navigation or create a local workspace with its own target, cases, knowledge, and runtime environment.</p>{registryError && <div className="cp-inline-error"><AlertCircle aria-hidden="true" /><span><strong>{registryError.message}</strong><small>{registryError.action}</small></span><button className="cp-icon-button" type="button" aria-label="Retry workspace registry" onClick={onRetryRegistry}><RefreshCw aria-hidden="true" /></button></div>}<button id="workspace-create-empty" className="button button--primary" type="button" onClick={onRequestCreate}><Plus aria-hidden="true" />Create workspace</button></section></div>;

  if (loading) return <div className="cp-workspace-page"><p className="cp-workspace-loading">Loading workspace configuration…</p></div>;
  if (error) return <div className="cp-workspace-page"><section className="cp-workspace-zero"><span className="cp-workspace-zero--error"><AlertCircle aria-hidden="true" /></span><h1>Workspace unavailable</h1><p>{error.message}</p><small>{error.action}</small><button className="button" type="button" onClick={loadDetail}><RefreshCw aria-hidden="true" />Retry</button></section></div>;
  if (!detail) return null;

  if (editing) return <div className="cp-workspace-page cp-workspace-page--form"><WorkspaceForm mode="edit" detail={detail} onCancel={() => { setEditing(false); onDirtyChange?.(false); }} onSaved={(updated) => { setDetail(updated); setEditing(false); onDirtyChange?.(false); onRegistryChanged(); }} onReloadLatest={() => loadDetail()} onDirtyChange={onDirtyChange} /></div>;

  return <div className="cp-workspace-page">
    <section className="cp-workspace-banner" aria-labelledby="workspace-heading">
      <div className="cp-workspace-banner-heading"><div><span className="cp-kicker"><CheckCircle2 aria-hidden="true" />Available workspace</span><h1 ref={heading} tabIndex={-1} id="workspace-heading">{detail.name}</h1><p className="mono">{detail.rootPath}</p></div><button className="button" type="button" onClick={() => setEditing(true)}><Edit3 aria-hidden="true" />Edit</button></div>
      <div className="cp-workspace-facts"><dl><div><dt>Platform</dt><dd>{detail.platform}</dd></div>{targetRows(detail).map(([label, value]) => <div key={label}><dt>{label}</dt><dd className={label.toLowerCase().includes('path') ? 'mono' : undefined}>{value}</dd></div>)}</dl><div className="cp-secret-summary"><ShieldCheck aria-hidden="true" /><div><strong>Runtime environment</strong>{Object.keys(detail.env).length ? <ul>{Object.keys(detail.env).map((name) => <li key={name}><code>{name}</code><span>Configured</span></li>)}</ul> : <p>No private environment values configured.</p>}</div></div></div>
    </section>
    <WorkspaceBrowser key={detail.revision} workspaceName={detail.name} />
  </div>;
}