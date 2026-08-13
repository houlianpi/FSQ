import type {
  ApiErrorBody,
  BootstrapResponse,
  CasesResponse,
  PlatformId,
  ReadinessResponse,
  ReplayFramesResponse,
  ReplayVideoResponse,
  RunSnapshot,
  StartRunPayload,
  StartRunResponse,
  TargetsResponse,
  StepArtifactsResponse,
  UiSnapshotResponse,
} from './types';

const API_BASE = '/api/control-plane';
const platforms = new Set<PlatformId>(['android', 'web', 'windows', 'macos']);
const modes = new Set(['explore', 'strict']);
const statuses = new Set(['preparing', 'running', 'finalizing', 'success', 'failed', 'inconclusive', 'cancelled', 'error']);
const readinessStatuses = new Set(['ready', 'unavailable', 'error']);

export class ControlPlaneApiError extends Error {
  readonly status: number;
  readonly body: ApiErrorBody;

  constructor(status: number, body: ApiErrorBody) {
    super(body.message);
    this.name = 'ControlPlaneApiError';
    this.status = status;
    this.body = body;
  }
}

async function responseError(response: Response): Promise<ControlPlaneApiError> {
  const candidate = await response.json().catch(() => null) as Partial<ApiErrorBody> | null;
  return new ControlPlaneApiError(response.status, {
    code: candidate?.code ?? 'request_failed',
    message: candidate?.message ?? `Request failed (${response.status}).`,
    action: candidate?.action ?? 'Retry the request.',
    details: candidate?.details,
  });
}

function invalidResponse(path: string, detail: string): never {
  throw new ControlPlaneApiError(200, {
    code: 'invalid_response',
    message: 'The Control Plane server returned an invalid response.',
    action: 'Restart or update the local Control Plane server and retry.',
    details: { path, detail },
  });
}

function record(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}
function string(value: unknown): value is string { return typeof value === 'string'; }
function nullableString(value: unknown): value is string | null { return value === null || string(value); }
function bool(value: unknown): value is boolean { return typeof value === 'boolean'; }
function finiteNumber(value: unknown): value is number { return typeof value === 'number' && Number.isFinite(value); }
function nonNegativeInteger(value: unknown): value is number { return finiteNumber(value) && Number.isInteger(value) && value >= 0; }
function platform(value: unknown): value is PlatformId { return string(value) && platforms.has(value as PlatformId); }
function arrayOf(value: unknown, predicate: (item: unknown) => boolean): boolean { return Array.isArray(value) && value.every(predicate); }

function activeTask(value: unknown): boolean {
  return record(value) && string(value.requestId) && nullableString(value.runId) && platform(value.platform)
    && string(value.targetId) && string(value.mode) && modes.has(value.mode) && string(value.status) && statuses.has(value.status);
}
function readinessRecord(value: unknown): boolean {
  return record(value) && string(value.status) && readinessStatuses.has(value.status) && string(value.message) && string(value.action);
}
function timelineEvent(value: unknown): boolean {
  if (!record(value) || !nonNegativeInteger(value.sequence)) return false;
  return ['time', 'phase', 'stepId', 'label', 'status', 'message', 'level'].every((key) => value[key] === undefined || string(value[key]))
    && (value.tool === undefined || nullableString(value.tool))
    && (value.durationMs === undefined || value.durationMs === null || finiteNumber(value.durationMs));
}

export function validateRunSnapshot(value: unknown, path = 'run snapshot'): RunSnapshot {
  if (!activeTask(value) || !record(value)) invalidResponse(path, 'Invalid task identity or discriminants.');
  const source = value.source;
  const activeStep = value.activeStep;
  const validSource = record(source)
    && (source.goal === undefined || string(source.goal))
    && (source.casePath === undefined || string(source.casePath))
    && (value.mode === 'explore' ? string(source.goal) && source.casePath === undefined : string(source.casePath) && source.goal === undefined);
  const validActiveStep = activeStep === null || (record(activeStep) && string(activeStep.stepId) && (activeStep.label === undefined || string(activeStep.label)));
  if (!validSource || !string(value.startedAt) || !nullableString(value.completedAt) || !bool(value.cancelRequested)
    || !arrayOf(value.events, timelineEvent) || !validActiveStep || !(value.result === null || record(value.result))
    || !string(value.summary) || !nonNegativeInteger(value.screenshotRevision) || !nonNegativeInteger(value.uiSnapshotRevision)
    || !bool(value.evidenceAvailable) || !bool(value.reportAvailable) || !bool(value.terminal)) {
    invalidResponse(path, 'Invalid run snapshot fields.');
  }
  return value as unknown as RunSnapshot;
}

