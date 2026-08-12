import type { ReadinessRecord, RunMode } from '../../../api/types';

interface PreflightStatusProps {
  mode: RunMode;
  workspace?: ReadinessRecord;
  provider?: ReadinessRecord;
  target?: ReadinessRecord;
  strict?: ReadinessRecord;
  requiresProvider?: boolean;
  loading: boolean;
}

function PreflightItem({ label, record, loading }: { label: string; record?: ReadinessRecord; loading: boolean }) {
  const status = loading ? 'loading' : record?.status ?? 'unavailable';
  const detail = loading ? 'Checking readiness…' : record?.message ?? 'Readiness is unavailable.';
  return <li className={`preflight-item preflight-item--${status}`}>
    <span className="preflight-icon" aria-hidden="true">{status === 'ready' ? '✓' : status === 'loading' ? '…' : '!'}</span>
    <span><strong>{label}</strong><small>{detail}</small>{record?.action && status !== 'ready' && <small className="preflight-action">{record.action}</small>}</span>
  </li>;
}

export function PreflightStatus({ mode, workspace, provider, target, strict, requiresProvider, loading }: PreflightStatusProps) {
  return <section className="preflight" aria-labelledby="preflight-title">
    <h3 id="preflight-title">Preflight</h3>
    <ul>
      <PreflightItem label="Target" record={target} loading={loading} />
      <PreflightItem label="Workspace" record={workspace} loading={loading} />
      <PreflightItem label={mode === 'explore' || requiresProvider ? 'Provider' : 'Strict runner'} record={mode === 'explore' || requiresProvider ? provider : strict} loading={loading} />
    </ul>
  </section>;
}
