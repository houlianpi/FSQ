import { createRef } from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { RunSnapshot } from '../../../api/types';
import { RunTimeline } from './RunTimeline';

it('keeps truthful terminal timeline and focuses the result heading', () => {
  const snapshot: RunSnapshot = {
    requestId: 'request', runId: 'run-1', platform: 'web', targetId: 'chrome', mode: 'explore', status: 'success',
    source: { goal: 'Verify the page' }, startedAt: '', completedAt: '', cancelRequested: false,
    events: [{ sequence: 1, label: 'navigateTo', status: 'completed', message: 'Navigation complete' }], activeStep: null,
    result: { status: 'success' }, summary: 'Goal verified.', screenshotRevision: 1, uiSnapshotRevision: 1,
    evidenceAvailable: true, reportAvailable: true, terminal: true,
  };
  render(<RunTimeline snapshot={snapshot} connection="ended" resultHeadingRef={createRef()} onCancel={vi.fn()} onNewRun={vi.fn()} />);
  expect(screen.getByText('navigateTo')).toBeInTheDocument();
  expect(screen.getByRole('heading', { name: 'Run success' })).toHaveFocus();
  expect(screen.getByRole('button', { name: 'New run' })).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: /Cancel/ })).not.toBeInTheDocument();
});

it('offers cancellation through finalizing and locks repeated cancellation', async () => {
  const onCancel = vi.fn();
  const active: RunSnapshot = {
    requestId: 'request', runId: 'run-1', platform: 'web', targetId: 'chrome', mode: 'strict', status: 'finalizing',
    source: { casePath: 'flow.codex.yaml' }, startedAt: '', completedAt: null, cancelRequested: false,
    events: [], activeStep: null, result: null, summary: 'Finalizing', screenshotRevision: 0, uiSnapshotRevision: 0,
    evidenceAvailable: false, reportAvailable: false, terminal: false,
  };
  const { rerender } = render(<RunTimeline snapshot={active} connection="live" resultHeadingRef={createRef()} onCancel={onCancel} onNewRun={vi.fn()} />);
  await userEvent.click(screen.getByRole('button', { name: 'Cancel run' }));
  expect(onCancel).toHaveBeenCalledOnce();
  rerender(<RunTimeline snapshot={{ ...active, cancelRequested: true }} connection="live" resultHeadingRef={createRef()} onCancel={onCancel} onNewRun={vi.fn()} />);
  expect(screen.getByRole('button', { name: /Cancellation requested/ })).toBeDisabled();
});
