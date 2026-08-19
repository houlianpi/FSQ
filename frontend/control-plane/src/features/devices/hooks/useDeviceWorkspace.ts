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
  PlatformOption,
} from '../../../api/types';
import { useRunStream } from './useRunStream';

const emptyResource = <T,>(): RequestResource<T> => ({ state: 'idle', data: null, error: null });
const loadingResource = <T,>(previous: T | null = null): RequestResource<T> => ({ state: 'loading', data: previous, error: null });

interface DeviceWorkspaceContext {
  workspaceName: string | null;
  platforms: readonly PlatformOption[];
  onWorkspaceChange: (workspaceName: string) => void;
}

export function useDeviceWorkspace(context: DeviceWorkspaceContext, client: ControlPlaneClient = controlPlaneClient) {
  const { workspaceName, platforms, onWorkspaceChange } = context;
  const [bootstrap, setBootstrap] = useState<RequestResource<BootstrapResponse>>(emptyResource);
  const [platform, setPlatformState] = useState<PlatformId | ''>('');
  const [targetId, setTargetId] = useState('');
  const [mode, setMode] = useState<RunMode>('explore');
  const [goal, setGoal] = useState('');
  const [casePath, setCasePath] = useState('');
  const [readiness, setReadiness] = useState<RequestResource<ReadinessResponse>>(emptyResource);
  const [targets, setTargets] = useState<RequestResource<TargetsResponse>>(emptyResource);
  const [cases, setCases] = useState<RequestResource<CasesResponse>>(emptyResource);
  const [requestId, setRequestId] = useState<string | null>(null);
  const [startError, setStartError] = useState<ApiErrorBody | null>(null);
  const [saveYamlState, setSaveYamlState] = useState<RequestResource<{ savedPath: string; message: string }>>(emptyResource);
  const [evidenceTab, setEvidenceTab] = useState<EvidenceTab>('screen');
  const [selectedStepId, setSelectedStepId] = useState<string | null>(null);
  const generationRef = useRef(0);
  const previousWorkspaceRef = useRef<string | null>(workspaceName);
  const discoveryControllerRef = useRef<AbortController | null>(null);
  const { snapshot, connection, error: streamError } = useRunStream(requestId, client);

  const loadDiscovery = useCallback((selectedWorkspace: string, selectedPlatform: PlatformId, clearSelection: boolean) => {
    discoveryControllerRef.current?.abort();
    const controller = new AbortController();
    discoveryControllerRef.current = controller;
    const generation = ++generationRef.current;
    if (clearSelection) { setTargetId(''); setCasePath(''); }
    setReadiness((value) => loadingResource(!clearSelection && value.data?.workspaceName === selectedWorkspace && value.data.platformId === selectedPlatform ? value.data : null));
    setTargets((value) => loadingResource(!clearSelection && value.data?.platform === selectedPlatform ? value.data : null));
    setCases((value) => loadingResource(!clearSelection && value.data?.platform === selectedPlatform ? value.data : null));

    const applies = () => generationRef.current === generation && !controller.signal.aborted;
    void client.readiness(selectedWorkspace, selectedPlatform, controller.signal).then((data) => { if (applies()) setReadiness({ state: 'ready', data, error: null }); }).catch((error) => { if (applies()) setReadiness({ state: 'error', data: null, error: toApiError(error) }); });
    void client.targets(selectedWorkspace, selectedPlatform, controller.signal).then((data) => {
      if (!applies()) return;
      setTargets({ state: 'ready', data, error: null });
      setTargetId((current) => {
        if (data.targets.some((target) => target.id === current && target.selectable)) return current;
        return data.targets.find((target) => target.selectable && target.isDefault)?.id ?? data.targets.find((target) => target.selectable)?.id ?? '';
      });
    }).catch((error) => { if (applies()) setTargets({ state: 'error', data: null, error: toApiError(error) }); });
    void client.cases(selectedWorkspace, selectedPlatform, controller.signal).then((data) => {
      if (!applies()) return;
      setCases({ state: 'ready', data, error: null });
      setCasePath((current) => data.cases.some((item) => item.path === current && item.selectable) ? current : '');
    }).catch((error) => { if (applies()) setCases({ state: 'error', data: null, error: toApiError(error) }); });
  }, [client]);

  useEffect(() => {
    const controller = new AbortController();
    setBootstrap(loadingResource());
    void client.bootstrap(controller.signal).then((data) => {
      setBootstrap({ state: 'ready', data, error: null });
      if (data.activeTask) {
        onWorkspaceChange(data.activeTask.workspaceName);
        setPlatformState(data.activeTask.platform);
        setTargetId(data.activeTask.targetId);
        setMode(data.activeTask.mode);
        setRequestId(data.activeTask.requestId);
      }
    }).catch((error) => { if (!controller.signal.aborted) setBootstrap({ state: 'error', data: null, error: toApiError(error) }); });
    return () => controller.abort();
  }, [client, onWorkspaceChange]);

  useEffect(() => {
    const workspaceChanged = previousWorkspaceRef.current !== workspaceName;
    previousWorkspaceRef.current = workspaceName;
    discoveryControllerRef.current?.abort();
    generationRef.current += 1;
    setTargetId('');
    setCasePath('');
    setReadiness(emptyResource());
    setTargets(emptyResource());
    setCases(emptyResource());
    const activeTask = bootstrap.data?.activeTask;
    const restoringActiveTask = activeTask?.workspaceName === workspaceName && activeTask.platform === platform;
    const onlyPlatform = platforms.length === 1 ? platforms[0].id : '';
    const platformAvailable = Boolean(platform && platforms.some((item) => item.id === platform));
    if (!workspaceName) {
      setPlatformState('');
      return;
    }
    if (!restoringActiveTask && (workspaceChanged || !platformAvailable)) {
      if (!onlyPlatform || onlyPlatform !== platform) {
        setPlatformState(onlyPlatform);
        return;
      }
    }
    if (!platform) return;
    loadDiscovery(workspaceName, platform, true);
    return () => discoveryControllerRef.current?.abort();
  }, [bootstrap.data?.activeTask, loadDiscovery, platform, platforms, workspaceName]);

  useEffect(() => {
    if (!snapshot) return;
    onWorkspaceChange(snapshot.workspaceName);
    setPlatformState(snapshot.platform);
    setTargetId(snapshot.targetId);
    setMode(snapshot.mode);
    if (!snapshot.terminal) setSelectedStepId(null);
    if (!snapshot.terminal || snapshot.mode !== 'explore') setSaveYamlState(emptyResource());
  }, [onWorkspaceChange, snapshot]);

  useEffect(() => {
    if (streamError?.code !== 'run_ended') return;
    setRequestId(null);
    setStartError(streamError);
    void client.bootstrap().then((data) => {
      setBootstrap({ state: 'ready', data, error: null });
      if (data.activeTask) {
        onWorkspaceChange(data.activeTask.workspaceName);
        setPlatformState(data.activeTask.platform);
        setTargetId(data.activeTask.targetId);
        setMode(data.activeTask.mode);
        setRequestId(data.activeTask.requestId);
      }
    }).catch((error) => setBootstrap({ state: 'error', data: null, error: toApiError(error) }));
  }, [client, onWorkspaceChange, streamError]);

  const active = Boolean(snapshot && !snapshot.terminal) || Boolean(requestId && !snapshot);
  const controlsLocked = active;
  const selectedTarget = targets.data?.targets.find((target) => target.id === targetId) ?? null;
  const selectedCase: CaseRecord | null = cases.data?.cases.find((item) => item.path === casePath) ?? null;
  const commonReady = readiness.state === 'ready' && targets.state === 'ready'
    && Boolean(workspaceName && platform)
    && readiness.data?.workspace.status === 'ready'
    && readiness.data?.platform.status === 'ready'
    && readiness.data.target.status === 'ready'
    && selectedTarget?.selectable === true;
  const sourceReady = mode === 'explore'
    ? goal.trim().length > 0 && readiness.data?.provider.status === 'ready'
    : cases.state === 'ready'
      && selectedCase?.selectable === true
      && readiness.data?.strict.status === 'ready'
      && (!selectedCase.requiresAiAssertion || readiness.data.provider.status === 'ready');
  const canStart = Boolean(commonReady && sourceReady && !active && bootstrap.state === 'ready' && !bootstrap.data?.busy);

  const setPlatform = (next: PlatformId | '') => {
    if (!controlsLocked && (!next || platforms.some((item) => item.id === next))) setPlatformState(next);
  };
  const refresh = () => { if (!controlsLocked && workspaceName && platform) loadDiscovery(workspaceName, platform, false); };
  const start = async () => {
    if (!canStart || !selectedTarget || !workspaceName || !platform) return;
    setStartError(null);
    const payload: StartRunPayload = mode === 'explore'
      ? { mode: 'explore', workspaceName, platform, targetId: selectedTarget.id, goal: goal.trim() }
      : { mode: 'strict', workspaceName, platform, targetId: selectedTarget.id, casePath };
    try {
      const response = await client.startRun(payload);
      setSaveYamlState(emptyResource());
      setRequestId(response.requestId);
    } catch (error) {
      setStartError(toApiError(error));
      loadDiscovery(workspaceName, platform, false);
    }
  };
  const cancel = async () => {
    if (!requestId) return;
    try { await client.cancelRun(requestId); }
    catch (error) { setStartError(toApiError(error)); }
  };
  const newRun = () => {
    setStartError(null);
    setSaveYamlState(emptyResource());
    setEvidenceTab('screen');
    setSelectedStepId(null);
    return client.bootstrap().then((data) => {
      setBootstrap({ state: 'ready', data, error: null });
      if (data.activeTask) {
        onWorkspaceChange(data.activeTask.workspaceName);
        setPlatformState(data.activeTask.platform);
        setTargetId(data.activeTask.targetId);
        setMode(data.activeTask.mode);
        setRequestId(data.activeTask.requestId);
      } else {
        setRequestId(null);
        if (workspaceName && platform) loadDiscovery(workspaceName, platform, false);
      }
    }).catch((error) => setStartError(toApiError(error)));
  };
  const saveYaml = async (caseName: string) => {
    if (!requestId || snapshot?.terminal !== true || snapshot.mode !== 'explore') return;
    setSaveYamlState(loadingResource(saveYamlState.data));
    try {
      const response = await client.saveYaml(requestId, { caseName });
      setSaveYamlState({ state: 'ready', data: response, error: null });
    } catch (error) {
      setSaveYamlState({ state: 'error', data: saveYamlState.data, error: toApiError(error) });
    }
  };

  const connectionLabel = useMemo(() => {
    if (active) return connection === 'polling' ? 'Polling' : connection === 'reconnecting' ? 'Reconnecting' : 'Live';
    if (targets.state === 'loading') return 'Discovering';
    if (selectedTarget?.selectable) return 'Ready';
    return 'Unavailable';
  }, [active, connection, selectedTarget, targets.state]);

  return {
    bootstrap, workspaceName, platform, setPlatform, targetId, setTargetId, mode, setMode, goal, setGoal, casePath, setCasePath,
    readiness, targets, cases, selectedTarget, selectedCase, requestId, snapshot, streamError, startError,
    evidenceTab, setEvidenceTab, selectedStepId, setSelectedStepId, saveYamlState, controlsLocked, canStart, connection, connectionLabel, refresh, start, cancel, saveYaml, newRun,
  };
}

export type DeviceWorkspace = ReturnType<typeof useDeviceWorkspace>;
