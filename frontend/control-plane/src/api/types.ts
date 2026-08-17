export type PlatformId = 'android' | 'web' | 'windows' | 'macos';
export type RunMode = 'explore' | 'strict';
export type TaskStatus =
  | 'preparing'
  | 'running'
  | 'finalizing'
  | 'success'
  | 'failed'
  | 'inconclusive'
  | 'cancelled'
  | 'error';
export type EvidenceTab = 'screen' | 'ui-tree' | 'logs';
export type LoadState = 'idle' | 'loading' | 'ready' | 'error';

export interface ApiErrorBody {
  code: string;
  message: string;
  action: string;
  details?: unknown;
}

export interface PlatformOption { id: PlatformId; label: string }
export interface WorkspaceSummary { name: string; initialized: boolean }
export interface ActiveTaskSummary {
  requestId: string;
  runId: string | null;
  platform: PlatformId;
  targetId: string;
  mode: RunMode;
  status: TaskStatus;
}
export interface BootstrapResponse {
  apiVersion: string;
  platforms: PlatformOption[];
  workspace: WorkspaceSummary;
  busy: boolean;
  activeTask: ActiveTaskSummary | null;
}

export type ReadinessStatus = 'ready' | 'unavailable' | 'error';
export interface ReadinessRecord { status: ReadinessStatus; message: string; action: string }
export interface ReadinessResponse {
  platform: PlatformId;
  workspace: ReadinessRecord;
  provider: ReadinessRecord;
  target: ReadinessRecord;
  strict: ReadinessRecord;
}

export interface TargetRecord {
  id: string;
  label: string;
  description: string;
  status: string;
  selectable: boolean;
  isDefault: boolean;
  metadata: Record<string, unknown>;
}
export interface TargetsResponse { platform: PlatformId; targetLabel: string; targets: TargetRecord[] }

export interface CaseRecord {
  path: string;
  id: string;
  name: string;
  platform: PlatformId | null;
  commandCount: number;
  requiresAiAssertion: boolean;
  validationStatus: 'validated' | 'invalid' | string;
  selectable: boolean;
  diagnostics: string[];
}
export interface CasesResponse { platform: PlatformId; cases: CaseRecord[]; truncated: boolean }

export interface TimelineEvent {
  sequence: number;
  time?: string;
  phase?: string;
  stepId?: string;
  label?: string;
  tool?: string | null;
  status?: string;
  durationMs?: number | null;
  message?: string;
  level?: string;
  payload?: unknown;
  toolCallId?: string;
  toolArguments?: unknown;
  toolOutputPreview?: unknown;
}
export interface RunSnapshot extends ActiveTaskSummary {
  source: { goal?: string; casePath?: string };
  startedAt: string;
  completedAt: string | null;
  cancelRequested: boolean;
  events: TimelineEvent[];
  activeStep: { stepId: string; label?: string } | null;
  result: Record<string, unknown> | null;
  summary: string;
  screenshotRevision: number;
  uiSnapshotRevision: number;
  evidenceAvailable: boolean;
  reportAvailable: boolean;
  terminal: boolean;
}
export type StartRunPayload =
  | { mode: 'explore'; platform: PlatformId; targetId: string; goal: string }
  | { mode: 'strict'; platform: PlatformId; targetId: string; casePath: string };
export interface StartRunResponse { requestId: string }
export interface UiSnapshotResponse {
  revision: number;
  timestamp: string | null;
  stepId: string | null;
  mimeType: string;
  format: string;
  content: string;
}
export interface StepArtifact {
  kind: 'screenshot' | 'ui_snapshot';
  phase: string;
  timestamp: string | null;
  mimeType: string;
  format?: string;
  contentBase64?: string;
  content?: string;
  error?: string;
  sizeBytes?: number;
}
export interface StepArtifactsResponse {
  available: boolean;
  stepId: string;
  artifacts: StepArtifact[];
  message: string | null;
}
export interface ReplayFrame {
  index: number;
  timestamp: number | null;
  mimeType: string;
  contentBase64?: string;
  error?: string;
  sizeBytes?: number;
}
export interface ReplayFramesResponse { available: boolean; frames: ReplayFrame[]; message: string | null }
export interface ReplayVideoResponse {
  available: boolean;
  videoUrl: string | null;
  mimeType?: string;
  sizeBytes?: number;
}

export interface AzureProviderConfig {
  type: 'azure_openai';
  modelName: string;
  baseUrl: string;
  apiKey: string;
}
export interface GitHubProviderConfig {
  type: 'github_copilot';
  modelName: string;
  authenticated: true;
}
export type ProviderConfig = AzureProviderConfig | GitHubProviderConfig;
export type ConfigResponse =
  | { configured: false; provider: null }
  | { configured: true; provider: ProviderConfig };
export interface AzureConfigPayload { baseUrl: string; modelName: string; apiKey: string }
export type DeviceFlowStatus = 'waiting' | 'success' | 'failed' | 'expired' | 'cancelled';
export interface GitHubDeviceFlowResponse {
  authRequestId: string;
  verificationUri: string;
  userCode: string;
  expiresAt: string;
  pollIntervalSeconds: number;
  status: DeviceFlowStatus;
  message?: string;
}
export interface ConnectionTestResponse {
  success: true;
  provider: 'azure_openai' | 'github_copilot';
  modelName: string;
  durationMs: number;
}

export interface RequestResource<T> {
  state: LoadState;
  data: T | null;
  error: ApiErrorBody | null;
}
