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

export type DeviceFlowPending = 'starting' | 'waiting' | 'loading_models' | 'retrying_models' | 'saving' | 'cancelling' | null;
export type ConnectionResult =
  | { success: true; data: ConnectionTestResponse }
  | { success: false; error: ApiErrorBody };

function isAbort(error: unknown): boolean {
  return error instanceof DOMException && error.name === 'AbortError';
}

function isPolling(flow: GitHubDeviceFlowResponse): flow is Extract<GitHubDeviceFlowResponse, { status: 'waiting' | 'loading_models' }> {
  return flow.status === 'waiting' || flow.status === 'loading_models';
}

function isUnsaved(flow: GitHubDeviceFlowResponse): boolean {
  return ['waiting', 'loading_models', 'ready', 'model_error'].includes(flow.status);
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
    if (!isPolling(flow)) return;
    const delay = Math.min(10, Math.max(1, flow.pollIntervalSeconds)) * 1000;
    pollTimerRef.current = window.setTimeout(async () => {
      const controller = new AbortController();
      deviceControllerRef.current = controller;
      try {
        const next = await client.githubDeviceFlow(flow.authRequestId, controller.signal);
        if (!mountedRef.current || generation !== deviceGenerationRef.current) return;
        setDeviceFlow(next);
        setDeviceFlowError(null);
        if (isPolling(next)) {
          setDeviceFlowPending(next.status);
          schedulePoll(next, generation);
        } else {
          setDeviceFlowPending(null);
          pollTimerRef.current = null;
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
  }, [client, setDeviceFlow]);

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

  const startGithub = useCallback(async () => {
    clearPoll();
    const generation = ++deviceGenerationRef.current;
    const controller = new AbortController();
    deviceControllerRef.current = controller;
    setDeviceFlow(null);
    setDeviceFlowError(null);
    setDeviceFlowPending('starting');
    try {
      const flow = await client.startGithubDeviceFlow(controller.signal);
      if (!mountedRef.current || generation !== deviceGenerationRef.current) return null;
      setDeviceFlow(flow);
      if (isPolling(flow)) {
        setDeviceFlowPending(flow.status);
        schedulePoll(flow, generation);
      } else {
        setDeviceFlowPending(null);
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
  }, [clearPoll, client, schedulePoll, setDeviceFlow]);

  const retryGithubModels = useCallback(async () => {
    const active = deviceFlowRef.current;
    if (!active || (active.status !== 'model_error' && !(active.status === 'ready' && active.models.length === 0))) return null;
    clearPoll();
    const generation = ++deviceGenerationRef.current;
    const controller = new AbortController();
    deviceControllerRef.current = controller;
    setDeviceFlowError(null);
    setDeviceFlowPending('retrying_models');
    try {
      const flow = await client.retryGithubModels(active.authRequestId, controller.signal);
      if (!mountedRef.current || generation !== deviceGenerationRef.current) return null;
      setDeviceFlow(flow);
      if (isPolling(flow)) {
        setDeviceFlowPending(flow.status);
        schedulePoll(flow, generation);
      } else {
        setDeviceFlowPending(null);
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
  }, [clearPoll, client, schedulePoll, setDeviceFlow]);

  const saveGithubModel = useCallback(async (modelName: string) => {
    const active = deviceFlowRef.current;
    const selectedModel = modelName.trim();
    if (!active || active.status !== 'ready' || !selectedModel) return null;
    clearPoll();
    const generation = ++deviceGenerationRef.current;
    const controller = new AbortController();
    deviceControllerRef.current = controller;
    setDeviceFlowError(null);
    setDeviceFlowPending('saving');
    try {
      const data = await client.saveGithubModel(active.authRequestId, selectedModel, controller.signal);
      if (!mountedRef.current || generation !== deviceGenerationRef.current) return null;
      setConfig({ state: 'ready', data, error: null });
      setDeviceFlow({ authRequestId: active.authRequestId, status: 'success', message: 'GitHub Copilot Provider saved.' });
      return data;
    } catch (error) {
      if (!isAbort(error) && mountedRef.current && generation === deviceGenerationRef.current) setDeviceFlowError(toApiError(error));
      return null;
    } finally {
      if (mountedRef.current && generation === deviceGenerationRef.current) setDeviceFlowPending(null);
      if (deviceControllerRef.current === controller) deviceControllerRef.current = null;
    }
  }, [clearPoll, client, setDeviceFlow]);

  const cancelGithub = useCallback(async () => {
    const active = deviceFlowRef.current;
    const generation = ++deviceGenerationRef.current;
    clearPoll();
    if (!active || !isUnsaved(active)) {
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
      if (mountedRef.current && generation === deviceGenerationRef.current) {
        setDeviceFlow(cancelled);
        setDeviceFlowError(null);
      }
    } catch (error) {
      if (!isAbort(error) && mountedRef.current && generation === deviceGenerationRef.current) setDeviceFlowError(toApiError(error));
    } finally {
      if (mountedRef.current && generation === deviceGenerationRef.current) setDeviceFlowPending(null);
      if (deviceControllerRef.current === controller) deviceControllerRef.current = null;
    }
  }, [clearPoll, client, setDeviceFlow]);

  const clearDeviceFlow = useCallback(async () => {
    if (deviceFlowRef.current && isUnsaved(deviceFlowRef.current)) {
      const cancellation = cancelGithub();
      const cancellationGeneration = deviceGenerationRef.current;
      await cancellation;
      if (cancellationGeneration !== deviceGenerationRef.current) return;
    }
    ++deviceGenerationRef.current;
    clearPoll();
    setDeviceFlow(null);
    setDeviceFlowError(null);
    setDeviceFlowPending(null);
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
      if (active && isUnsaved(active)) void client.cancelGithubDeviceFlow(active.authRequestId);
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
    retryGithubModels,
    saveGithubModel,
    cancelGithub,
    clearDeviceFlow,
    testSavedConnection,
    testPending,
    connectionResult,
    dismissConnectionResult: () => setConnectionResult(null),
  };
}