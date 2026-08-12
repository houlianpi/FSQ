import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ControlPlaneApiError, controlPlaneClient } from '../../../api/controlPlaneClient';
import type { RunSnapshot } from '../../../api/types';
import { LiveEvidencePanel } from './LiveEvidencePanel';

const snapshot: RunSnapshot = {
  requestId: 'request', runId: 'run', platform: 'web', targetId: 'chrome', mode: 'explore', status: 'running',
  source: { goal: 'Verify' }, startedAt: '', completedAt: null, cancelRequested: false,
  events: [{ sequence: 1, time: '2026-08-11T12:00:00Z', level: 'info', phase: 'execution', tool: 'clickOn', status: 'completed', message: 'Clicked safely' }],
  activeStep: null, result: null, summary: 'Running', screenshotRevision: 0, uiSnapshotRevision: 0,
  evidenceAvailable: false, reportAvailable: false, terminal: false,
};

it('provides keyboard-operable evidence tabs and structured logs', async () => {
  const onTabChange = vi.fn();
  const { rerender } = render(<LiveEvidencePanel tab="screen" snapshot={snapshot} platform="web" targetLabel="Chrome" onTabChange={onTabChange} />);
  const screenTab = screen.getByRole('tab', { name: 'Screen' });
  screenTab.focus();
  await userEvent.keyboard('{ArrowRight}');
  expect(onTabChange).toHaveBeenCalledWith('ui-tree');
  await userEvent.keyboard('{End}');
  expect(onTabChange).toHaveBeenCalledWith('logs');
  await userEvent.keyboard('{Home}');
  expect(onTabChange).toHaveBeenCalledWith('screen');
  rerender(<LiveEvidencePanel tab="logs" snapshot={snapshot} platform="web" targetLabel="Chrome" onTabChange={onTabChange} />);
  expect(screen.getByRole('table', { name: 'Structured run logs' })).toBeInTheDocument();
  expect(screen.getByText('Clicked safely')).toBeInTheDocument();
  expect(screen.queryByText(JSON.stringify(snapshot.events[0]))).not.toBeInTheDocument();
});

it('distinguishes screen loading, unavailable, failed, and available states', async () => {
  let resolveScreen!: (blob: Blob) => void;
  vi.spyOn(controlPlaneClient, 'screen').mockReturnValue(new Promise((resolve) => { resolveScreen = resolve; }));
  vi.stubGlobal('URL', { ...URL, createObjectURL: vi.fn(() => 'blob:screen'), revokeObjectURL: vi.fn() });
  const revised = { ...snapshot, screenshotRevision: 1 };
  const { rerender } = render(<LiveEvidencePanel tab="screen" snapshot={revised} platform="web" targetLabel="Chrome" onTabChange={vi.fn()} />);
  expect(screen.getByText('Loading screen')).toBeInTheDocument();
  resolveScreen(new Blob(['png'], { type: 'image/png' }));
  expect(await screen.findByRole('img', { name: /screenshot evidence/i })).toHaveAttribute('src', 'blob:screen');

  vi.mocked(controlPlaneClient.screen).mockRejectedValueOnce(new ControlPlaneApiError(404, { code: 'evidence_unavailable', message: 'missing', action: 'wait' }));
  rerender(<LiveEvidencePanel tab="screen" snapshot={{ ...revised, screenshotRevision: 2 }} platform="web" targetLabel="Chrome" onTabChange={vi.fn()} />);
  expect(await screen.findByText('Screen unavailable')).toBeInTheDocument();
  vi.mocked(controlPlaneClient.screen).mockRejectedValueOnce(new Error('broken'));
  rerender(<LiveEvidencePanel tab="screen" snapshot={{ ...revised, screenshotRevision: 3 }} platform="web" targetLabel="Chrome" onTabChange={vi.fn()} />);
  expect(await screen.findByRole('alert')).toHaveTextContent('Screen failed to load');
  vi.unstubAllGlobals();
});

