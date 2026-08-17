import { createRef } from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { RunSnapshot } from '../../../api/types';
import { RunTimeline } from './RunTimeline';

it('keeps truthful terminal timeline, separates terminal actions, and selects actions', async () => {
  const onSelectStep = vi.fn();
  const message = 'Navigation complete with enough detail to require the disclosure control. '.repeat(4);
  const goal = 'Verify the page and keep enough source text available for expansion. '.repeat(3).trim();
  const snapshot: RunSnapshot = {
    requestId: 'request', runId: 'run-1', platform: 'web', targetId: 'chrome', mode: 'explore', status: 'success',
    source: { goal }, startedAt: '', completedAt: '', cancelRequested: false,
    events: [{ sequence: 1, time: '2026-08-14T10:15:30Z', label: 'navigateTo', status: 'completed', message }], activeStep: null,
    result: { status: 'success' }, summary: 'Goal verified.', screenshotRevision: 1, uiSnapshotRevision: 1,
    evidenceAvailable: true, reportAvailable: true, terminal: true,
  };
  render(<RunTimeline snapshot={{ ...snapshot, events: [{ ...snapshot.events[0], stepId: 'step-1' }] }} connection="ended" selectedStepId={null} resultHeadingRef={createRef()} onSelectStep={onSelectStep} onCancel={vi.fn()} onNewRun={vi.fn()} />);
  expect(screen.getByText('navigateTo')).toBeInTheDocument();
  expect(screen.getByText('Run source · Explore').closest('.run-source-summary')).not.toHaveTextContent('success');
  expect(screen.queryByText(/Updates:/)).not.toBeInTheDocument();
  expect(screen.queryByRole('heading', { name: 'Run success' })).not.toBeInTheDocument();
  const sourceText = screen.getByText(goal);
  expect(sourceText.closest('.run-source-summary')).not.toHaveClass('run-source-summary--expanded');
  expect(screen.getByRole('button', { name: 'Expand run source' }).closest('.run-source-line')).toContainElement(sourceText);
  await userEvent.click(screen.getByRole('button', { name: 'Expand run source' }));
  expect(sourceText.closest('.run-source-summary')).toHaveClass('run-source-summary--expanded');
  await userEvent.click(screen.getByRole('button', { name: 'Collapse run source' }));
  expect(sourceText.closest('.run-source-summary')).not.toHaveClass('run-source-summary--expanded');
  expect(screen.getByRole('button', { name: 'Select action navigateTo' })).not.toHaveTextContent(/\d{1,2}:\d{2}/);
  expect(screen.getByRole('button', { name: 'Save yaml' })).toBeDisabled();
  expect(screen.getByRole('button', { name: 'New run' })).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: /Cancel/ })).not.toBeInTheDocument();
  const disclosure = await screen.findByRole('button', { name: 'Expand message' });
  await userEvent.click(disclosure);
  expect(onSelectStep).not.toHaveBeenCalled();
  await userEvent.click(document.getElementById('timeline-message-1') as HTMLElement);
  expect(onSelectStep).toHaveBeenCalledWith('step-1');
  expect(onSelectStep).toHaveBeenCalledOnce();
});

it('offers cancellation through finalizing and locks repeated cancellation', async () => {
  const onCancel = vi.fn();
  const active: RunSnapshot = {
    requestId: 'request', runId: 'run-1', platform: 'web', targetId: 'chrome', mode: 'strict', status: 'finalizing',
    source: { casePath: 'flow.codex.yaml' }, startedAt: '', completedAt: null, cancelRequested: false,
    events: [], activeStep: null, result: null, summary: 'Finalizing', screenshotRevision: 0, uiSnapshotRevision: 0,
    evidenceAvailable: false, reportAvailable: false, terminal: false,
  };
  const { rerender } = render(<RunTimeline snapshot={active} connection="live" selectedStepId={null} resultHeadingRef={createRef()} onSelectStep={vi.fn()} onCancel={onCancel} onNewRun={vi.fn()} />);
  await userEvent.click(screen.getByRole('button', { name: 'Cancel run' }));
  expect(onCancel).toHaveBeenCalledOnce();
  rerender(<RunTimeline snapshot={{ ...active, cancelRequested: true }} connection="live" selectedStepId={null} resultHeadingRef={createRef()} onSelectStep={vi.fn()} onCancel={onCancel} onNewRun={vi.fn()} />);
  expect(screen.getByRole('button', { name: /Cancellation requested/ })).toBeDisabled();
});

