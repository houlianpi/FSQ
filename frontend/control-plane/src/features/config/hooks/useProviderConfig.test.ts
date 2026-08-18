import { act, renderHook, waitFor } from '@testing-library/react';
import type { ControlPlaneClient } from '../../../api/controlPlaneClient';
import type { ConfigResponse, GitHubDeviceFlowResponse } from '../../../api/types';
import { useProviderConfig } from './useProviderConfig';

const unconfigured: ConfigResponse = { configured: false, provider: null };
const azure: ConfigResponse = {
  configured: true,
  provider: { type: 'azure_openai', baseUrl: 'https://example.test/openai/v1/', modelName: 'gpt-5.4', apiKey: 'saved-key' },
};
const waiting: GitHubDeviceFlowResponse = {
  authRequestId: 'auth-1', verificationUri: 'https://github.com/login/device', userCode: 'ABCD-EFGH',
  expiresAt: '2030-01-01T00:00:00Z', pollIntervalSeconds: 1, status: 'waiting',
};
const ready: GitHubDeviceFlowResponse = {
  authRequestId: 'auth-1', expiresAt: '2030-01-01T00:10:00Z', status: 'ready',
  models: [{ id: 'gpt-5', name: 'GPT 5' }, { id: 'gpt-5.5', name: 'GPT 5.5' }],
};
const githubConfig: ConfigResponse = {
  configured: true,
  provider: { type: 'github_copilot', modelName: 'gpt-5.5', authenticated: true },
};

function client(overrides: Partial<ControlPlaneClient> = {}) {
  return {
    config: vi.fn().mockResolvedValue(unconfigured),
    saveAzureConfig: vi.fn().mockResolvedValue(azure),
    startGithubDeviceFlow: vi.fn().mockResolvedValue(waiting),
    githubDeviceFlow: vi.fn().mockResolvedValue(waiting),
    retryGithubModels: vi.fn().mockResolvedValue(ready),
    saveGithubModel: vi.fn().mockResolvedValue(githubConfig),
    cancelGithubDeviceFlow: vi.fn().mockResolvedValue({ ...waiting, status: 'cancelled' }),
    testConnection: vi.fn().mockResolvedValue({ success: true, provider: 'azure_openai', modelName: 'gpt-5.4', durationMs: 125 }),
    ...overrides,
  } as unknown as ControlPlaneClient;
}

afterEach(() => {
  vi.useRealTimers();
});

it('loads Config and applies the complete saved Azure response', async () => {
  const api = client();
  const { result } = renderHook(() => useProviderConfig(api));
  await waitFor(() => expect(result.current.config.state).toBe('ready'));

  await act(async () => result.current.saveAzure({ baseUrl: ' https://example.test ', modelName: ' gpt-5.4 ', apiKey: 'saved-key' }));

  expect(api.saveAzureConfig).toHaveBeenCalledWith({ baseUrl: 'https://example.test', modelName: 'gpt-5.4', apiKey: 'saved-key' }, expect.any(AbortSignal));
  expect(result.current.config.data).toEqual(azure);
  expect(result.current.saveError).toBeNull();
});

it('starts GitHub without a model and polls authorization through model readiness', async () => {
  vi.useFakeTimers();
  const api = client({
    githubDeviceFlow: vi.fn().mockResolvedValue(ready),
  });
  const { result } = renderHook(() => useProviderConfig(api));
  await act(async () => Promise.resolve());
  await act(async () => result.current.startGithub());
  expect(result.current.deviceFlow?.status).toBe('waiting');

  await act(async () => vi.advanceTimersByTimeAsync(1000));

  expect(api.startGithubDeviceFlow).toHaveBeenCalledWith(expect.any(AbortSignal));
  expect(api.githubDeviceFlow).toHaveBeenCalledWith('auth-1', expect.any(AbortSignal));
  expect(api.config).toHaveBeenCalledTimes(1);
  expect(result.current.deviceFlow).toEqual(ready);
});

it('saves only an explicit discovered model and applies returned Config truth', async () => {
  const api = client({ startGithubDeviceFlow: vi.fn().mockResolvedValue(ready) });
  const { result } = renderHook(() => useProviderConfig(api));
  await act(async () => Promise.resolve());
  await act(async () => result.current.startGithub());

  await act(async () => result.current.saveGithubModel('gpt-5.5'));

  expect(api.saveGithubModel).toHaveBeenCalledWith('auth-1', 'gpt-5.5', expect.any(AbortSignal));
  expect(result.current.config.data).toEqual(githubConfig);
  expect(result.current.deviceFlow?.status).toBe('success');
});