function validateBootstrap(value: unknown): BootstrapResponse {
  if (!record(value) || !string(value.apiVersion)
    || !arrayOf(value.platforms, (item) => record(item) && platform(item.id) && string(item.label))
    || !record(value.workspace) || !string(value.workspace.name) || !bool(value.workspace.initialized)
    || !bool(value.busy) || !(value.activeTask === null || activeTask(value.activeTask))) invalidResponse('bootstrap', 'Invalid bootstrap fields.');
  return value as unknown as BootstrapResponse;
}
function validateReadiness(value: unknown): ReadinessResponse {
  if (!record(value) || !platform(value.platform) || !readinessRecord(value.workspace) || !readinessRecord(value.provider)
    || !readinessRecord(value.target) || !readinessRecord(value.strict)) invalidResponse('readiness', 'Invalid readiness fields.');
  return value as unknown as ReadinessResponse;
}
function validateTargets(value: unknown): TargetsResponse {
  const target = (item: unknown) => record(item) && string(item.id) && string(item.label) && string(item.description)
    && string(item.status) && bool(item.selectable) && bool(item.isDefault) && record(item.metadata);
  if (!record(value) || !platform(value.platform) || !string(value.targetLabel) || !arrayOf(value.targets, target)) invalidResponse('targets', 'Invalid target fields.');
  return value as unknown as TargetsResponse;
}
function validateCases(value: unknown): CasesResponse {
  const caseRecord = (item: unknown) => record(item) && string(item.path) && string(item.id) && string(item.name)
    && (item.platform === null || platform(item.platform)) && nonNegativeInteger(item.commandCount) && bool(item.requiresAiAssertion)
    && string(item.validationStatus) && bool(item.selectable) && arrayOf(item.diagnostics, string);
  if (!record(value) || !platform(value.platform) || !arrayOf(value.cases, caseRecord) || !bool(value.truncated)) invalidResponse('cases', 'Invalid case fields.');
  return value as unknown as CasesResponse;
}
function validateStart(value: unknown): StartRunResponse {
  if (!record(value) || !string(value.requestId) || !value.requestId) invalidResponse('start run', 'Missing requestId.');
  return value as unknown as StartRunResponse;
}
function validateUiSnapshot(value: unknown): UiSnapshotResponse {
  if (!record(value) || !nonNegativeInteger(value.revision) || !nullableString(value.timestamp) || !nullableString(value.stepId)
    || !string(value.mimeType) || !string(value.format) || !string(value.content)) invalidResponse('ui snapshot', 'Invalid UI snapshot fields.');
  return value as unknown as UiSnapshotResponse;
}
function validateStepArtifacts(value: unknown): StepArtifactsResponse {
  const artifact = (item: unknown) => record(item) && ['screenshot', 'ui_snapshot'].includes(String(item.kind))
    && string(item.phase) && nullableString(item.timestamp) && string(item.mimeType)
    && (item.format === undefined || string(item.format)) && (item.contentBase64 === undefined || string(item.contentBase64))
    && (item.content === undefined || string(item.content)) && (item.error === undefined || string(item.error))
    && (item.sizeBytes === undefined || nonNegativeInteger(item.sizeBytes))
    && (string(item.error) || (item.kind === 'screenshot' ? string(item.contentBase64) : string(item.content)));
  if (!record(value) || !bool(value.available) || !string(value.stepId) || !arrayOf(value.artifacts, artifact) || !nullableString(value.message)) invalidResponse('step artifacts', 'Invalid step artifact fields.');
  return value as unknown as StepArtifactsResponse;
}
function validateReplayFrames(value: unknown): ReplayFramesResponse {
  const frame = (item: unknown) => record(item) && nonNegativeInteger(item.index) && (item.timestamp === null || finiteNumber(item.timestamp)) && string(item.mimeType)
    && (item.contentBase64 === undefined || string(item.contentBase64)) && (item.error === undefined || string(item.error))
    && (item.sizeBytes === undefined || nonNegativeInteger(item.sizeBytes)) && (string(item.contentBase64) || string(item.error));
  if (!record(value) || !bool(value.available) || !arrayOf(value.frames, frame) || !nullableString(value.message)) invalidResponse('replay frames', 'Invalid replay frame fields.');
  return value as unknown as ReplayFramesResponse;
}
function validateReplayVideo(value: unknown): ReplayVideoResponse {
  if (!record(value) || !bool(value.available) || !nullableString(value.videoUrl)
    || (value.mimeType !== undefined && !string(value.mimeType)) || (value.sizeBytes !== undefined && !nonNegativeInteger(value.sizeBytes))) invalidResponse('replay video', 'Invalid replay video fields.');
  return value as unknown as ReplayVideoResponse;
}

