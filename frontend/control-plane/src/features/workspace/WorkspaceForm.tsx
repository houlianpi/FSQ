import { useEffect, useMemo, useRef, useState } from 'react';
import { AlertCircle, Eye, EyeOff, Plus, RefreshCw, Trash2 } from 'lucide-react';
import { ControlPlaneApiError, controlPlaneClient, toApiError } from '../../api/controlPlaneClient';
import type { ApiErrorBody, PlatformId, WorkspaceDetail, WorkspaceTarget } from '../../api/types';

interface WorkspaceFormProps {
  mode: 'create' | 'edit';
  detail?: WorkspaceDetail;
  onCancel: () => void;
  onSaved: (detail: WorkspaceDetail) => void;
  onReloadLatest?: () => void;
  onDirtyChange?: (dirty: boolean) => void;
}

interface TargetDraft {
  appId: string;
  browserExecutablePath: string;
  appPath: string;
  windowTitleRe: string;
  launchArgs: string;
  bundleId: string;
}
interface EnvRow { id: number; name: string; value: string }

const emptyTarget = (): TargetDraft => ({ appId: '', browserExecutablePath: '', appPath: '', windowTitleRe: '', launchArgs: '', bundleId: '' });

function targetFromDetail(detail?: WorkspaceDetail): TargetDraft {
  const draft = emptyTarget();
  if (!detail) return draft;
  const target = detail.target;
  if ('appId' in target) draft.appId = target.appId;
  if ('browserExecutablePath' in target) draft.browserExecutablePath = target.browserExecutablePath;
  if ('appPath' in target) draft.appPath = target.appPath ?? '';
  if ('windowTitleRe' in target) draft.windowTitleRe = target.windowTitleRe ?? '';
  if ('launchArgs' in target) draft.launchArgs = target.launchArgs;
  if ('bundleId' in target) draft.bundleId = target.bundleId ?? '';
  return draft;
}

function targetPayload(platform: PlatformId, target: TargetDraft): WorkspaceTarget {
  if (platform === 'android') return { appId: target.appId.trim() };
  if (platform === 'web') return { browserExecutablePath: target.browserExecutablePath.trim() };
  if (platform === 'windows') return {
    appPath: target.appPath.trim(),
    ...(target.windowTitleRe.trim() ? { windowTitleRe: target.windowTitleRe.trim() } : {}),
    launchArgs: target.launchArgs,
  };
  return {
    ...(target.bundleId.trim() ? { bundleId: target.bundleId.trim() } : {}),
    ...(target.appPath.trim() ? { appPath: target.appPath.trim() } : {}),
  };
}

function finalPath(parentPath: string, name: string): string {
  if (!parentPath.trim()) return name.trim();
  const separator = parentPath.includes('\\') ? '\\' : '/';
  return `${parentPath.trim().replace(/[\\/]+$/, '')}${separator}${name.trim()}`;
}

