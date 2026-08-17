import type { KeyboardEvent } from 'react';
import type { EvidenceTab, PlatformId, RunSnapshot } from '../../../api/types';
import { RunLogsView } from './RunLogsView';
import { ReplayVideoView } from './ReplayVideoView';
import { ScreenView } from './ScreenView';
import { StepEvidenceView } from './StepEvidenceView';
import { UiSnapshotView } from './UiSnapshotView';

const tabs: { id: EvidenceTab; label: string }[] = [
  { id: 'screen', label: 'Screen' }, { id: 'ui-tree', label: 'UI Tree' }, { id: 'logs', label: 'Logs' },
];

interface LiveEvidencePanelProps {
  tab: EvidenceTab;
  snapshot: RunSnapshot | null;
  selectedStepId?: string | null;
  platform: PlatformId;
  targetLabel: string;
  onTabChange: (tab: EvidenceTab) => void;
  onClearStep?: () => void;
}

export function LiveEvidencePanel({ tab, snapshot, selectedStepId = null, platform, targetLabel, onTabChange, onClearStep = () => undefined }: LiveEvidencePanelProps) {
  const onTabKeyDown = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
    event.preventDefault();
    const next = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : (index + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length;
    onTabChange(tabs[next].id);
    document.getElementById(`evidence-tab-${tabs[next].id}`)?.focus();
  };
  return <section className="evidence-card" aria-labelledby="live-evidence-title">
    <header className="card-header evidence-header"><div><h2 id="live-evidence-title">Live evidence</h2><p>{platform} · {selectedStepId ? `Action ${selectedStepId}` : targetLabel || 'No target selected'}</p></div>
      {selectedStepId && <button className="button evidence-replay-button" type="button" onClick={onClearStep}>Show run replay</button>}
      <div className="evidence-tabs" role="tablist" aria-label="Live evidence views">
        {tabs.map((item, index) => <button id={`evidence-tab-${item.id}`} key={item.id} type="button" role="tab" aria-selected={tab === item.id} aria-controls={`evidence-panel-${item.id}`} tabIndex={tab === item.id ? 0 : -1} onClick={() => onTabChange(item.id)} onKeyDown={(event) => onTabKeyDown(event, index)}>{item.label}</button>)}
      </div>
    </header>
    <div className="evidence-surface" id={`evidence-panel-${tab}`} role="tabpanel" aria-labelledby={`evidence-tab-${tab}`}>
      {tab === 'screen' && (snapshot?.terminal
        ? selectedStepId ? <StepEvidenceView requestId={snapshot.requestId} stepId={selectedStepId} kind="screen" platform={platform} /> : <ReplayVideoView requestId={snapshot.requestId} />
        : <ScreenView requestId={snapshot?.requestId ?? null} revision={snapshot?.screenshotRevision ?? 0} platform={platform} targetLabel={targetLabel} />)}
      {tab === 'ui-tree' && (snapshot?.terminal && selectedStepId
        ? <StepEvidenceView requestId={snapshot.requestId} stepId={selectedStepId} kind="ui-tree" platform={platform} />
        : <UiSnapshotView requestId={snapshot?.requestId ?? null} revision={snapshot?.uiSnapshotRevision ?? 0} />)}
      {tab === 'logs' && <RunLogsView events={snapshot?.events ?? []} active={Boolean(snapshot && !snapshot.terminal)} />}
    </div>
    <footer className="evidence-footer"><span>{snapshot?.evidenceAvailable ? 'Evidence captured' : 'Awaiting evidence'}</span><span>{snapshot?.runId ? `Run ${snapshot.runId}` : 'No run allocated'}</span></footer>
  </section>;
}