async function jsonRequest<T>(path: string, validate: (value: unknown) => T, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  });
  if (!response.ok) throw await responseError(response);
  const value: unknown = await response.json().catch(() => invalidResponse(path, 'Response body is not JSON.'));
  return validate(value);
}

export function toApiError(error: unknown): ApiErrorBody {
  if (error instanceof ControlPlaneApiError) return error.body;
  if (error instanceof DOMException && error.name === 'AbortError') {
    return { code: 'aborted', message: 'Request cancelled.', action: 'Retry if needed.' };
  }
  return {
    code: 'network_error',
    message: error instanceof Error ? error.message : 'The Control Plane request failed.',
    action: 'Check the local server and retry.',
  };
}

export const controlPlaneClient = {
  bootstrap: (signal?: AbortSignal) => jsonRequest('/bootstrap', validateBootstrap, { signal }),
  readiness: (platform: PlatformId, signal?: AbortSignal) =>
    jsonRequest(`/readiness?platform=${encodeURIComponent(platform)}`, validateReadiness, { signal }),
  targets: (platform: PlatformId, signal?: AbortSignal) =>
    jsonRequest(`/targets?platform=${encodeURIComponent(platform)}`, validateTargets, { signal }),
  cases: (platform: PlatformId, signal?: AbortSignal) =>
    jsonRequest(`/cases?platform=${encodeURIComponent(platform)}`, validateCases, { signal }),
  startRun: (payload: StartRunPayload) => jsonRequest('/runs', validateStart, { method: 'POST', body: JSON.stringify(payload) }),
  cancelRun: (requestId: string) => jsonRequest(`/runs/${encodeURIComponent(requestId)}/cancel`, (value) => validateRunSnapshot(value, 'cancel run'), { method: 'POST', body: '{}' }),
  runSnapshot: (requestId: string, signal?: AbortSignal) => jsonRequest(`/runs/${encodeURIComponent(requestId)}`, validateRunSnapshot, { signal }),
  streamUrl: (requestId: string, afterSequence: number) =>
    `${API_BASE}/runs/${encodeURIComponent(requestId)}/stream?afterSequence=${afterSequence}`,
  screenUrl: (requestId: string, revision: number) =>
    `${API_BASE}/runs/${encodeURIComponent(requestId)}/screen?revision=${revision}`,
  screen: async (requestId: string, revision: number, signal?: AbortSignal) => {
    const response = await fetch(`${API_BASE}/runs/${encodeURIComponent(requestId)}/screen?revision=${revision}`, { signal });
    if (!response.ok) throw await responseError(response);
    const mimeType = response.headers.get('Content-Type');
    if (!mimeType?.startsWith('image/')) invalidResponse('screen', 'Screenshot content type is not an image.');
    const blob = await response.blob();
    if (!blob.size) invalidResponse('screen', 'Screenshot body is empty.');
    return blob;
  },
  uiSnapshot: (requestId: string, signal?: AbortSignal) =>
    jsonRequest(`/runs/${encodeURIComponent(requestId)}/ui-snapshot`, validateUiSnapshot, { signal }),
  stepArtifacts: (requestId: string, stepId: string, signal?: AbortSignal) =>
    jsonRequest(`/runs/${encodeURIComponent(requestId)}/step-artifacts/${encodeURIComponent(stepId)}`, validateStepArtifacts, { signal }),
  replayFrames: (requestId: string, signal?: AbortSignal) =>
    jsonRequest(`/runs/${encodeURIComponent(requestId)}/replay`, validateReplayFrames, { signal }),
  replayVideo: (requestId: string, signal?: AbortSignal) =>
    jsonRequest(`/runs/${encodeURIComponent(requestId)}/replay-video`, validateReplayVideo, { signal }),
  uploadReplayVideo: (requestId: string, mimeType: string, videoBase64: string, signal?: AbortSignal) =>
    jsonRequest(`/runs/${encodeURIComponent(requestId)}/replay-video`, validateReplayVideo, { method: 'POST', body: JSON.stringify({ mimeType, videoBase64 }), signal }),
};

export type ControlPlaneClient = typeof controlPlaneClient;