it('renders a flat sequence-ordered event list and discloses long messages', async () => {
  const longMessage = 'A detailed safe planning message '.repeat(8);
  const active: RunSnapshot = {
    requestId: 'request', runId: 'run-1', platform: 'web', targetId: 'chrome', mode: 'explore', status: 'running',
    source: { goal: 'Verify' }, startedAt: '', completedAt: null, cancelRequested: false,
    events: [
      { sequence: 4, phase: 'startup', label: 'Latest startup', status: 'running', message: longMessage },
      { sequence: 2, phase: 'startup', label: 'Second startup', status: 'completed', message: 'Ready' },
      { sequence: 1, phase: 'startup', label: 'First startup', status: 'completed', message: 'Ready' },
      { sequence: 3, time: '2026-08-14T10:15:30Z', phase: 'planning', label: 'Plan', message: 'Planned' },
    ], activeStep: null, result: null, summary: 'Running', screenshotRevision: 0, uiSnapshotRevision: 0,
    evidenceAvailable: false, reportAvailable: false, terminal: false,
  };
  const { container } = render(<RunTimeline snapshot={active} connection="live" selectedStepId={null} resultHeadingRef={createRef()} onSelectStep={vi.fn()} onCancel={vi.fn()} onNewRun={vi.fn()} />);

  expect(container.querySelector('.timeline-group')).not.toBeInTheDocument();
  expect(container.querySelector('.timeline-group-toggle')).not.toBeInTheDocument();
  expect(screen.getAllByRole('listitem').map((item) => item.querySelector('strong')?.textContent)).toEqual([
    'First startup',
    'Second startup',
    'Plan',
    'Latest startup',
  ]);
  expect(screen.getByText('Latest startup').closest('li')?.querySelector('.status-badge')).toHaveTextContent('running');
  expect(screen.getByText('Plan').closest('li')?.querySelector('.status-badge')).toBeNull();
  expect(screen.getByText('Plan').closest('li')).not.toHaveTextContent(/\d{1,2}:\d{2}/);
  expect(screen.getByText('Plan').closest('li')).not.toHaveClass('timeline-row--running');
  const disclosure = await screen.findByRole('button', { name: 'Expand message' });
  expect(disclosure).toHaveTextContent('⌄');
  expect(disclosure).toHaveAttribute('aria-expanded', 'false');
  await userEvent.click(disclosure);
  expect(disclosure).toHaveTextContent('⌃');
  expect(disclosure).toHaveAttribute('aria-expanded', 'true');
  await userEvent.click(disclosure);
  expect(disclosure).toHaveTextContent('⌄');
  expect(disclosure).toHaveAttribute('aria-expanded', 'false');
});

it('highlights only the active running action and clears active highlighting after terminal selection', async () => {
  const snapshot: RunSnapshot = {
    requestId: 'request', runId: 'run-1', platform: 'web', targetId: 'chrome', mode: 'explore', status: 'running',
    source: { goal: 'Verify' }, startedAt: '', completedAt: null, cancelRequested: false,
    events: [
      { sequence: 1, label: 'First', stepId: 'step-1', status: 'completed' },
      { sequence: 2, label: 'Second', stepId: 'step-2', status: 'running' },
    ], activeStep: { stepId: 'step-2', label: 'Second' }, result: null, summary: 'Running', screenshotRevision: 0, uiSnapshotRevision: 0,
    evidenceAvailable: false, reportAvailable: false, terminal: false,
  };
  const { rerender } = render(<RunTimeline snapshot={snapshot} connection="live" selectedStepId={null} resultHeadingRef={createRef()} onSelectStep={vi.fn()} onCancel={vi.fn()} onNewRun={vi.fn()} />);

  expect(screen.getByText('Second').closest('li')).toHaveClass('timeline-row--active');
  expect(screen.getByText('First').closest('li')).not.toHaveClass('timeline-row--active');

  rerender(<RunTimeline snapshot={{ ...snapshot, terminal: true, status: 'success', completedAt: 'now' }} connection="ended" selectedStepId="step-2" resultHeadingRef={createRef()} onSelectStep={vi.fn()} onCancel={vi.fn()} onNewRun={vi.fn()} />);
  expect(screen.getByText('Second').closest('li')).not.toHaveClass('timeline-row--active');
  expect(screen.getByText('Second').closest('li')).toHaveClass('timeline-row--selected');
});

it('moves active highlighting to newer non-step progress after an active action', () => {
  const snapshot: RunSnapshot = {
    requestId: 'request', runId: 'run-1', platform: 'web', targetId: 'chrome', mode: 'explore', status: 'running',
    source: { goal: 'Verify' }, startedAt: '', completedAt: null, cancelRequested: false,
    events: [
      { sequence: 28, label: 'assert_with_ai', stepId: 'step-assert', status: 'completed', message: 'Tool returned output.' },
      { sequence: 29, label: 'Agent message', message: '{"status":"success"}' },
      { sequence: 30, label: 'Verification started', status: 'running', message: 'Running evidence-based verifier agent.' },
      { sequence: 31, label: 'Agent updated', message: 'fsq-agent verifier' },
    ], activeStep: { stepId: 'step-assert', label: 'assert_with_ai' }, result: null, summary: 'Running', screenshotRevision: 0, uiSnapshotRevision: 0,
    evidenceAvailable: false, reportAvailable: false, terminal: false,
  };
  render(<RunTimeline snapshot={snapshot} connection="live" selectedStepId={null} resultHeadingRef={createRef()} onSelectStep={vi.fn()} onCancel={vi.fn()} onNewRun={vi.fn()} />);

  expect(screen.getByText('assert_with_ai').closest('li')).not.toHaveClass('timeline-row--active');
  expect(screen.getByText('Verification started').closest('li')).toHaveClass('timeline-row--active');
  expect(screen.getByText('Agent updated').closest('li')).not.toHaveClass('timeline-row--active');
});

