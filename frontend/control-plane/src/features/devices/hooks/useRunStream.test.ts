import { act, renderHook, waitFor } from '@testing-library/react';
import { ControlPlaneApiError, controlPlaneClient } from '../../../api/controlPlaneClient';
import type { RunSnapshot } from '../../../api/types';
import { useRunStream } from './useRunStream';

afterEach(() => {
  vi.restoreAllMocks();
  TestEventSource.instances = [];
});

const snapshot = (overrides: Partial<RunSnapshot> = {}): RunSnapshot => ({
  requestId: 'request-1', runId: 'run-1', platform: 'web', targetId: 'chrome', mode: 'explore', status: 'running',
  source: { goal: 'Verify' }, startedAt: '', completedAt: null, cancelRequested: false,
  events: [], activeStep: null, result: null, summary: 'Running', screenshotRevision: 0, uiSnapshotRevision: 0,
  evidenceAvailable: false, reportAvailable: false, terminal: false, ...overrides,
});

class TestEventSource {
  static instances: TestEventSource[] = [];
  readonly listeners = new Map<string, (event: Event) => void>();
  onerror: ((event: Event) => void) | null = null;
  constructor(readonly url: string) { TestEventSource.instances.push(this); }
  addEventListener(type: string, listener: EventListenerOrEventListenerObject) {
    this.listeners.set(type, listener as (event: Event) => void);
  }
  close() {}
  emit(type: string, value: RunSnapshot) {
    this.listeners.get(type)?.(new MessageEvent(type, { data: JSON.stringify(value) }));
  }
}

it('accepts terminal and status-only snapshots without new events', async () => {
  const original = window.EventSource;
  Object.defineProperty(window, 'EventSource', { configurable: true, value: TestEventSource });
  Object.defineProperty(globalThis, 'EventSource', { configurable: true, value: TestEventSource });
  vi.spyOn(controlPlaneClient, 'runSnapshot').mockResolvedValue(snapshot({
    events: [{ sequence: 4, label: 'Last event' }],
  }));
  vi.spyOn(controlPlaneClient, 'streamUrl').mockReturnValue('/stream');
  const { result, unmount } = renderHook(() => useRunStream('request-1'));
  await waitFor(() => expect(result.current.snapshot?.events).toHaveLength(1));

  act(() => TestEventSource.instances.at(-1)?.emit('snapshot', snapshot({
    status: 'success', terminal: true, completedAt: '2026-08-11T00:00:00Z', summary: 'Done', events: [],
  })));

  expect(result.current.snapshot?.status).toBe('success');
  expect(result.current.snapshot?.summary).toBe('Done');
  expect(result.current.snapshot?.events).toHaveLength(1);
  expect(result.current.connection).toBe('ended');
  unmount();
  Object.defineProperty(window, 'EventSource', { configurable: true, value: original });
  Object.defineProperty(globalThis, 'EventSource', { configurable: true, value: original });
});

it('ends recoverably when polling finds a restarted backend', async () => {
  const original = window.EventSource;
  Reflect.deleteProperty(window, 'EventSource');
  Reflect.deleteProperty(globalThis, 'EventSource');
  vi.spyOn(controlPlaneClient, 'runSnapshot').mockRejectedValue(new ControlPlaneApiError(404, {
    code: 'request_not_found', message: 'missing', action: 'reload',
  }));

  const { result, unmount } = renderHook(() => useRunStream('request-1'));
  await waitFor(() => expect(result.current.connection).toBe('ended'));
  expect(result.current.error?.code).toBe('run_ended');
  expect(result.current.error?.action).toMatch(/new run|reattach/i);
  unmount();
  Object.defineProperty(window, 'EventSource', { configurable: true, value: original });
  Object.defineProperty(globalThis, 'EventSource', { configurable: true, value: original });
});

it('falls back to polling after bounded EventSource reconnect exhaustion', async () => {
  vi.useFakeTimers();
  const original = window.EventSource;
  Object.defineProperty(window, 'EventSource', { configurable: true, value: TestEventSource });
  Object.defineProperty(globalThis, 'EventSource', { configurable: true, value: TestEventSource });
  const client = {
    ...controlPlaneClient,
    runSnapshot: vi.fn().mockResolvedValue(snapshot()),
    streamUrl: vi.fn().mockReturnValue('/stream'),
  };
  const { result, unmount } = renderHook(() => useRunStream('request-1', client));
  await act(async () => Promise.resolve());
  for (const delay of [400, 800, 1600]) {
    act(() => TestEventSource.instances.at(-1)?.onerror?.(new Event('error')));
    await act(async () => { await vi.advanceTimersByTimeAsync(delay); });
  }
  act(() => TestEventSource.instances.at(-1)?.onerror?.(new Event('error')));
  await act(async () => Promise.resolve());
  expect(result.current.connection).toBe('polling');
  expect(client.runSnapshot).toHaveBeenCalled();
  unmount();
  vi.useRealTimers();
  Object.defineProperty(window, 'EventSource', { configurable: true, value: original });
  Object.defineProperty(globalThis, 'EventSource', { configurable: true, value: original });
});
