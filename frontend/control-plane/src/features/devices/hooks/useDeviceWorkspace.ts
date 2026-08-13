import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { controlPlaneClient, toApiError, type ControlPlaneClient } from '../../../api/controlPlaneClient';
import type {
  ApiErrorBody,
  BootstrapResponse,
  CaseRecord,
  CasesResponse,
  EvidenceTab,
  PlatformId,
  ReadinessResponse,
  RequestResource,
  RunMode,
  StartRunPayload,
  TargetsResponse,
} from '../../../api/types';
import { useRunStream } from './useRunStream';

const emptyResource = <T,>(): RequestResource<T> => ({ state: 'idle', data: null, error: null });
const loadingResource = <T,>(previous: T | null = null): RequestResource<T> => ({ state: 'loading', data: previous, error: null });

export function useDeviceWorkspace(client: ControlPlaneClient = controlPlaneClient) {
  const [bootstrap, setBootstrap] = useState<RequestResource<BootstrapResponse>>(emptyResource);
  const [platform, setPlatformState] = useState<PlatformId>('android');
  const [targetId, setTargetId] = useState('');
  const [mode, setMode] = useState<RunMode>('explore');
  const [goal, setGoal] = useState('');
  const [casePath, setCasePath] = useState('');
  const [readiness, setReadiness] = useState<RequestResource<ReadinessResponse>>(emptyResource);
  const [targets, setTargets] = useState<RequestResource<TargetsResponse>>(emptyResource);
  const [cases, setCases] = useState<RequestResource<CasesResponse>>(emptyResource);
  const [requestId, setRequestId] = useState<string | null>(null);
  const [startError, setStartError] = useState<ApiErrorBody | null>(null);
  const [evidenceTab, setEvidenceTab] = useState<EvidenceTab>('screen');
  const [selectedStepId, setSelectedStepId] = useState<string | null>(null);
  const generationRef = useRef(0);
  const discoveryControllerRef = useRef<AbortController | null>(null);
  const { snapshot, connection, error: streamError } = useRunStream(requestId, client);

  const loadDiscovery = useCallback((selectedPlatform: PlatformId, clearSelection: boolean) => {
    discoveryControllerRef.current?.abort();
    const controller = new AbortController();
    discoveryControllerRef.current = controller;
    const generation = ++generationRef.current;
    if (clearSelection) { setTargetId(''); setCasePath(''); }
    setReadiness((value) => loadingResource(value.data?.platform === selectedPlatform ? value.data : null));
    setTargets((value) => loadingResource(value.data?.platform === selectedPlatform ? value.data : null));
    setCases((value) => loadingResource(value.data?.platform === selectedPlatform ? value.data : null));

    const applies = () => generationRef.current === generation && !controller.signal.aborted;
    void client.readiness(selectedPlatform, controller.signal).then((data) => { if (applies()) setReadiness({ state: 'ready', data, error: null }); }).catch((error) => { if (applies()) setReadiness({ state: 'error', data: null, error: toApiError(error) }); });
    void client.targets(selectedPlatform, controller.signal).then((data) => {
      if (!applies()) return;
      setTargets({ state: 'ready', data, error: null });
      setTargetId((current) => {
        if (data.targets.some((target) => target.id === current && target.selectable)) return current;
        return data.targets.find((target) => target.selectable && target.isDefault)?.id ?? data.targets.find((target) => target.selectable)?.id ?? '';
      });
    }).catch((error) => { if (applies()) setTargets({ state: 'error', data: null, error: toApiError(error) }); });
    void client.cases(selectedPlatform, controller.signal).then((data) => {
      if (!applies()) return;
      setCases({ state: 'ready', data, error: null });
      setCasePath((current) => data.cases.some((item) => item.path === current && item.selectable) ? current : (data.cases.find((item) => item.selectable)?.path ?? ''));
    }).catch((error) => { if (applies()) setCases({ state: 'error', data: null, error: toApiError(error) }); });
  }, [client]);

  useEffect(() => {
    const controller = new AbortController();
    setBootstrap(loadingResource());
    void client.bootstrap(controller.signal).then((data) => {
      setBootstrap({ state: 'ready', data, error: null });
      if (data.activeTask) {
        setPlatformState(data.activeTask.platform);
        setTargetId(data.activeTask.targetId);
        setMode(data.activeTask.mode);
        setRequestId(data.activeTask.requestId);
      }
    }).catch((error) => { if (!controller.signal.aborted) setBootstrap({ state: 'error', data: null, error: toApiError(error) }); });
    return () => controller.abort();
  }, [client]);

  useEffect(() => {
    loadDiscovery(platform, true);
    return () => discoveryControllerRef.current?.abort();
  }, [loadDiscovery, platform]);

  useEffect(() => {
    if (!snapshot) return;
    setPlatformState(snapshot.platform);
    setTargetId(snapshot.targetId);
    setMode(snapshot.mode);
    if (!snapshot.terminal) setSelectedStepId(null);
  }, [snapshot]);

  useEffect(() => {
    if (streamError?.code !== 'run_ended') return;
    setRequestId(null);
    setStartError(streamError);
    void client.bootstrap().then((data) => {
      setBootstrap({ state: 'ready', data, error: null });
      if (data.activeTask) {
        setPlatformState(data.activeTask.platform);
        setTargetId(data.activeTask.targetId);
        setMode(data.activeTask.mode);
        setRequestId(data.activeTask.requestId);
      }
    }).catch((error) => setBootstrap({ state: 'error', data: null, error: toApiError(error) }));
  }, [client, streamError]);

  const active = Boolean(snapshot && !snapshot.terminal) || Boolean(requestId && !snapshot);
  const controlsLocked = active;
  const selectedTarget = targets.data?.targets.find((target) => target.id === targetId) ?? null;
  const selectedCase: CaseRecord | null = cases.data?.cases.find((item) => item.path === casePath) ?? null;
  const commonReady = readiness.state === 'ready' && targets.state === 'ready'
    && readiness.data?.workspace.status === 'ready'
    && readiness.data.target.status === 'ready'
    && selectedTarget?.selectable === true;
  const sourceReady = mode === 'explore'
    ? goal.trim().length > 0 && readiness.data?.provider.status === 'ready'
    : cases.state === 'ready'
      && selectedCase?.selectable === true
      && readiness.data?.strict.status === 'ready'
      && (!selectedCase.requiresAiAssertion || readiness.data.provider.status === 'ready');
  const canStart = Boolean(commonReady && sourceReady && !active && bootstrap.state === 'ready' && !bootstrap.data?.busy);

  const setPlatform = (next: PlatformId) => { if (!controlsLocked) setPlatformState(next); };
  const refresh = () => { if (!controlsLocked) loadDiscovery(platform, false); };
  const start = async () => {
    if (!canStart || !selectedTarget) return;
    setStartError(null);
    const payload: StartRunPayload = mode === 'explore'
      ? { mode: 'explore', platform, targetId: selectedTarget.id, goal: goal.trim() }
      : { mode: 'strict', platform, targetId: selectedTarget.id, casePath };
    try {
      const response = await client.startRun(payload);
      setRequestId(response.requestId);
    } catch (error) {
      setStartError(toApiError(error));
      loadDiscovery(platform, false);
    }
  };
  const cancel = async () => {
    if (!requestId) return;
    try { await client.cancelRun(requestId); }
    catch (error) { setStartError(toApiError(error)); }
  };
  const newRun = () => {
    setStartError(null);
    setEvidenceTab('screen');
    setSelectedStepId(null);
    return client.bootstrap().then((data) => {
      setBootstrap({ state: 'ready', data, error: null });
      if (data.activeTask) {
        setPlatformState(data.activeTask.platform);
        setTargetId(data.activeTask.targetId);
        setMode(data.activeTask.mode);
        setRequestId(data.activeTask.requestId);
      } else {
        setRequestId(null);
        loadDiscovery(platform, false);
      }
    }).catch((error) => setStartError(toApiError(error)));
  };

  const connectionLabel = useMemo(() => {
    if (active) return connection === 'polling' ? 'Polling' : connection === 'reconnecting' ? 'Reconnecting' : 'Live';
    if (targets.state === 'loading') return 'Discovering';
    if (selectedTarget?.selectable) return 'Ready';
    return 'Unavailable';
  }, [active, connection, selectedTarget, targets.state]);

  return {
    bootstrap, platform, setPlatform, targetId, setTargetId, mode, setMode, goal, setGoal, casePath, setCasePath,
    readiness, targets, cases, selectedTarget, selectedCase, requestId, snapshot, streamError, startError,
    evidenceTab, setEvidenceTab, selectedStepId, setSelectedStepId, controlsLocked, canStart, connection, connectionLabel, refresh, start, cancel, newRun,
  };
}

export type DeviceWorkspace = ReturnType<typeof useDeviceWorkspace>;
