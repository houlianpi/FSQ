import type { PlatformId, PlatformOption, TargetsResponse } from '../../../api/types';

interface TargetToolbarProps {
  platforms: readonly PlatformOption[];
  platform: PlatformId;
  targetId: string;
  targets: TargetsResponse | null;
  locked: boolean;
  loading: boolean;
  connectionLabel: string;
  onPlatformChange: (platform: PlatformId) => void;
  onTargetChange: (targetId: string) => void;
  onRefresh: () => void;
}

const defaultPlatforms: PlatformOption[] = [
  { id: 'android', label: 'Android' }, { id: 'web', label: 'Web' },
  { id: 'windows', label: 'Windows' }, { id: 'macos', label: 'macOS' },
];

export function TargetToolbar({ platforms, platform, targetId, targets, locked, loading, connectionLabel, onPlatformChange, onTargetChange, onRefresh }: TargetToolbarProps) {
  return <div className="target-toolbar">
    <label className="toolbar-select"><span>Platform</span>
      <select aria-label="Platform" value={platform} disabled={locked} onChange={(event) => onPlatformChange(event.target.value as PlatformId)}>
        {(platforms.length ? platforms : defaultPlatforms).map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
      </select>
    </label>
    <label className="toolbar-select toolbar-select--target"><span>{targets?.targetLabel ?? (platform === 'android' ? 'Device' : platform === 'web' ? 'Browser' : 'Application')}</span>
      <select aria-label={targets?.targetLabel ?? 'Target'} value={targetId} disabled={locked || loading} onChange={(event) => onTargetChange(event.target.value)}>
        <option value="">{loading ? 'Discovering…' : 'Select a target'}</option>
        {targets?.targets.map((target) => <option key={target.id} value={target.id} disabled={!target.selectable}>{target.label}{target.selectable ? '' : ` — ${target.status}`}</option>)}
      </select>
    </label>
    <span className={`connection-status connection-status--${connectionLabel.toLowerCase()}`} role="status"><span aria-hidden="true">●</span>{connectionLabel}</span>
    <button className="button button--secondary" type="button" disabled={locked || loading} onClick={onRefresh} aria-label="Refresh readiness, targets, and cases">↻ Refresh</button>
  </div>;
}