it('falls back to the latest running row or latest row when active step cannot match', () => {
  const base: RunSnapshot = {
    requestId: 'request', runId: 'run-1', platform: 'web', targetId: 'chrome', mode: 'explore', status: 'running',
    source: { goal: 'Verify' }, startedAt: '', completedAt: null, cancelRequested: false,
    events: [
      { sequence: 1, label: 'First', status: 'completed' },
      { sequence: 2, label: 'Second', status: 'running' },
      { sequence: 3, label: 'Third' },
    ], activeStep: { stepId: 'missing-step', label: 'Missing' }, result: null, summary: 'Running', screenshotRevision: 0, uiSnapshotRevision: 0,
    evidenceAvailable: false, reportAvailable: false, terminal: false,
  };
  const { rerender } = render(<RunTimeline snapshot={base} connection="live" selectedStepId={null} resultHeadingRef={createRef()} onSelectStep={vi.fn()} onCancel={vi.fn()} onNewRun={vi.fn()} />);

  expect(screen.getByText('Second').closest('li')).toHaveClass('timeline-row--active');
  expect(screen.getByText('Third').closest('li')).not.toHaveClass('timeline-row--active');

  rerender(<RunTimeline snapshot={{ ...base, events: base.events.map((event) => ({ ...event, status: event.status === 'running' ? undefined : event.status })) }} connection="live" selectedStepId={null} resultHeadingRef={createRef()} onSelectStep={vi.fn()} onCancel={vi.fn()} onNewRun={vi.fn()} />);
  expect(screen.getByText('Third').closest('li')).toHaveClass('timeline-row--active');
});

it('pauses timeline following and jumps to appended events', async () => {
  const active: RunSnapshot = {
    requestId: 'request', runId: 'run-1', platform: 'web', targetId: 'chrome', mode: 'explore', status: 'running',
    source: { goal: 'Verify' }, startedAt: '', completedAt: null, cancelRequested: false,
    events: [{ sequence: 1, phase: 'run', label: 'Started', status: 'running' }], activeStep: null,
    result: null, summary: 'Running', screenshotRevision: 0, uiSnapshotRevision: 0, evidenceAvailable: false, reportAvailable: false, terminal: false,
  };
  const { container, rerender } = render(<RunTimeline snapshot={active} connection="live" selectedStepId={null} resultHeadingRef={createRef()} onSelectStep={vi.fn()} onCancel={vi.fn()} onNewRun={vi.fn()} />);
  const scrolling = container.querySelector('.timeline-scroll') as HTMLDivElement;
  const scrollTo = vi.fn();
  Object.defineProperties(scrolling, { scrollHeight: { configurable: true, value: 1000 }, clientHeight: { configurable: true, value: 200 }, scrollTop: { configurable: true, value: 0, writable: true }, scrollTo: { configurable: true, value: scrollTo } });
  fireEvent.scroll(scrolling);

  rerender(<RunTimeline snapshot={{ ...active, events: [...active.events, { sequence: 2, phase: 'run', label: 'Next', status: 'running' }] }} connection="live" selectedStepId={null} resultHeadingRef={createRef()} onSelectStep={vi.fn()} onCancel={vi.fn()} onNewRun={vi.fn()} />);
  rerender(<RunTimeline snapshot={{ ...active, events: [...active.events, { sequence: 2, phase: 'run', label: 'Next', status: 'running' }, { sequence: 3, phase: 'run', label: 'Another', status: 'running' }] }} connection="live" selectedStepId={null} resultHeadingRef={createRef()} onSelectStep={vi.fn()} onCancel={vi.fn()} onNewRun={vi.fn()} />);
  const jump = await screen.findByRole('button', { name: 'Jump to latest · 2 new' });
  rerender(<RunTimeline snapshot={{ ...active, terminal: true, status: 'success' }} connection="ended" selectedStepId={null} resultHeadingRef={createRef()} onSelectStep={vi.fn()} onCancel={vi.fn()} onNewRun={vi.fn()} />);
  expect(screen.queryByRole('button', { name: /Jump to latest/ })).not.toBeInTheDocument();
  rerender(<RunTimeline snapshot={{ ...active, events: [...active.events, { sequence: 2, phase: 'run', label: 'Next', status: 'running' }, { sequence: 3, phase: 'run', label: 'Another', status: 'running' }] }} connection="live" selectedStepId={null} resultHeadingRef={createRef()} onSelectStep={vi.fn()} onCancel={vi.fn()} onNewRun={vi.fn()} />);
  const activeJump = await screen.findByRole('button', { name: /Jump to latest/ });
  expect(scrolling.scrollTop).toBe(0);
  await userEvent.click(activeJump);
  expect(scrolling.scrollTop).toBe(scrolling.scrollHeight - scrolling.clientHeight);
  expect(scrollTo).not.toHaveBeenCalled();
  await waitFor(() => expect(screen.queryByRole('button', { name: /Jump to latest/ })).not.toBeInTheDocument());
  expect(scrolling).toHaveFocus();
});