export function WorkspaceForm({ mode, detail, onCancel, onSaved, onReloadLatest, onDirtyChange }: WorkspaceFormProps) {
  const [name, setName] = useState(detail?.name ?? '');
  const [parentPath, setParentPath] = useState(detail ? detail.rootPath.replace(/[\\/][^\\/]+$/, '') : '');
  const [platform, setPlatform] = useState<PlatformId>(detail?.platform ?? 'android');
  const [target, setTarget] = useState<TargetDraft>(() => targetFromDetail(detail));
  const [envRows, setEnvRows] = useState<EnvRow[]>(() => Object.entries(detail?.env ?? {}).map(([envName, value], index) => ({ id: index + 1, name: envName, value })));
  const [revealed, setRevealed] = useState<Set<number>>(new Set());
  const [error, setError] = useState<ApiErrorBody | null>(null);
  const [fieldError, setFieldError] = useState('');
  const [pending, setPending] = useState(false);
  const nextRowId = useRef(envRows.length + 1);
  const firstField = useRef<HTMLInputElement>(null);
  const initialValue = useMemo(() => JSON.stringify({ target: detail?.target, env: detail?.env }), [detail]);
  const currentValue = JSON.stringify({ target: targetPayload(platform, target), env: Object.fromEntries(envRows.map((row) => [row.name, row.value])) });
  const dirty = mode === 'create'
    ? Boolean(name || parentPath || Object.values(target).some(Boolean) || envRows.length)
    : currentValue !== initialValue;

  useEffect(() => onDirtyChange?.(dirty), [dirty, onDirtyChange]);
  useEffect(() => () => onDirtyChange?.(false), [onDirtyChange]);

  const updateTarget = (field: keyof TargetDraft, value: string) => setTarget((current) => ({ ...current, [field]: value }));
  const changePlatform = (value: PlatformId) => { setPlatform(value); setTarget(emptyTarget()); };
  const addEnv = () => setEnvRows((rows) => [...rows, { id: nextRowId.current++, name: '', value: '' }]);
  const updateEnv = (id: number, field: 'name' | 'value', value: string) => setEnvRows((rows) => rows.map((row) => row.id === id ? { ...row, [field]: value } : row));
  const deleteEnv = (id: number) => {
    setEnvRows((rows) => rows.filter((row) => row.id !== id));
    setRevealed((current) => { const next = new Set(current); next.delete(id); return next; });
  };

  const validate = (): Record<string, string> | null => {
    if (mode === 'create' && (!name.trim() || !parentPath.trim())) { setFieldError('Workspace name and parent path are required.'); return null; }
    if (platform === 'android' && !target.appId.trim()) { setFieldError('Android App ID is required.'); return null; }
    if (platform === 'web' && !target.browserExecutablePath.trim()) { setFieldError('Web browser executable path is required.'); return null; }
    if (platform === 'windows' && !target.appPath.trim()) { setFieldError('Windows application path is required.'); return null; }
    if (platform === 'macos' && !target.bundleId.trim() && !target.appPath.trim()) { setFieldError('macOS Bundle ID or application path is required.'); return null; }
    const env: Record<string, string> = {};
    for (const row of envRows) {
      if (!/^[A-Za-z_][A-Za-z0-9_]*$/.test(row.name)) { setFieldError('Environment names must use letters, digits, and underscores and cannot start with a digit.'); return null; }
      if (!row.value.trim()) { setFieldError(`Environment value for ${row.name} cannot be blank.`); return null; }
      if (row.name in env) { setFieldError(`Environment name ${row.name} is duplicated.`); return null; }
      env[row.name] = row.value;
    }
    setFieldError('');
    return env;
  };

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    const env = validate();
    if (!env) { firstField.current?.focus(); return; }
    setPending(true);
    setError(null);
    try {
      const saved = mode === 'create'
        ? await controlPlaneClient.createWorkspace({ name: name.trim(), parentPath: parentPath.trim(), platform, target: targetPayload(platform, target), env })
        : await controlPlaneClient.updateWorkspace(detail!.name, { target: targetPayload(platform, target), env, expectedRevision: detail!.revision });
      onSaved(saved);
    } catch (reason) {
      setError(toApiError(reason));
      if (reason instanceof ControlPlaneApiError && reason.body.code !== 'workspace_conflict') firstField.current?.focus();
    } finally {
      setPending(false);
    }
  };

  return <form className="cp-workspace-form" onSubmit={submit}>
    <fieldset disabled={pending}>
      <legend>{mode === 'create' ? 'Create workspace' : 'Edit workspace'}</legend>
      {mode === 'create' ? <div className="cp-form-grid cp-form-grid--identity">
        <label><span>Workspace name</span><input ref={firstField} value={name} onChange={(event) => setName(event.target.value)} autoComplete="off" /></label>
        <label><span>Parent path</span><input value={parentPath} onChange={(event) => setParentPath(event.target.value)} placeholder="C:\\projects" autoComplete="off" /></label>
        <label className="cp-path-preview"><span>Final path</span><output>{finalPath(parentPath, name) || 'Complete the name and parent path'}</output></label>
        <label><span>Platform</span><select value={platform} onChange={(event) => changePlatform(event.target.value as PlatformId)}><option value="android">Android</option><option value="web">Web</option><option value="windows">Windows</option><option value="macos">macOS</option></select></label>
      </div> : <dl className="cp-workspace-immutable"><div><dt>Name</dt><dd>{detail!.name}</dd></div><div><dt>Root</dt><dd className="mono">{detail!.rootPath}</dd></div><div><dt>Platform</dt><dd>{detail!.platform}</dd></div></dl>}

      <section className="cp-form-section"><div><h3>Target</h3><p>Identify the local application FSQ should operate.</p></div><div className="cp-form-grid">
        {platform === 'android' && <label><span>App ID</span><input ref={mode === 'edit' ? firstField : undefined} value={target.appId} onChange={(event) => updateTarget('appId', event.target.value)} placeholder="com.example.app" /></label>}
        {platform === 'web' && <label className="cp-field-wide"><span>Web path</span><input ref={mode === 'edit' ? firstField : undefined} value={target.browserExecutablePath} onChange={(event) => updateTarget('browserExecutablePath', event.target.value)} placeholder="Browser executable path" /></label>}
        {platform === 'windows' && <><label className="cp-field-wide"><span>App path</span><input ref={mode === 'edit' ? firstField : undefined} value={target.appPath} onChange={(event) => updateTarget('appPath', event.target.value)} /></label><label><span>Window title regex <small>Optional</small></span><input value={target.windowTitleRe} onChange={(event) => updateTarget('windowTitleRe', event.target.value)} /></label><label><span>Launch args <small>Optional</small></span><input value={target.launchArgs} onChange={(event) => updateTarget('launchArgs', event.target.value)} /></label></>}
        {platform === 'macos' && <><label><span>Bundle ID</span><input ref={mode === 'edit' ? firstField : undefined} value={target.bundleId} onChange={(event) => updateTarget('bundleId', event.target.value)} placeholder="com.example.App" /></label><label><span>App path</span><input value={target.appPath} onChange={(event) => updateTarget('appPath', event.target.value)} /></label></>}
      </div></section>

      <details className="cp-env-disclosure" open={mode === 'edit'}><summary>Environment <span>{envRows.length ? `${envRows.length} configured` : 'Optional'}</span></summary><div className="cp-env-content"><p>Values remain local and are masked by default.</p>{envRows.map((row) => <div className="cp-env-row" key={row.id}><label><span>Name</span><input value={row.name} onChange={(event) => updateEnv(row.id, 'name', event.target.value)} placeholder="TEST_PASSWORD" autoComplete="off" /></label><label><span>Value</span><span className="cp-secret-input"><input type={revealed.has(row.id) ? 'text' : 'password'} value={row.value} onChange={(event) => updateEnv(row.id, 'value', event.target.value)} autoComplete="new-password" /><button type="button" aria-label={`${revealed.has(row.id) ? 'Hide' : 'Show'} value for ${row.name || 'environment row'}`} onClick={() => setRevealed((current) => { const next = new Set(current); next.has(row.id) ? next.delete(row.id) : next.add(row.id); return next; })}>{revealed.has(row.id) ? <EyeOff aria-hidden="true" /> : <Eye aria-hidden="true" />}</button></span></label><button className="cp-icon-button cp-delete-env" type="button" aria-label={`Delete ${row.name || 'environment row'}`} onClick={() => deleteEnv(row.id)}><Trash2 aria-hidden="true" /></button></div>)}<button className="button" type="button" onClick={addEnv}><Plus aria-hidden="true" />Add environment value</button></div></details>

      {fieldError && <p className="cp-form-error" role="alert"><AlertCircle aria-hidden="true" />{fieldError}</p>}
      {error && <div className="cp-form-error cp-form-error--server" role="alert"><AlertCircle aria-hidden="true" /><span><strong>{error.message}</strong><small>{error.action}</small></span>{error.code === 'workspace_conflict' && onReloadLatest && <button className="button" type="button" onClick={onReloadLatest}><RefreshCw aria-hidden="true" />Reload latest</button>}</div>}
      <div className="cp-form-actions"><button className="button" type="button" onClick={onCancel}>Cancel</button><button className="button button--primary" type="submit">{pending ? 'Saving…' : mode === 'create' ? 'Create workspace' : 'Save changes'}</button></div>
    </fieldset>
  </form>;
}