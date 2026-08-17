import { render, screen } from '@testing-library/react';
import type { RunSnapshot } from '../../api/types';
import { DevicesPage } from './DevicesPage';
import { useDeviceWorkspace } from './hooks/useDeviceWorkspace';

vi.mock('./hooks/useDeviceWorkspace', () => ({ useDeviceWorkspace: vi.fn() }));

it('announces live run truth and locks target controls without moving focus', () => {
  const snapshot: RunSnapshot = {
    requestId: 'request-1', runId: 'run-1', platform: 'web', targetId: 'chrome', mode: 'explore', status: 'running',
    source: { goal: 'Verify' }, startedAt: '', completedAt: null, cancelRequested: false, events: [], activeStep: null,
    result: null, summary: 'Executing step 1.', screenshotRevision: 0, uiSnapshotRevision: 0,
    evidenceAvailable: false, reportAvailable: false, terminal: false,
  };
  vi.mocked(useDeviceWorkspace).mockReturnValue({
    bootstrap: { state: 'ready', data: { apiVersion: '1.0', platforms: [{ id: 'web', label: 'Web' }], workspace: { name: 'test', initialized: true }, busy: true, activeTask: snapshot }, error: null },
    platform: 'web', setPlatform: vi.fn(), targetId: 'chrome', setTargetId: vi.fn(), mode: 'explore', setMode: vi.fn(), goal: 'Verify', setGoal: vi.fn(), casePath: '', setCasePath: vi.fn(),
    readiness: { state: 'ready', data: null, error: null },
    targets: { state: 'ready', data: { platform: 'web', targetLabel: 'Browser', targets: [{ id: 'chrome', label: 'Chrome', description: 'ready', status: 'ready', selectable: true, isDefault: true, metadata: {} }] }, error: null },
    cases: { state: 'ready', data: { platform: 'web', cases: [], truncated: false }, error: null }, selectedTarget: { id: 'chrome', label: 'Chrome', description: 'ready', status: 'ready', selectable: true, isDefault: true, metadata: {} }, selectedCase: null,
    requestId: 'request-1', snapshot, streamError: null, startError: null, evidenceTab: 'screen', setEvidenceTab: vi.fn(),
    selectedStepId: null, setSelectedStepId: vi.fn(), controlsLocked: true, canStart: false, connection: 'live', connectionLabel: 'Live', refresh: vi.fn(), start: vi.fn(), cancel: vi.fn(), newRun: vi.fn(),
  });

  render(<DevicesPage renderShell={(toolbar, content) => <>{toolbar}{content}</>} />);

  expect(screen.getByLabelText('Platform')).toBeDisabled();
  expect(screen.getByLabelText('Browser')).toBeDisabled();
  expect(document.querySelector('[aria-live="polite"]')).toHaveTextContent('Run running. Executing step 1. Live.');
  expect(document.body).toHaveFocus();
});