import { act, renderHook, waitFor } from '@testing-library/react';
import type { ControlPlaneClient } from '../../../api/controlPlaneClient';
import type { BootstrapResponse, ReadinessResponse, TargetsResponse, CasesResponse } from '../../../api/types';
import { useDeviceWorkspace } from './useDeviceWorkspace';

const bootstrap: BootstrapResponse = {
  apiVersion: '1.0', platforms: [{ id: 'android', label: 'Android' }, { id: 'web', label: 'Web' }],
  workspace: { name: 'test', initialized: true }, busy: false, activeTask: null,
};
const readiness = (platform: 'android' | 'web'): ReadinessResponse => ({
  platform,
  workspace: { status: 'ready', message: 'ready', action: '' }, provider: { status: 'ready', message: 'ready', action: '' },
  target: { status: 'ready', message: 'ready', action: '' }, strict: { status: 'ready', message: 'ready', action: '' },
});
const targets = (platform: 'android' | 'web'): TargetsResponse => ({ platform, targetLabel: platform === 'web' ? 'Browser' : 'Device', targets: [{ id: `${platform}-target`, label: `${platform} target`, description: 'ready', status: 'ready', selectable: true, isDefault: true, metadata: {} }] });
const cases = (platform: 'android' | 'web'): CasesResponse => ({ platform, truncated: false, cases: [{ path: `${platform}.codex.yaml`, id: platform, name: `${platform} case`, platform, commandCount: 1, requiresAiAssertion: false, validationStatus: 'validated', selectable: true, diagnostics: [] }] });

function deferred<T>() { let resolve!: (value: T) => void; const promise = new Promise<T>((done) => { resolve = done; }); return { promise, resolve }; }
const runSnapshot = (requestId = 'request-1', platform: 'android' | 'web' = 'android') => ({
  requestId, runId: null, platform, targetId: `${platform}-target`, mode: 'explore' as const, status: 'preparing' as const,
  source: { goal: 'Verify' }, startedAt: '', completedAt: null, cancelRequested: false, events: [], activeStep: null,
  result: null, summary: 'Preparing', screenshotRevision: 0, uiSnapshotRevision: 0, evidenceAvailable: false, reportAvailable: false, terminal: false,
});

it('rejects stale platform responses by request generation', async () => {
  const oldReadiness = deferred<ReadinessResponse>();
  const client = {
    bootstrap: vi.fn().mockResolvedValue(bootstrap),
    readiness: vi.fn((platform: 'android' | 'web') => platform === 'android' ? oldReadiness.promise : Promise.resolve(readiness('web'))),
    targets: vi.fn((platform: 'android' | 'web') => Promise.resolve(targets(platform))),
    cases: vi.fn((platform: 'android' | 'web') => Promise.resolve(cases(platform))),
    startRun: vi.fn(), cancelRun: vi.fn(), runSnapshot: vi.fn(), streamUrl: vi.fn(), screenUrl: vi.fn(), uiSnapshot: vi.fn(),
  } as unknown as ControlPlaneClient;
  const { result } = renderHook(() => useDeviceWorkspace(client));
  await waitFor(() => expect(result.current.targets.data?.platform).toBe('android'));
  act(() => result.current.setPlatform('web'));
  await waitFor(() => expect(result.current.readiness.data?.platform).toBe('web'));
  act(() => oldReadiness.resolve(readiness('android')));
  await act(async () => Promise.resolve());
  expect(result.current.readiness.data?.platform).toBe('web');
});

it('derives start eligibility and sends mode-specific strict payloads', async () => {
  const startRun = vi.fn().mockResolvedValue({ requestId: 'request-1' });
  const client = {
    bootstrap: vi.fn().mockResolvedValue(bootstrap), readiness: vi.fn().mockResolvedValue(readiness('android')),
    targets: vi.fn().mockResolvedValue(targets('android')), cases: vi.fn().mockResolvedValue(cases('android')),
    startRun, cancelRun: vi.fn(), runSnapshot: vi.fn().mockResolvedValue(runSnapshot()), streamUrl: vi.fn(), screenUrl: vi.fn(), uiSnapshot: vi.fn(),
  } as unknown as ControlPlaneClient;
  globalThis.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ requestId: 'request-1', runId: null, platform: 'android', targetId: 'android-target', mode: 'strict', status: 'preparing', source: { casePath: 'android.codex.yaml' }, startedAt: '', completedAt: null, cancelRequested: false, events: [], activeStep: null, result: null, summary: 'Preparing', screenshotRevision: 0, uiSnapshotRevision: 0, evidenceAvailable: false, reportAvailable: false, terminal: false }), { status: 200, headers: { 'Content-Type': 'application/json' } }));
  const { result } = renderHook(() => useDeviceWorkspace(client));
  await waitFor(() => expect(result.current.targets.state).toBe('ready'));
  expect(result.current.canStart).toBe(false);
  act(() => result.current.setMode('strict'));
  await waitFor(() => expect(result.current.canStart).toBe(true));
  await act(async () => result.current.start());
  expect(startRun).toHaveBeenCalledWith({ mode: 'strict', platform: 'android', targetId: 'android-target', casePath: 'android.codex.yaml' });
  expect(result.current.controlsLocked).toBe(true);
});

