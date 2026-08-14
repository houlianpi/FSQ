import { createRef } from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
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
    source: { casePath: 'flow.fsq.yaml' }, startedAt: '', completedAt: null, cancelRequested: false,
    events: [], activeStep: null, result: null, summary: 'Finalizing', screenshotRevision: 0, uiSnapshotRevision: 0,
    evidenceAvailable: false, reportAvailable: false, terminal: false,
  };
  const { rerender } = render(<RunTimeline snapshot={active} connection="live" resultHeadingRef={createRef()} onCancel={onCancel} onNewRun={vi.fn()} />);
  await userEvent.click(screen.getByRole('button', { name: 'Cancel run' }));
  expect(onCancel).toHaveBeenCalledOnce();
  rerender(<RunTimeline snapshot={{ ...active, cancelRequested: true }} connection="live" resultHeadingRef={createRef()} onCancel={onCancel} onNewRun={vi.fn()} />);
  expect(screen.getByRole('button', { name: /Cancellation requested/ })).toBeDisabled();
});

it('groups contiguous phases, expands the latest group, and discloses long messages', async () => {
  const longMessage = 'A detailed safe planning message '.repeat(8);
  const active: RunSnapshot = {
    requestId: 'request', runId: 'run-1', platform: 'web', targetId: 'chrome', mode: 'explore', status: 'running',
    source: { goal: 'Verify' }, startedAt: '', completedAt: null, cancelRequested: false,
    events: [
      { sequence: 1, phase: 'startup', label: 'First startup', status: 'completed', message: 'Ready' },
      { sequence: 2, phase: 'startup', label: 'Second startup', status: 'completed', message: 'Ready' },
      { sequence: 3, phase: 'planning', label: 'Plan', status: 'completed', message: 'Planned' },
      { sequence: 4, phase: 'startup', label: 'Latest startup', status: 'running', message: longMessage },
    ], activeStep: null, result: null, summary: 'Running', screenshotRevision: 0, uiSnapshotRevision: 0,
    evidenceAvailable: false, reportAvailable: false, terminal: false,
  };
  const { rerender } = render(<RunTimeline snapshot={active} connection="live" resultHeadingRef={createRef()} onCancel={vi.fn()} onNewRun={vi.fn()} />);

  const startupGroups = screen.getAllByRole('button', { name: /Startup/ });
  expect(startupGroups).toHaveLength(2);
  expect(startupGroups[0]).toHaveAttribute('aria-expanded', 'false');
  expect(document.getElementById(startupGroups[0].getAttribute('aria-controls') ?? '')).toHaveAttribute('hidden');
  expect(startupGroups[1]).toHaveAttribute('aria-expanded', 'true');
  expect(screen.getByText('Latest startup')).toBeInTheDocument();
  expect(screen.getByText('First startup')).not.toBeVisible();

  await userEvent.click(startupGroups[0]);
  expect(screen.getByText('First startup')).toBeInTheDocument();
  rerender(<RunTimeline snapshot={{ ...active, events: [...active.events, { sequence: 5, phase: 'verification', label: 'Verify', status: 'running' }] }} connection="live" resultHeadingRef={createRef()} onCancel={vi.fn()} onNewRun={vi.fn()} />);
  expect(screen.getByText('First startup')).toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: /Startup1 eventrunning/ }));
  const disclosure = screen.getByRole('button', { name: 'Expand message' });
  expect(disclosure).toHaveAttribute('aria-expanded', 'false');
  await userEvent.click(disclosure);
  expect(disclosure).toHaveTextContent('Collapse message');
  expect(disclosure).toHaveAttribute('aria-expanded', 'true');
});

it('pauses timeline following and jumps to appended events', async () => {
  const active: RunSnapshot = {
    requestId: 'request', runId: 'run-1', platform: 'web', targetId: 'chrome', mode: 'explore', status: 'running',
    source: { goal: 'Verify' }, startedAt: '', completedAt: null, cancelRequested: false,
    events: [{ sequence: 1, phase: 'run', label: 'Started', status: 'running' }], activeStep: null,
    result: null, summary: 'Running', screenshotRevision: 0, uiSnapshotRevision: 0, evidenceAvailable: false, reportAvailable: false, terminal: false,
  };
  const { container, rerender } = render(<RunTimeline snapshot={active} connection="live" resultHeadingRef={createRef()} onCancel={vi.fn()} onNewRun={vi.fn()} />);
  const scrolling = container.querySelector('.timeline-scroll') as HTMLDivElement;
  const scrollTo = vi.fn();
  Object.defineProperties(scrolling, { scrollHeight: { configurable: true, value: 1000 }, clientHeight: { configurable: true, value: 200 }, scrollTop: { configurable: true, value: 0, writable: true }, scrollTo: { configurable: true, value: scrollTo } });
  fireEvent.scroll(scrolling);

  rerender(<RunTimeline snapshot={{ ...active, events: [...active.events, { sequence: 2, phase: 'run', label: 'Next', status: 'running' }] }} connection="live" resultHeadingRef={createRef()} onCancel={vi.fn()} onNewRun={vi.fn()} />);
  rerender(<RunTimeline snapshot={{ ...active, events: [...active.events, { sequence: 2, phase: 'run', label: 'Next', status: 'running' }, { sequence: 3, phase: 'run', label: 'Another', status: 'running' }] }} connection="live" resultHeadingRef={createRef()} onCancel={vi.fn()} onNewRun={vi.fn()} />);
  const jump = await screen.findByRole('button', { name: 'Jump to latest · 2 new' });
  expect(scrollTo).not.toHaveBeenCalled();
  await userEvent.click(jump);
  expect(scrollTo).toHaveBeenCalled();
  expect(jump).toHaveFocus();
  fireEvent.blur(jump);
  await waitFor(() => expect(screen.queryByRole('button', { name: /Jump to latest/ })).not.toBeInTheDocument());
});