it('clears polling and cooperatively cancels a waiting flow on unmount', async () => {
  vi.useFakeTimers();
  const api = client();
  const { result, unmount } = renderHook(() => useProviderConfig(api));
  await act(async () => Promise.resolve());
  await act(async () => result.current.startGithub());

  unmount();
  await act(async () => Promise.resolve());
  await vi.advanceTimersByTimeAsync(2000);

  expect(api.cancelGithubDeviceFlow).toHaveBeenCalledWith('auth-1');
  expect(api.githubDeviceFlow).not.toHaveBeenCalled();
});

it('aborts a device-code request when its dialog closes before a flow exists', async () => {
  let capturedSignal: AbortSignal | undefined;
  const api = client({
    startGithubDeviceFlow: vi.fn((signal?: AbortSignal) => {
      capturedSignal = signal;
      return new Promise<GitHubDeviceFlowResponse>((_resolve, reject) => signal?.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError'))));
    }),
  });
  const { result } = renderHook(() => useProviderConfig(api));
  await waitFor(() => expect(result.current.config.state).toBe('ready'));
  act(() => { void result.current.startGithub(); });
  await waitFor(() => expect(result.current.deviceFlowPending).toBe('starting'));

  await act(async () => result.current.clearDeviceFlow());

  expect(capturedSignal?.aborted).toBe(true);
  expect(result.current.deviceFlowPending).toBeNull();
});

it('ignores a stale cancellation response after a newer GitHub flow starts', async () => {
  let resolveCancellation: ((flow: GitHubDeviceFlowResponse) => void) | undefined;
  const newerReady = { ...ready, authRequestId: 'auth-2' };
  const api = client({
    startGithubDeviceFlow: vi.fn()
      .mockResolvedValueOnce(waiting)
      .mockResolvedValueOnce(newerReady),
    cancelGithubDeviceFlow: vi.fn(() => new Promise<GitHubDeviceFlowResponse>((resolve) => {
      resolveCancellation = resolve;
    })),
  });
  const { result } = renderHook(() => useProviderConfig(api));
  await waitFor(() => expect(result.current.config.state).toBe('ready'));
  await act(async () => result.current.startGithub());

  act(() => { void result.current.cancelGithub(); });
  await waitFor(() => expect(result.current.deviceFlowPending).toBe('cancelling'));
  await act(async () => result.current.startGithub());
  expect(result.current.deviceFlow).toEqual(newerReady);

  await act(async () => resolveCancellation?.({ ...waiting, status: 'cancelled' }));

  expect(result.current.deviceFlow).toEqual(newerReady);
  expect(result.current.deviceFlowPending).toBeNull();
});

it('does not clear a newer GitHub flow when an older dialog cleanup finishes', async () => {
  let resolveCancellation: ((flow: GitHubDeviceFlowResponse) => void) | undefined;
  const newerReady = { ...ready, authRequestId: 'auth-2' };
  const api = client({
    startGithubDeviceFlow: vi.fn()
      .mockResolvedValueOnce(waiting)
      .mockResolvedValueOnce(newerReady),
    cancelGithubDeviceFlow: vi.fn(() => new Promise<GitHubDeviceFlowResponse>((resolve) => {
      resolveCancellation = resolve;
    })),
  });
  const { result } = renderHook(() => useProviderConfig(api));
  await waitFor(() => expect(result.current.config.state).toBe('ready'));
  await act(async () => result.current.startGithub());

  act(() => { void result.current.clearDeviceFlow(); });
  await waitFor(() => expect(result.current.deviceFlowPending).toBe('cancelling'));
  await act(async () => result.current.startGithub());
  await act(async () => resolveCancellation?.({ ...waiting, status: 'cancelled' }));

  expect(result.current.deviceFlow).toEqual(newerReady);
  expect(result.current.deviceFlowPending).toBeNull();
});

it('captures both successful and structured failed saved-provider tests', async () => {
  const failedApi = client({
    testConnection: vi.fn().mockRejectedValue(new Error('network unavailable')),
  });
  const { result } = renderHook(() => useProviderConfig(failedApi));
  await waitFor(() => expect(result.current.config.state).toBe('ready'));

  await act(async () => result.current.testSavedConnection());

  expect(result.current.connectionResult).toEqual({
    success: false,
    error: expect.objectContaining({ code: 'network_error', message: 'network unavailable' }),
  });
});