it('distinguishes UI Tree loading, unavailable, oversized, failed, and available states', async () => {
  let resolveTree!: (value: Awaited<ReturnType<typeof controlPlaneClient.uiSnapshot>>) => void;
  vi.spyOn(controlPlaneClient, 'uiSnapshot').mockReturnValue(new Promise((resolve) => { resolveTree = resolve; }));
  const revised = { ...snapshot, uiSnapshotRevision: 1 };
  const { rerender } = render(<LiveEvidencePanel tab="ui-tree" snapshot={revised} platform="web" targetLabel="Chrome" onTabChange={vi.fn()} />);
  expect(screen.getByText('Loading UI Tree')).toBeInTheDocument();
  resolveTree({ revision: 1, timestamp: null, stepId: 'step-1', mimeType: 'application/json', format: 'json', content: '{"safe":true}' });
  expect(await screen.findByText('{"safe":true}')).toBeInTheDocument();

  vi.mocked(controlPlaneClient.uiSnapshot).mockRejectedValueOnce(new ControlPlaneApiError(404, { code: 'evidence_unavailable', message: 'missing', action: 'wait' }));
  rerender(<LiveEvidencePanel tab="ui-tree" snapshot={{ ...revised, uiSnapshotRevision: 2 }} platform="web" targetLabel="Chrome" onTabChange={vi.fn()} />);
  expect(await screen.findByText('UI Tree unavailable')).toBeInTheDocument();
  vi.mocked(controlPlaneClient.uiSnapshot).mockRejectedValueOnce(new ControlPlaneApiError(413, { code: 'evidence_too_large', message: 'large', action: 'inspect' }));
  rerender(<LiveEvidencePanel tab="ui-tree" snapshot={{ ...revised, uiSnapshotRevision: 3 }} platform="web" targetLabel="Chrome" onTabChange={vi.fn()} />);
  expect(await screen.findByText('UI Tree is too large to display')).toBeInTheDocument();
  vi.mocked(controlPlaneClient.uiSnapshot).mockRejectedValueOnce(new Error('broken'));
  rerender(<LiveEvidencePanel tab="ui-tree" snapshot={{ ...revised, uiSnapshotRevision: 4 }} platform="web" targetLabel="Chrome" onTabChange={vi.fn()} />);
  expect(await screen.findByRole('alert')).toHaveTextContent('UI Tree failed to load');
});

it('shows an explicit not-yet-captured screen state', () => {
  render(<LiveEvidencePanel tab="screen" snapshot={snapshot} platform="web" targetLabel="Chrome" onTabChange={vi.fn()} />);
  expect(screen.getByText('Screen not yet captured')).toBeInTheDocument();
});

it('discloses long log messages and resumes paused log following', async () => {
  const longMessage = 'A safe structured agent message '.repeat(8);
  const withLongLog = { ...snapshot, events: [{ ...snapshot.events[0], message: longMessage }] };
  const { container, rerender } = render(<LiveEvidencePanel tab="logs" snapshot={withLongLog} platform="web" targetLabel="Chrome" onTabChange={vi.fn()} />);
  const disclosure = screen.getByRole('button', { name: 'Expand message' });
  await userEvent.click(disclosure);
  expect(disclosure).toHaveTextContent('Collapse message');

  const scrolling = container.querySelector('.logs-table-wrap') as HTMLDivElement;
  const scrollTo = vi.fn();
  Object.defineProperties(scrolling, { scrollHeight: { configurable: true, value: 1000 }, clientHeight: { configurable: true, value: 200 }, scrollTop: { configurable: true, value: 0, writable: true }, scrollTo: { configurable: true, value: scrollTo } });
  fireEvent.scroll(scrolling);
  rerender(<LiveEvidencePanel tab="logs" snapshot={{ ...withLongLog, events: [...withLongLog.events, { sequence: 2, phase: 'execution', message: 'New row' }] }} platform="web" targetLabel="Chrome" onTabChange={vi.fn()} />);

  const jump = await screen.findByRole('button', { name: 'Jump to latest · 1 new' });
  expect(scrollTo).not.toHaveBeenCalled();
  await userEvent.click(jump);
  expect(scrollTo).toHaveBeenCalled();
  expect(jump).toHaveFocus();
  fireEvent.blur(jump);
  await waitFor(() => expect(screen.queryByRole('button', { name: /Jump to latest/ })).not.toBeInTheDocument());
});