it('requires provider readiness only for provider-gated strict cases', async () => {
  const unavailableProvider = { ...readiness('android'), provider: { status: 'unavailable' as const, message: 'setup', action: 'configure' } };
  const baseCase = cases('android').cases[0];
  const providerCases = { ...cases('android'), cases: [{ ...baseCase, path: 'gated.codex.yaml', requiresAiAssertion: true }, { ...baseCase, path: 'free.codex.yaml' }] };
  const client = {
    bootstrap: vi.fn().mockResolvedValue(bootstrap), readiness: vi.fn().mockResolvedValue(unavailableProvider),
    targets: vi.fn().mockResolvedValue(targets('android')), cases: vi.fn().mockResolvedValue(providerCases),
    startRun: vi.fn(), cancelRun: vi.fn(), runSnapshot: vi.fn(), streamUrl: vi.fn(), screenUrl: vi.fn(), screen: vi.fn(), uiSnapshot: vi.fn(),
  } as unknown as ControlPlaneClient;
  const { result } = renderHook(() => useDeviceWorkspace(client));
  await waitFor(() => expect(result.current.cases.state).toBe('ready'));
  act(() => result.current.setMode('strict'));
  expect(result.current.selectedCase?.requiresAiAssertion).toBe(true);
  expect(result.current.canStart).toBe(false);

  act(() => result.current.setCasePath('free.codex.yaml'));
  expect(result.current.canStart).toBe(true);
});

it('allows Explore and sends its payload without waiting for case discovery', async () => {
  const pendingCases = deferred<CasesResponse>();
  const startRun = vi.fn().mockResolvedValue({ requestId: 'explore-request' });
  const client = {
    bootstrap: vi.fn().mockResolvedValue(bootstrap), readiness: vi.fn().mockResolvedValue(readiness('android')),
    targets: vi.fn().mockResolvedValue(targets('android')), cases: vi.fn().mockReturnValue(pendingCases.promise),
    startRun, cancelRun: vi.fn(), runSnapshot: vi.fn().mockResolvedValue(runSnapshot('explore-request')), streamUrl: vi.fn(), screenUrl: vi.fn(), uiSnapshot: vi.fn(),
  } as unknown as ControlPlaneClient;
  const { result } = renderHook(() => useDeviceWorkspace(client));
  await waitFor(() => expect(result.current.targets.state).toBe('ready'));
  act(() => result.current.setGoal('  Verify the welcome page  '));

  await waitFor(() => expect(result.current.canStart).toBe(true));
  expect(result.current.cases.state).toBe('loading');
  await act(async () => result.current.start());
  expect(startRun).toHaveBeenCalledWith({ mode: 'explore', platform: 'android', targetId: 'android-target', goal: 'Verify the welcome page' });
});

it('respects backend bootstrap truth when starting a new run', async () => {
  const activeBootstrap: BootstrapResponse = {
    ...bootstrap, busy: true,
    activeTask: { requestId: 'other-request', runId: null, platform: 'web', targetId: 'web-target', mode: 'strict', status: 'running' },
  };
  const bootstrapCall = vi.fn()
    .mockResolvedValueOnce(bootstrap)
    .mockResolvedValueOnce(activeBootstrap)
    .mockResolvedValueOnce(bootstrap);
  const client = {
    bootstrap: bootstrapCall, readiness: vi.fn((platform: 'android' | 'web') => Promise.resolve(readiness(platform))),
    targets: vi.fn((platform: 'android' | 'web') => Promise.resolve(targets(platform))), cases: vi.fn((platform: 'android' | 'web') => Promise.resolve(cases(platform))),
    startRun: vi.fn(), cancelRun: vi.fn(), runSnapshot: vi.fn().mockResolvedValue(runSnapshot('other-request', 'web')), streamUrl: vi.fn(), screenUrl: vi.fn(), uiSnapshot: vi.fn(),
  } as unknown as ControlPlaneClient;
  const { result } = renderHook(() => useDeviceWorkspace(client));
  await waitFor(() => expect(result.current.bootstrap.state).toBe('ready'));

  await act(async () => result.current.newRun());
  await waitFor(() => expect(result.current.requestId).toBe('other-request'));
  expect(result.current.bootstrap.data?.busy).toBe(true);
  expect(result.current.platform).toBe('web');

  await act(async () => result.current.newRun());
  await waitFor(() => expect(result.current.requestId).toBeNull());
  expect(result.current.bootstrap.data?.busy).toBe(false);
});
