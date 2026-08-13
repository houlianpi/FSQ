import { useCallback, useEffect, useRef, useState } from 'react';
import { controlPlaneClient, toApiError, type ControlPlaneClient } from '../../../api/controlPlaneClient';
import type {
  ApiErrorBody,
  AzureConfigPayload,
  ConfigResponse,
  ConnectionTestResponse,
  GitHubDeviceFlowResponse,
  RequestResource,
} from '../../../api/types';

type DeviceFlowPending = 'starting' | 'waiting' | 'cancelling' | null;
export type ConnectionResult =
  | { success: true; data: ConnectionTestResponse }
  | { success: false; error: ApiErrorBody };

function isAbort(error: unknown): boolean {
  return error instanceof DOMException && error.name === 'AbortError';
}

export function useProviderConfig(client: ControlPlaneClient = controlPlaneClient) {
  const [config, setConfig] = useState<RequestResource<ConfigResponse>>({ state: 'loading', data: null, error: null });
  const [savePending, setSavePending] = useState(false);
  const [saveError, setSaveError] = useState<ApiErrorBody | null>(null);
  const [deviceFlow, setDeviceFlowState] = useState<GitHubDeviceFlowResponse | null>(null);
  const [deviceFlowPending, setDeviceFlowPending] = useState<DeviceFlowPending>(null);
  const [deviceFlowError, setDeviceFlowError] = useState<ApiErrorBody | null>(null);
  const [testPending, setTestPending] = useState(false);
  const [connectionResult, setConnectionResult] = useState<ConnectionResult | null>(null);
  const mountedRef = useRef(false);
  const configControllerRef = useRef<AbortController | null>(null);
  const saveControllerRef = useRef<AbortController | null>(null);
  const deviceControllerRef = useRef<AbortController | null>(null);
  const testControllerRef = useRef<AbortController | null>(null);
  const pollTimerRef = useRef<number | null>(null);
  const deviceGenerationRef = useRef(0);
  const deviceFlowRef = useRef<GitHubDeviceFlowResponse | null>(null);

  const setDeviceFlow = useCallback((next: GitHubDeviceFlowResponse | null) => {
    deviceFlowRef.current = next;
    setDeviceFlowState(next);
  }, []);

  const clearPoll = useCallback(() => {
    if (pollTimerRef.current !== null) window.clearTimeout(pollTimerRef.current);
    pollTimerRef.current = null;
    deviceControllerRef.current?.abort();
    deviceControllerRef.current = null;
  }, []);

  const loadConfig = useCallback(async (quiet = false) => {
    configControllerRef.current?.abort();
    const controller = new AbortController();
    configControllerRef.current = controller;
    if (!quiet) setConfig((current) => ({ state: 'loading', data: current.data, error: null }));
    try {
      const data = await client.config(controller.signal);
      if (mountedRef.current && configControllerRef.current === controller) setConfig({ state: 'ready', data, error: null });
      return data;
    } catch (error) {
      if (!isAbort(error) && mountedRef.current && configControllerRef.current === controller) {
        setConfig((current) => ({ state: 'error', data: quiet ? current.data : null, error: toApiError(error) }));
      }
      return null;
    }
  }, [client]);

  const schedulePoll = useCallback((flow: GitHubDeviceFlowResponse, generation: number) => {
    const delay = Math.min(10, Math.max(1, flow.pollIntervalSeconds)) * 1000;
    pollTimerRef.current = window.setTimeout(async () => {
      const controller = new AbortController();
      deviceControllerRef.current = controller;
      try {
        const next = await client.githubDeviceFlow(flow.authRequestId, controller.signal);
        if (!mountedRef.current || generation !== deviceGenerationRef.current) return;
        setDeviceFlow(next);
        setDeviceFlowError(null);
        if (next.status === 'waiting') {
          setDeviceFlowPending('waiting');
          schedulePoll(next, generation);
        } else {
          setDeviceFlowPending(null);
          pollTimerRef.current = null;
          if (next.status === 'success') await loadConfig(true);
        }
      } catch (error) {
        if (!isAbort(error) && mountedRef.current && generation === deviceGenerationRef.current) {
          setDeviceFlowPending(null);
          setDeviceFlowError(toApiError(error));
        }
      } finally {
        if (deviceControllerRef.current === controller) deviceControllerRef.current = null;
      }
    }, delay);
  }, [client, loadConfig, setDeviceFlow]);

  const saveAzure = useCallback(async (payload: AzureConfigPayload) => {
    saveControllerRef.current?.abort();
    const controller = new AbortController();
    saveControllerRef.current = controller;
    setSavePending(true);
    setSaveError(null);
    const normalized = {
      baseUrl: payload.baseUrl.trim(),
      modelName: payload.modelName.trim(),
      apiKey: payload.apiKey.trim(),
    };
    try {
      const data = await client.saveAzureConfig(normalized, controller.signal);
      if (mountedRef.current && saveControllerRef.current === controller) setConfig({ state: 'ready', data, error: null });
      return data;
    } catch (error) {
      if (!isAbort(error) && mountedRef.current && saveControllerRef.current === controller) setSaveError(toApiError(error));
      return null;
    } finally {
      if (mountedRef.current && saveControllerRef.current === controller) setSavePending(false);
    }
  }, [client]);

  const startGithub = useCallback(async (modelName: string) => {
    clearPoll();
    const generation = ++deviceGenerationRef.current;
    const controller = new AbortController();
    deviceControllerRef.current = controller;
    setDeviceFlow(null);
    setDeviceFlowError(null);
    setDeviceFlowPending('starting');
    try {
      const flow = await client.startGithubDeviceFlow(modelName.trim(), controller.signal);
      if (!mountedRef.current || generation !== deviceGenerationRef.current) return null;
      setDeviceFlow(flow);
      if (flow.status === 'waiting') {
        setDeviceFlowPending('waiting');
        schedulePoll(flow, generation);
      } else {
        setDeviceFlowPending(null);
        if (flow.status === 'success') await loadConfig(true);
      }
      return flow;
    } catch (error) {
      if (!isAbort(error) && mountedRef.current && generation === deviceGenerationRef.current) {
        setDeviceFlowPending(null);
        setDeviceFlowError(toApiError(error));
      }
      return null;
    } finally {
      if (deviceControllerRef.current === controller) deviceControllerRef.current = null;
    }
  }, [clearPoll, client, loadConfig, schedulePoll, setDeviceFlow]);

  const cancelGithub = useCallback(async () => {
    const active = deviceFlowRef.current;
    ++deviceGenerationRef.current;
    clearPoll();
    if (!active || active.status !== 'waiting') {
      setDeviceFlow(null);
      setDeviceFlowError(null);
      setDeviceFlowPending(null);
      return;
    }
    const controller = new AbortController();
    deviceControllerRef.current = controller;
    setDeviceFlowPending('cancelling');
    try {
      const cancelled = await client.cancelGithubDeviceFlow(active.authRequestId, controller.signal);
      if (mountedRef.current) {
        setDeviceFlow(cancelled);
        setDeviceFlowError(null);
      }
    } catch (error) {
      if (!isAbort(error) && mountedRef.current) setDeviceFlowError(toApiError(error));
    } finally {
      if (mountedRef.current) setDeviceFlowPending(null);
      if (deviceControllerRef.current === controller) deviceControllerRef.current = null;
    }
  }, [clearPoll, client, setDeviceFlow]);

  const clearDeviceFlow = useCallback(() => {
    if (deviceFlowRef.current?.status === 'waiting') return cancelGithub();
    ++deviceGenerationRef.current;
    clearPoll();
    setDeviceFlow(null);
    setDeviceFlowError(null);
    setDeviceFlowPending(null);
    return Promise.resolve();
  }, [cancelGithub, clearPoll, setDeviceFlow]);

  const testSavedConnection = useCallback(async () => {
    testControllerRef.current?.abort();
    const controller = new AbortController();
    testControllerRef.current = controller;
    setTestPending(true);
    setConnectionResult(null);
    try {
      const data = await client.testConnection(controller.signal);
      if (mountedRef.current && testControllerRef.current === controller) setConnectionResult({ success: true, data });
    } catch (error) {
      if (!isAbort(error) && mountedRef.current && testControllerRef.current === controller) {
        setConnectionResult({ success: false, error: toApiError(error) });
      }
    } finally {
      if (mountedRef.current && testControllerRef.current === controller) setTestPending(false);
    }
  }, [client]);

  useEffect(() => {
    mountedRef.current = true;
    void loadConfig();
    return () => {
      mountedRef.current = false;
      ++deviceGenerationRef.current;
      configControllerRef.current?.abort();
      saveControllerRef.current?.abort();
      testControllerRef.current?.abort();
      clearPoll();
      const active = deviceFlowRef.current;
      if (active?.status === 'waiting') void client.cancelGithubDeviceFlow(active.authRequestId);
    };
  }, [clearPoll, client, loadConfig]);

  return {
    config,
    reload: loadConfig,
    saveAzure,
    savePending,
    saveError,
    deviceFlow,
    deviceFlowPending,
    deviceFlowError,
    startGithub,
    cancelGithub,
    clearDeviceFlow,
    testSavedConnection,
    testPending,
    connectionResult,
    dismissConnectionResult: () => setConnectionResult(null),
  };
}