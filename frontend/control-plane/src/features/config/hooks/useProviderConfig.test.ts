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

function client(overrides: Partial<ControlPlaneClient> = {}) {
  return {
    config: vi.fn().mockResolvedValue(unconfigured),
    saveAzureConfig: vi.fn().mockResolvedValue(azure),
    startGithubDeviceFlow: vi.fn().mockResolvedValue(waiting),
    githubDeviceFlow: vi.fn().mockResolvedValue(waiting),
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

it('polls a waiting GitHub flow and refreshes persisted Config on success', async () => {
  vi.useFakeTimers();
  const githubConfig: ConfigResponse = {
    configured: true,
    provider: { type: 'github_copilot', modelName: 'gpt-5.5', authenticated: true },
  };
  const api = client({
    config: vi.fn().mockResolvedValueOnce(unconfigured).mockResolvedValueOnce(githubConfig),
    githubDeviceFlow: vi.fn().mockResolvedValue({ ...waiting, status: 'success', message: 'Saved.' }),
  });
  const { result } = renderHook(() => useProviderConfig(api));
  await act(async () => Promise.resolve());
  await act(async () => result.current.startGithub('gpt-5.5'));
  expect(result.current.deviceFlow?.status).toBe('waiting');

  await act(async () => vi.advanceTimersByTimeAsync(1000));

  expect(api.githubDeviceFlow).toHaveBeenCalledWith('auth-1', expect.any(AbortSignal));
  expect(api.config).toHaveBeenCalledTimes(2);
  expect(result.current.config.data).toEqual(githubConfig);
  expect(result.current.deviceFlow?.status).toBe('success');
});

it('clears polling and cooperatively cancels a waiting flow on unmount', async () => {
  vi.useFakeTimers();
  const api = client();
  const { result, unmount } = renderHook(() => useProviderConfig(api));
  await act(async () => Promise.resolve());
  await act(async () => result.current.startGithub('gpt-5.5'));

  unmount();
  await act(async () => Promise.resolve());
  await vi.advanceTimersByTimeAsync(2000);

  expect(api.cancelGithubDeviceFlow).toHaveBeenCalledWith('auth-1');
  expect(api.githubDeviceFlow).not.toHaveBeenCalled();
});

it('aborts a device-code request when its dialog closes before a flow exists', async () => {
  let capturedSignal: AbortSignal | undefined;
  const api = client({
    startGithubDeviceFlow: vi.fn((_modelName: string, signal?: AbortSignal) => {
      capturedSignal = signal;
      return new Promise<GitHubDeviceFlowResponse>((_resolve, reject) => signal?.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError'))));
    }),
  });
  const { result } = renderHook(() => useProviderConfig(api));
  await waitFor(() => expect(result.current.config.state).toBe('ready'));
  act(() => { void result.current.startGithub('gpt-5.5'); });
  await waitFor(() => expect(result.current.deviceFlowPending).toBe('starting'));

  await act(async () => result.current.clearDeviceFlow());

  expect(capturedSignal?.aborted).toBe(true);
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