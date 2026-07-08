const state = {
  currentRequestId: null,
  progressTimer: null,
  progressStream: null,
  progressScrollScheduled: false,
  replayRequestId: null,
  previewToken: null,
  pendingReplayVideoCleanup: null,
  replayVideoInFlight: false,
  progressSequence: 0,
  lastProgressSequence: 0,
  progressDetailOpenState: new Map(),
  selectedProgressItem: null,
  activeProgressItem: null,
  activeProgressItemClearTimer: null,
  selectedProgressRunId: false,
  finishingRun: false,
  activeRunMode: 'goal',
  modeStates: {
    goal: createRunModeState(),
    yaml: createRunModeState(),
    'strict-yaml': createRunModeState(),
  },
  yamlActiveView: 'input',
  yamlInputContent: '',
  yamlRecordedContent: '',
  yamlInputDisplay: null,
  yamlRecordedDisplay: null,
  yamlInputLastPreviewPath: '',
  selectedYamlRegion: null,
  selectedYamlStepCard: null,
  selectedYamlCaseSummary: null,
  selectedYamlCaseTitle: null,
  activeYamlStepCard: null,
  activeYamlStepClearTimer: null,
  stepArtifactPreviewActive: false,
  stepArtifactStepKey: null,
  currentExecutionMode: null,
  platformId: null,
  platformLabel: null,
};

function createRunModeState() {
  return {
    caseYamlValue: '',
    progressHtml: '',
    progressRunIdText: '',
    progressRunIdValue: '',
    progressRunIdHidden: true,
    progressSequence: 0,
    lastProgressSequence: 0,
    progressDetailOpenEntries: [],
    yamlActiveView: '',
    yamlInputContent: '',
    yamlInputDisplay: null,
    yamlInputLastPreviewPath: '',
    yamlInputStatusText: '',
    yamlInputStatusClassName: 'yaml-status yaml-status-neutral',
    yamlInputStatusHidden: true,
    yamlInputHtml: '',
    yamlRecordedContent: '',
    yamlRecordedDisplay: null,
    yamlRecordedStatusText: '',
    yamlRecordedStatusClassName: 'yaml-status yaml-status-neutral',
    yamlRecordedStatusHidden: true,
    yamlRecordedHtml: '',
  };
}

const REPLAY_FAST_SAME_EVENT_DELAY_MS = 250;
const REPLAY_FAST_ACTION_DELAY_MS = 900;
const REPLAY_FAST_MAX_DELAY_MS = 1500;
const REPLAY_FAST_FALLBACK_DELAY_MS = 500;
const REPLAY_FAST_FINAL_FRAME_HOLD_MS = 700;
const REPLAY_FAST_TIME_SCALE = 10;
const PROGRESS_POLL_INTERVAL_MS = 750;
const CONTROL_PANEL_WIDTH_STORAGE_KEY = 'fsqPlayground.controlPanelWidth';
const CONTROL_PANEL_MIN_WIDTH = 300;
const CONTROL_PANEL_MAX_WIDTH = 720;
const PREVIEW_PANEL_MIN_WIDTH = 360;
const YAML_SELECTABLE_REGION_SELECTOR = '.yaml-param-row, .yaml-metadata-item, .yaml-step-card, .yaml-case-title-row, .yaml-case-summary';
const YAML_STEP_CENTER_TOLERANCE_RATIO = 0.15;

const els = {
  shell: document.querySelector('.shell'),
  controlPanel: document.querySelector('.control-panel'),
  panelResizer: document.getElementById('panel-resizer'),
  status: document.getElementById('server-status'),
  refresh: document.getElementById('refresh'),
  deviceSelect: document.getElementById('device-select'),
  sessionMessage: document.getElementById('session-message'),
  goal: document.getElementById('goal'),
  caseYaml: document.getElementById('case-yaml'),
  yamlPathRow: document.getElementById('yaml-path-row'),
  yamlSection: document.getElementById('yaml-section'),
  yamlTabs: document.querySelector('.yaml-tabs'),
  yamlInputTab: document.getElementById('yaml-input-tab'),
  yamlRecordedTab: document.getElementById('yaml-recorded-tab'),
  yamlProgressTab: document.getElementById('yaml-progress-tab'),
  yamlInputPane: document.getElementById('yaml-input-pane'),
  yamlRecordedPane: document.getElementById('yaml-recorded-pane'),
  yamlInputStatus: document.getElementById('yaml-input-status'),
  yamlRecordedStatus: document.getElementById('yaml-recorded-status'),
  yamlInputViewer: document.getElementById('yaml-input-viewer'),
  yamlRecordedViewer: document.getElementById('yaml-recorded-viewer'),
  runSelected: document.getElementById('run-selected'),
  runModeInputs: Array.from(document.querySelectorAll('input[name="run-mode"]')),
  progressRunId: document.getElementById('progress-run-id'),
  progress: document.getElementById('progress'),
  replayVideo: document.getElementById('replay-video'),
  screenshot: document.getElementById('screenshot'),
  previewEmpty: document.getElementById('preview-empty'),
  previewTab: document.getElementById('preview-tab'),
  reportTab: document.getElementById('report-tab'),
  previewPane: document.getElementById('preview-pane'),
  progressPane: document.getElementById('progress-pane'),
  reportPane: document.getElementById('report-pane'),
  reportContent: document.getElementById('report-content'),
  stepArtifactPreview: document.getElementById('step-artifact-preview'),
};

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.error || `${response.status} ${response.statusText}`);
  }
  return data;
}

async function refreshAll() {
  await refreshRuntime();
  await refreshStatus();
  if (platformRequiresSession()) {
    await refreshSetup();
    await autoCreateSessionIfPossible({ silent: true });
    await refreshStatus();
  }
}

function clearPage() {
  if (state.currentRequestId) return;
  stopProgressUpdates();
  resetRunModeStates();
  state.replayRequestId = null;
  state.previewToken = null;
  state.currentRequestId = null;
  state.progressSequence = 0;
  state.lastProgressSequence = 0;
  state.progressDetailOpenState.clear();
  state.currentExecutionMode = null;
  state.finishingRun = false;
  clearStepArtifactPreview();

  els.goal.value = '';
  els.caseYaml.value = '';
  clearYamlInput();
  clearRecordedYaml();
  clearRunId();
  clearActiveProgressItem();
  clearSelectedProgressItem();
  els.progress.innerHTML = '';
  els.reportContent.textContent = '';
  clearPreview();
  setRunButtonIdle();

  const goalMode = els.runModeInputs.find((input) => input.value === 'goal');
  if (goalMode) goalMode.checked = true;
  updateRunMode();
  showRightTab('preview');
  refreshStatus();
}

async function refreshStatus() {
  try {
    const status = await api('/status');
    setServerStatus(status.busy ? 'Running' : 'Ready', status.busy ? 'running' : 'ready');
    els.deviceSelect.disabled = Boolean(state.currentRequestId || state.finishingRun || status.busy);
    if (state.currentRequestId) {
      setRunButtonCancel();
    } else if (state.finishingRun) {
      setRunButtonCancel({ disabled: true });
    } else {
      setRunButtonIdle({ disabled: Boolean(status.busy) });
    }
    if (!platformRequiresSession()) {
      setNoSessionPlatformMessage();
    } else if (status.session?.connected) {
      els.sessionMessage.textContent = `Connected to ${status.session.displayName || status.session.deviceId}`;
    } else {
      els.sessionMessage.textContent = 'No active session.';
    }
  } catch (error) {
    setServerStatus(error.message, 'error');
  }
}

function setServerStatus(text, status) {
  els.status.textContent = text;
  els.status.className = `status-pill status-${status}`;
}

async function refreshSetup() {
  try {
    const setup = await api('/session/setup');
    const options = setup.targets || [];
    els.deviceSelect.innerHTML = '';
    for (const target of options) {
      const option = document.createElement('option');
      option.value = target.id;
      option.textContent = target.description ? `${target.label} (${target.description})` : target.label;
      if (target.isDefault || setup.fields?.[0]?.defaultValue === target.id) option.selected = true;
      els.deviceSelect.appendChild(option);
    }
    if (setup.notice) {
      els.sessionMessage.textContent = `${setup.notice.message}: ${setup.notice.description || ''}`;
    }
  } catch (error) {
    els.sessionMessage.textContent = error.message;
  }
}

async function refreshRuntime() {
  try {
    const runtime = await api('/runtime-info');
    state.platformId = runtime.platformId || null;
    state.platformLabel = runtime.interface?.type || (runtime.platformId ? capitalize(runtime.platformId) : null);
    if (!platformRequiresSession()) {
      setNoSessionPlatformMessage();
    }
    return runtime;
  } catch (error) {
    setServerStatus(error.message, 'error');
    return null;
  }
}

function platformRequiresSession() {
  return state.platformId === 'android';
}

function setNoSessionPlatformMessage() {
  const label = state.platformLabel || (state.platformId ? capitalize(state.platformId) : 'This');
  els.sessionMessage.textContent = `${label} harness — no device session required.`;
}

function capitalize(value) {
  return value ? value.charAt(0).toUpperCase() + value.slice(1) : value;
}

async function autoCreateSessionIfPossible({ silent = false } = {}) {
  try {
    const session = await api('/session');
    if (session.connected) return true;
    const result = await api('/session/auto', { method: 'POST', body: JSON.stringify({}) });
    if (!silent) {
      els.sessionMessage.textContent = `Connected to ${result.session.displayName || result.session.deviceId}`;
    } else if (result.session?.connected) {
      els.sessionMessage.textContent = `Connected to ${result.session.displayName || result.session.deviceId}`;
    }
    return true;
  } catch (error) {
    if (!silent || error.message.includes('Multiple') || error.message.includes('No online')) {
      els.sessionMessage.textContent = error.message;
    }
    return false;
  }
}

async function ensureSession() {
  if (!platformRequiresSession()) return true;
  try {
    const session = await api('/session');
    if (session.connected) return true;
  } catch (error) {
    els.sessionMessage.textContent = error.message;
    return false;
  }
  if (await autoCreateSessionIfPossible()) return true;
  if (els.deviceSelect.value) {
    els.sessionMessage.textContent = 'Automatic session selection is required before running.';
  }
  return false;
}

async function runGoal() {
  const goal = els.goal.value.trim();
  if (!goal) return;
  await startExecution({ goal });
}

async function runYaml() {
  const caseYamlPath = els.caseYaml.value.trim();
  if (!caseYamlPath) return;
  if (currentRunMode() === 'strict-yaml') {
    await startExecution({ strictCaseYamlPath: caseYamlPath });
    return;
  }
  await startExecution({ caseYamlPath });
}

async function runSelected() {
  if (state.currentRequestId) {
    await cancelExecution();
    return;
  }
  if (currentRunMode() === 'yaml' || currentRunMode() === 'strict-yaml') {
    await runYaml();
    return;
  }
  await runGoal();
}

function currentRunMode() {
  return els.runModeInputs.find((input) => input.checked)?.value || 'goal';
}

function currentModeState(mode = state.activeRunMode) {
  return state.modeStates[mode] || state.modeStates.goal;
}

function resetRunModeStates() {
  state.modeStates = {
    goal: createRunModeState(),
    yaml: createRunModeState(),
    'strict-yaml': createRunModeState(),
  };
}

function saveRunModeState(mode = state.activeRunMode) {
  const modeState = currentModeState(mode);
  captureProgressDetailState();
  modeState.caseYamlValue = els.caseYaml.value;
  modeState.progressHtml = els.progress.innerHTML;
  modeState.progressRunIdText = els.progressRunId.textContent;
  modeState.progressRunIdValue = els.progressRunId.dataset.runId || '';
  modeState.progressRunIdHidden = els.progressRunId.hidden;
  modeState.progressSequence = state.progressSequence;
  modeState.lastProgressSequence = state.lastProgressSequence;
  modeState.progressDetailOpenEntries = Array.from(state.progressDetailOpenState.entries());
  modeState.yamlActiveView = state.yamlActiveView;
  modeState.yamlInputContent = state.yamlInputContent;
  modeState.yamlInputDisplay = state.yamlInputDisplay;
  modeState.yamlInputLastPreviewPath = state.yamlInputLastPreviewPath;
  modeState.yamlInputStatusText = els.yamlInputStatus.textContent;
  modeState.yamlInputStatusClassName = els.yamlInputStatus.className;
  modeState.yamlInputStatusHidden = els.yamlInputStatus.hidden;
  modeState.yamlInputHtml = els.yamlInputViewer.innerHTML;
  modeState.yamlRecordedContent = state.yamlRecordedContent;
  modeState.yamlRecordedDisplay = state.yamlRecordedDisplay;
  modeState.yamlRecordedStatusText = els.yamlRecordedStatus.textContent;
  modeState.yamlRecordedStatusClassName = els.yamlRecordedStatus.className;
  modeState.yamlRecordedStatusHidden = els.yamlRecordedStatus.hidden;
  modeState.yamlRecordedHtml = els.yamlRecordedViewer.innerHTML;
}

function restoreRunModeState(mode = state.activeRunMode) {
  const modeState = currentModeState(mode);
  els.caseYaml.value = modeState.caseYamlValue;
  els.progress.innerHTML = modeState.progressHtml;
  els.progressRunId.textContent = modeState.progressRunIdText;
  if (modeState.progressRunIdValue) {
    els.progressRunId.dataset.runId = modeState.progressRunIdValue;
  } else {
    delete els.progressRunId.dataset.runId;
  }
  els.progressRunId.hidden = modeState.progressRunIdHidden;
  state.progressSequence = modeState.progressSequence;
  state.lastProgressSequence = modeState.lastProgressSequence;
  state.progressDetailOpenState = new Map(modeState.progressDetailOpenEntries);
  state.yamlInputContent = modeState.yamlInputContent;
  state.yamlInputDisplay = modeState.yamlInputDisplay;
  state.yamlInputLastPreviewPath = modeState.yamlInputLastPreviewPath;
  els.yamlInputStatus.textContent = modeState.yamlInputStatusText;
  els.yamlInputStatus.className = modeState.yamlInputStatusClassName;
  els.yamlInputStatus.hidden = modeState.yamlInputStatusHidden;
  els.yamlInputViewer.innerHTML = modeState.yamlInputHtml;
  state.yamlRecordedContent = modeState.yamlRecordedContent;
  state.yamlRecordedDisplay = modeState.yamlRecordedDisplay;
  els.yamlRecordedStatus.textContent = modeState.yamlRecordedStatusText;
  els.yamlRecordedStatus.className = modeState.yamlRecordedStatusClassName;
  els.yamlRecordedStatus.hidden = modeState.yamlRecordedStatusHidden;
  els.yamlRecordedViewer.innerHTML = modeState.yamlRecordedHtml;
  state.yamlActiveView = modeState.yamlActiveView || defaultYamlViewForMode(mode);
  stripTransientModeClasses();
  bindProgressDetailToggles();
  clearSelectedYamlRegion();
  clearActiveYamlStepCard();
  clearSelectedProgressRunId();
  clearSelectedProgressItem();
  clearActiveProgressItem();
}

function stripTransientModeClasses() {
  els.yamlInputViewer.querySelectorAll('.yaml-region-selected, .yaml-step-card-active')
    .forEach((element) => element.classList.remove('yaml-region-selected', 'yaml-step-card-active'));
  els.yamlRecordedViewer.querySelectorAll('.yaml-region-selected, .yaml-step-card-active')
    .forEach((element) => element.classList.remove('yaml-region-selected', 'yaml-step-card-active'));
  els.progress.querySelectorAll('.progress-item-selected, .progress-item-active')
    .forEach((element) => element.classList.remove('progress-item-selected', 'progress-item-active'));
}

function bindProgressDetailToggles() {
  for (const detail of els.progress.querySelectorAll('.progress-detail[data-detail-key]')) {
    detail.addEventListener('toggle', () => {
      state.progressDetailOpenState.set(detail.dataset.detailKey, detail.open);
    });
  }
}

function defaultYamlViewForMode(mode) {
  if (mode === 'strict-yaml') return 'input';
  return 'progress';
}

function switchRunMode() {
  if (state.currentRequestId || state.finishingRun) return;
  saveRunModeState(state.activeRunMode);
  state.activeRunMode = currentRunMode();
  restoreRunModeState(state.activeRunMode);
  updateRunMode({ preserveView: true });
}

function updateRunMode({ preserveView = false } = {}) {
  const mode = currentRunMode();
  const hasInputYaml = mode === 'yaml' || mode === 'strict-yaml';
  els.goal.hidden = hasInputYaml;
  els.yamlPathRow.hidden = !hasInputYaml;
  els.caseYaml.disabled = !hasInputYaml || Boolean(state.currentRequestId);
  for (const input of els.runModeInputs) input.disabled = Boolean(state.currentRequestId || state.finishingRun);
  els.yamlSection.hidden = false;
  els.yamlTabs.hidden = false;
  els.yamlProgressTab.hidden = false;
  syncYamlTabOrder(mode);
  const targetView = preserveView ? state.yamlActiveView : defaultYamlViewForMode(mode);
  if (mode === 'goal') {
    els.yamlInputTab.hidden = true;
    els.yamlRecordedTab.hidden = false;
    showYamlView(targetView);
  } else if (mode === 'strict-yaml') {
    els.yamlInputTab.hidden = false;
    els.yamlRecordedTab.hidden = true;
    showYamlView(targetView);
  } else {
    els.yamlInputTab.hidden = false;
    els.yamlRecordedTab.hidden = false;
    showYamlView(targetView);
  }
  if (!state.currentRequestId && !state.finishingRun) setRunButtonIdle();
}

function syncYamlTabOrder(mode) {
  const tabs = mode === 'goal' || mode === 'yaml'
    ? [els.yamlProgressTab, els.yamlInputTab, els.yamlRecordedTab]
    : [els.yamlInputTab, els.yamlRecordedTab, els.yamlProgressTab];
  for (const tab of tabs) els.yamlTabs.appendChild(tab);
}

async function startExecution(payload) {
  if (!(await ensureSession())) return;
  state.activeRunMode = currentRunMode();
  state.currentExecutionMode = payload.strictCaseYamlPath ? 'strict-yaml' : (payload.caseYamlPath ? 'yaml' : 'goal');
  state.progressSequence = 0;
  state.lastProgressSequence = 0;
  state.progressDetailOpenState.clear();
  state.replayRequestId = null;
  clearStepArtifactPreview();
  clearRecordedYaml();
  clearRunId();
  clearActiveProgressItem();
  clearSelectedProgressItem();
  els.progress.innerHTML = '';
  els.reportContent.textContent = 'No report yet.';
  clearPreview('Loading live preview...');
  highlightRunStartSummary();
  els.refresh.disabled = true;
  els.deviceSelect.disabled = true;
  try {
    const result = await api('/execute', { method: 'POST', body: JSON.stringify(payload) });
    state.currentRequestId = result.requestId;
    state.finishingRun = false;
    state.replayRequestId = result.requestId;
    setRunButtonCancel();
    updateRunMode();
    startProgressPolling();
    await refreshStatus();
  } catch (error) {
    state.currentExecutionMode = null;
    state.finishingRun = false;
    els.refresh.disabled = false;
    els.deviceSelect.disabled = false;
    updateRunMode();
    appendProgress(`Error: ${error.message}`);
  }
}

function highlightRunStartSummary() {
  if (state.currentExecutionMode !== 'strict-yaml') return;
  const title = els.yamlInputViewer.querySelector('.yaml-case-title-row');
  if (title) {
    selectYamlRegion(title);
    return;
  }
  const summary = els.yamlInputViewer.querySelector('.yaml-case-summary');
  if (summary) selectYamlRegion(summary);
}

async function cancelExecution() {
  const requestId = state.currentRequestId;
  if (!requestId) return;
  setRunButtonCancel({ disabled: true });
  try {
    const progress = await api(`/cancel/${encodeURIComponent(requestId)}`, { method: 'POST', body: JSON.stringify({}) });
    stopProgressUpdates();
    appendProgress('Cancelled by user', null, [], 'failed');
    state.currentRequestId = null;
    state.currentExecutionMode = null;
    state.finishingRun = false;
    state.replayRequestId = progress.result?.runId || progress.runId || state.replayRequestId;
    setRunButtonIdle();
    updateRunMode();
    await refreshStatus();
  } catch (error) {
    appendProgress(`Cancel error: ${error.message}`, null, [], 'failed');
    setRunButtonCancel();
  }
}

function setRunButtonCancel({ disabled = false } = {}) {
  els.runSelected.textContent = 'Cancel';
  els.runSelected.classList.remove('primary');
  els.runSelected.classList.add('secondary-button');
  els.runSelected.disabled = disabled;
}

function setRunButtonIdle({ disabled = false } = {}) {
  els.runSelected.textContent = 'Run';
  els.runSelected.classList.add('primary');
  els.runSelected.classList.remove('secondary-button');
  els.runSelected.disabled = disabled;
}

function startProgressPolling() {
  stopProgressUpdates();
  if (window.EventSource) {
    const requestId = state.currentRequestId;
    const stream = new EventSource(`/task-stream/${encodeURIComponent(requestId)}`);
    state.progressStream = stream;
    stream.onmessage = (event) => {
      try {
        applyProgress(JSON.parse(event.data));
      } catch (error) {
        appendProgress(`Progress error: ${error.message}`, null, [], 'failed');
      }
    };
    stream.onerror = () => {
      if (!state.currentRequestId) return;
      stopProgressUpdates();
      state.progressTimer = window.setInterval(refreshProgress, PROGRESS_POLL_INTERVAL_MS);
    };
    return;
  }
  state.progressTimer = window.setInterval(refreshProgress, PROGRESS_POLL_INTERVAL_MS);
  refreshProgress();
}

function stopProgressUpdates() {
  if (state.progressTimer) {
    window.clearInterval(state.progressTimer);
    state.progressTimer = null;
  }
  if (state.progressStream) {
    state.progressStream.close();
    state.progressStream = null;
  }
}

async function refreshProgress() {
  if (!state.currentRequestId) return;
  try {
    await applyProgress(await api(progressPath(state.currentRequestId)));
  } catch (error) {
    appendProgress(`Progress error: ${error.message}`, null, [], 'failed');
  }
}

async function applyProgress(progress) {
  if (!state.currentRequestId) return;
  for (const event of progress.events || []) {
    if (event.type === 'run_started') setRunId(event.run_id || event.runId);
    syncYamlStepWithProgressEvent(event);
    appendProgress(eventLabel(event), event.sequence, eventDetails(event), eventStatus(event));
    updateLastProgressSequence(event.sequence);
  }
  if (progress.preview?.token && progress.preview.token !== state.previewToken) {
    await refreshPreview(progress.requestId, progress.preview.token);
  }
  if (progress.status !== 'running') {
    stopProgressUpdates();
    state.currentRequestId = null;
    state.finishingRun = true;
    setRunButtonCancel({ disabled: true });
    scheduleClearActiveYamlStepCard();
    appendProgress(`Finished: ${progress.status}`, null, [], statusFromValue(progress.status));
    if (progress.error) appendProgress(`Error: ${progress.error}`, null, [], 'failed');
    if (progress.result?.runId) {
      setRunId(progress.result.runId);
      state.replayRequestId = progress.result.runId;
      await loadReport(progress.result.runId);
      await loadRecordedYaml(progress.result.runId, progress.result.recording || null);
      await refreshPreviewFromReplay(progress.result.runId);
    }
    if (state.replayRequestId && progress.status !== 'cancelled') {
      try {
        const replay = await loadReplayFrames(state.replayRequestId);
        appendReplayFramesProgress(replay.frames);
        appendReplayVideoGeneratingProgress();
        const replayVideo = await ensureReplayVideoGenerated(state.replayRequestId, replay.frames);
        if (replayVideo?.videoUrl) {
          appendProgress('Replay video saved', null, [], 'success');
          await showReplayVideoPreview(replayVideo.videoUrl);
          showRightTab('preview');
        } else {
          appendProgress(`Replay video was not generated: ${replayVideo?.error || 'unknown error'}`, null, [], 'failed');
        }
      } catch (error) {
        appendProgress(`Replay video was not generated: ${error.message}`, null, [], 'failed');
      }
    }
    scheduleClearActiveProgressItem();
    clearSelectedYamlRegion();
    setRunButtonIdle();
    els.refresh.disabled = false;
    els.deviceSelect.disabled = false;
    state.finishingRun = false;
    state.currentExecutionMode = null;
    updateRunMode({ preserveView: true });
    saveRunModeState(state.activeRunMode);
    await refreshStatus();
    await refreshRuntime();
  }
}

function progressPath(requestId) {
  const encoded = encodeURIComponent(requestId);
  if (state.lastProgressSequence <= 0) return `/task-progress/${encoded}`;
  return `/task-progress/${encoded}?after_sequence=${state.lastProgressSequence}`;
}

function updateLastProgressSequence(sequence) {
  if (Number.isInteger(sequence) && sequence > state.lastProgressSequence) {
    state.lastProgressSequence = sequence;
  }
}

async function refreshPreview(requestId, token) {
  try {
    const preview = await api(`/preview/${encodeURIComponent(requestId)}`);
    const src = `data:image/png;base64,${preview.screenshot}`;
    await preloadImage(src);
    clearStepArtifactPreview();
    state.previewToken = token;
    els.replayVideo.hidden = true;
    els.replayVideo.style.display = 'none';
    els.screenshot.src = src;
    els.screenshot.style.display = 'block';
    els.previewEmpty.style.display = 'none';
  } catch {
    // Preview artifacts are best-effort while strict execution is still writing evidence.
  }
}

function setRunId(runId) {
  if (!runId) return;
  els.progressRunId.textContent = `Run ID: ${runId}`;
  els.progressRunId.dataset.runId = runId;
  els.progressRunId.hidden = false;
}

function clearRunId() {
  els.progressRunId.textContent = '';
  delete els.progressRunId.dataset.runId;
  els.progressRunId.hidden = true;
  clearSelectedProgressRunId();
}

async function loadReport(runId) {
  try {
    els.reportContent.textContent = 'Loading report...';
    const report = await api(`/reports/${encodeURIComponent(runId)}?format=markdown`);
    els.reportContent.innerHTML = renderMarkdown(report.content || 'Report is empty.');
  } catch (error) {
    els.reportContent.textContent = `Unable to load report: ${error.message}`;
  }
}

async function loadInputYaml() {
  const path = els.caseYaml.value.trim();
  showYamlView('input');
  if (!path) {
    clearYamlInput();
    setYamlInputStatus('YAML path is required.', 'error');
    return;
  }
  setYamlInputStatus('Loading YAML...', 'neutral');
  try {
    const yaml = await api(`/yaml/input?path=${encodeURIComponent(path)}`);
    state.yamlInputContent = yaml.content || '';
    state.yamlInputDisplay = yaml.display || null;
    state.yamlInputLastPreviewPath = path;
    renderYamlDisplay(els.yamlInputViewer, state.yamlInputDisplay, 'YAML file is empty.');
    setYamlInputStatus('', 'success');
  } catch (error) {
    state.yamlInputContent = '';
    state.yamlInputDisplay = null;
    renderYamlEmpty(els.yamlInputViewer, '');
    setYamlInputStatus(error.message, 'error');
  }
}

async function loadRecordedYaml(runId, recording) {
  if (state.currentExecutionMode === 'strict-yaml') {
    clearRecordedYaml();
    updateRunMode();
    return;
  }
  if (!recording) {
    clearRecordedYaml();
    return;
  }
  setRecordedYamlNoContent('Loading recorded YAML...', 'neutral');
  els.yamlSection.hidden = false;
  try {
    const yaml = await api(`/yaml/recorded/${encodeURIComponent(runId)}`);
    state.yamlRecordedContent = yaml.content || '';
    state.yamlRecordedDisplay = yaml.display || null;
    if (yaml.content) {
      renderYamlDisplay(els.yamlRecordedViewer, state.yamlRecordedDisplay, 'Recorded YAML is empty.');
    } else {
      renderYamlEmpty(els.yamlRecordedViewer, recordingStatusDetails(yaml));
    }
    setYamlRecordedStatus('', 'neutral');
    els.yamlSection.hidden = false;
  } catch (error) {
    state.yamlRecordedContent = '';
    state.yamlRecordedDisplay = null;
    renderYamlEmpty(els.yamlRecordedViewer, error.message);
    setYamlRecordedStatus(error.message, 'error');
    els.yamlSection.hidden = false;
  }
}

function clearYamlInput(message = 'No YAML loaded.') {
  state.yamlInputContent = '';
  state.yamlInputDisplay = null;
  state.yamlInputLastPreviewPath = '';
  setYamlInputStatus(message === 'No YAML loaded.' ? '' : message, 'neutral');
  renderYamlEmpty(els.yamlInputViewer, message);
}

function clearRecordedYaml() {
  state.yamlRecordedContent = '';
  state.yamlRecordedDisplay = null;
  setYamlRecordedStatus('', 'neutral');
  renderYamlEmpty(els.yamlRecordedViewer, 'No recorded YAML yet.');
}

function setRecordedYamlNoContent(message, status = 'neutral') {
  state.yamlRecordedContent = '';
  state.yamlRecordedDisplay = null;
  setYamlRecordedStatus(message, status);
  renderYamlEmpty(els.yamlRecordedViewer, message);
}

function setYamlInputStatus(message, status) {
  setYamlStatus(els.yamlInputStatus, message, status);
}

function setYamlRecordedStatus(message, status) {
  setYamlStatus(els.yamlRecordedStatus, message, status);
}

function setYamlStatus(element, message, status) {
  element.hidden = !message;
  element.textContent = message;
  element.className = `yaml-status yaml-status-${status || 'neutral'}`;
}

function showYamlView(viewName) {
  const inputAvailable = !els.yamlInputTab.hidden;
  const recordedAvailable = !els.yamlRecordedTab.hidden;
  const progressAvailable = !els.yamlProgressTab.hidden;
  let selectedView = inputAvailable ? 'input' : (recordedAvailable ? 'recorded' : 'progress');
  if (viewName === 'recorded' && recordedAvailable) selectedView = 'recorded';
  if (viewName === 'progress' && progressAvailable) selectedView = 'progress';
  if (viewName === 'input' && inputAvailable) selectedView = 'input';
  const showInput = selectedView === 'input';
  const showRecorded = selectedView === 'recorded';
  const showProgress = selectedView === 'progress';
  state.yamlActiveView = selectedView;
  els.yamlInputPane.hidden = !showInput;
  els.yamlRecordedPane.hidden = !showRecorded;
  els.progressPane.hidden = !showProgress;
  els.yamlInputTab.classList.toggle('active', inputAvailable && showInput);
  els.yamlRecordedTab.classList.toggle('active', recordedAvailable && showRecorded);
  els.yamlProgressTab.classList.toggle('active', progressAvailable && showProgress);
  els.yamlInputTab.setAttribute('aria-selected', String(inputAvailable && showInput));
  els.yamlRecordedTab.setAttribute('aria-selected', String(recordedAvailable && showRecorded));
  els.yamlProgressTab.setAttribute('aria-selected', String(progressAvailable && showProgress));
}

function renderYamlDisplay(root, display, emptyMessage) {
  clearSelectedYamlRegion(root);
  clearActiveYamlStepCard(root);
  root.innerHTML = '';
  if (!display) {
    renderYamlEmpty(root, emptyMessage);
    return;
  }
  const fragment = document.createDocumentFragment();
  fragment.appendChild(renderYamlCaseTitle(display.metadata || {}));
  fragment.appendChild(renderYamlCaseSummary(display.metadata || {}));
  fragment.appendChild(renderYamlSteps(display.steps || []));
  root.appendChild(fragment);
}

function renderYamlCaseTitle(metadata) {
  const titleRow = document.createElement('div');
  titleRow.className = 'yaml-case-title-row';
  const title = document.createElement('div');
  title.className = 'yaml-case-title';
  title.textContent = metadata.title || 'Untitled case';
  titleRow.appendChild(title);
  return titleRow;
}

function renderYamlCaseSummary(metadata) {
  const summary = document.createElement('div');
  summary.className = 'yaml-case-summary';

  if (Array.isArray(metadata.tags) && metadata.tags.length > 0) {
    const tags = document.createElement('div');
    tags.className = 'yaml-tags';
    for (const tag of metadata.tags) {
      const chip = document.createElement('span');
      chip.className = 'yaml-chip yaml-chip-muted';
      chip.textContent = String(tag);
      tags.appendChild(chip);
    }
    summary.appendChild(tags);
  }

  const fields = Array.isArray(metadata.fields) ? metadata.fields : [];
  if (fields.length > 0) {
    const grid = document.createElement('div');
    grid.className = 'yaml-metadata-grid';
    for (const field of fields) {
      const item = document.createElement('div');
      item.className = 'yaml-metadata-item';
      const label = document.createElement('span');
      label.className = 'yaml-metadata-label';
      label.textContent = field.label || field.key || 'Field';
      const value = document.createElement('span');
      value.className = 'yaml-metadata-value';
      value.textContent = formatYamlValue(field.value);
      item.appendChild(label);
      item.appendChild(value);
      grid.appendChild(item);
    }
    summary.appendChild(grid);
  }
  return summary;
}

function renderYamlSteps(steps) {
  const container = document.createElement('div');
  container.className = 'yaml-step-list';
  if (!steps.length) {
    const empty = document.createElement('div');
    empty.className = 'yaml-empty';
    empty.textContent = 'No YAML steps.';
    container.appendChild(empty);
    return container;
  }
  for (const step of steps) {
    container.appendChild(renderYamlStep(step));
  }
  return container;
}

function renderYamlStep(step) {
  const card = document.createElement('div');
  card.className = 'yaml-step-card';
  card.dataset.yamlStepIndex = String(step.index || '');
  card.dataset.yamlAction = step.action || 'command';
  card.dataset.yamlActionKey = normalizeYamlActionName(step.action || 'command');
  const header = document.createElement('div');
  header.className = 'yaml-step-header';

  const index = document.createElement('span');
  index.className = 'yaml-step-index';
  index.textContent = String(step.index || '?').padStart(2, '0');
  header.appendChild(index);

  const action = document.createElement('span');
  const actionKind = step.kind || 'action';
  action.className = `yaml-action-name yaml-action-name-${actionKind}`;
  action.textContent = step.action || 'command';
  action.title = actionKind;
  header.appendChild(action);

  for (const badge of step.badges || []) {
    const chip = document.createElement('span');
    chip.className = 'yaml-chip yaml-chip-muted';
    chip.textContent = badge.label || String(badge);
    header.appendChild(chip);
  }

  card.appendChild(header);
  if ((step.params || []).length > 0) {
    card.appendChild(renderYamlParams(step.params || []));
  }
  return card;
}

function renderYamlParams(params) {
  const list = document.createElement('div');
  list.className = 'yaml-param-list';
  for (const param of params) {
    const row = document.createElement('div');
    row.className = 'yaml-param-row';
    const key = document.createElement('span');
    key.className = 'yaml-param-key';
    key.textContent = param.key || 'value';
    const value = document.createElement('span');
    value.className = `yaml-param-value yaml-param-value-${param.kind || 'scalar'}`;
    value.textContent = yamlParamDisplayValue(param);
    row.appendChild(key);
    row.appendChild(value);
    list.appendChild(row);
    if (Array.isArray(param.fields) && param.fields.length > 0) {
      list.appendChild(renderYamlNestedParams(param.fields));
    }
  }
  return list;
}

function renderYamlNestedParams(params) {
  const nested = document.createElement('div');
  nested.className = 'yaml-param-nested';
  for (const param of params) {
    const row = document.createElement('div');
    row.className = 'yaml-param-row yaml-param-row-nested';
    const key = document.createElement('span');
    key.className = 'yaml-param-key';
    key.textContent = param.key || 'value';
    const value = document.createElement('span');
    value.className = `yaml-param-value yaml-param-value-${param.kind || 'scalar'}`;
    value.textContent = yamlParamDisplayValue(param);
    row.appendChild(key);
    row.appendChild(value);
    nested.appendChild(row);
    if (Array.isArray(param.fields) && param.fields.length > 0) {
      nested.appendChild(renderYamlNestedParams(param.fields));
    }
  }
  return nested;
}

function yamlParamDisplayValue(param) {
  if (param.kind === 'secret') return `runtimeSecret: ${param.value}`;
  if ((param.kind === 'object' || param.kind === 'list') && Array.isArray(param.fields)) return '';
  return formatYamlValue(param.value);
}

function renderYamlEmpty(root, message) {
  clearSelectedYamlRegion(root);
  clearActiveYamlStepCard(root);
  root.innerHTML = '';
  if (!message) return;
  const empty = document.createElement('div');
  empty.className = 'yaml-empty';
  empty.textContent = message;
  root.appendChild(empty);
}

function formatYamlValue(value) {
  if (value === null || value === undefined) return '';
  if (Array.isArray(value)) return value.join(', ');
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

function syncYamlStepWithProgressEvent(event) {
  if (state.currentExecutionMode !== 'strict-yaml') return;
  if (!event || !['tool_call_started', 'tool_call_completed', 'tool_call_failed', 'step_completed'].includes(event.type)) return;
  const stepCard = yamlStepCardForEvent(event);
  if (!stepCard) return;
  activateYamlStepCard(stepCard);
}

function yamlStepCardForEvent(event) {
  const stepIndex = yamlStepIndexFromEvent(event);
  if (Number.isInteger(stepIndex) && stepIndex > 0) {
    const byIndex = yamlStepCardByIndex(stepIndex);
    if (byIndex) return byIndex;
  }
  const actionKey = normalizeYamlActionName(yamlActionFromEvent(event));
  if (!actionKey) return null;
  return Array.from(els.yamlInputViewer.querySelectorAll('.yaml-step-card'))
    .find((card) => card.dataset.yamlActionKey === actionKey) || null;
}

function yamlStepCardByIndex(stepIndex) {
  return Array.from(els.yamlInputViewer.querySelectorAll('.yaml-step-card'))
    .find((card) => Number(card.dataset.yamlStepIndex) === stepIndex) || null;
}

function yamlStepIndexFromEvent(event) {
  const payload = event.payload || {};
  const runnerResult = payload.runner_result || {};
  const sourceRef = runnerResult.source_ref || {};
  for (const value of [payload.step_index, payload.stepIndex]) {
    const numeric = Number(value);
    if (Number.isInteger(numeric) && numeric > 0) return numeric;
  }
  const sourceIndex = Number(sourceRef.step_index);
  if (Number.isInteger(sourceIndex) && sourceIndex >= 0) return sourceIndex + 1;
  for (const value of [payload.step_id, payload.stepId, payload.runner_step_id, payload.runnerStepId, runnerResult.step_id]) {
    const parsed = yamlStepIndexFromStepId(value);
    if (parsed) return parsed;
  }
  return null;
}

function yamlStepIndexFromStepId(value) {
  if (typeof value !== 'string') return null;
  const match = value.match(/-step-(\d+)$/);
  if (!match) return null;
  return Number.parseInt(match[1], 10);
}

function yamlActionFromEvent(event) {
  const payload = event.payload || {};
  const runnerResult = payload.runner_result || {};
  const metadata = runnerResult.metadata || payload.metadata || {};
  return payload.fsq_action_name
    || metadata.authored_action_name
    || runnerResult.action_name
    || payload.capability_name
    || event.tool_name
    || '';
}

function normalizeYamlActionName(value) {
  return String(value || '').replace(/[^a-z0-9]/gi, '').toLowerCase();
}

function activateYamlStepCard(stepCard) {
  cancelActiveYamlStepClearTimer();
  if (state.activeYamlStepCard === stepCard) {
    centerYamlStepCard(stepCard);
    return;
  }
  clearActiveYamlStepCard();
  state.activeYamlStepCard = stepCard;
  stepCard.classList.add('yaml-step-card-active');
  centerYamlStepCard(stepCard);
}

function clearActiveYamlStepCard(root = null) {
  if (!state.activeYamlStepCard) return;
  if (root && !root.contains(state.activeYamlStepCard)) return;
  cancelActiveYamlStepClearTimer();
  state.activeYamlStepCard.classList.remove('yaml-step-card-active');
  state.activeYamlStepCard = null;
}

function centerYamlStepCard(stepCard) {
  const viewer = stepCard.closest('.yaml-viewer');
  if (!viewer || !stepCard.getClientRects().length) return;
  const viewerRect = viewer.getBoundingClientRect();
  const stepRect = stepCard.getBoundingClientRect();
  const viewerCenter = viewerRect.top + viewerRect.height / 2;
  const stepCenter = stepRect.top + stepRect.height / 2;
  const tolerance = Math.max(24, viewerRect.height * YAML_STEP_CENTER_TOLERANCE_RATIO);
  if (Math.abs(stepCenter - viewerCenter) <= tolerance) return;
  stepCard.scrollIntoView({ block: 'center', behavior: 'smooth' });
}

function scheduleClearActiveYamlStepCard(delayMs = 900) {
  cancelActiveYamlStepClearTimer();
  state.activeYamlStepClearTimer = window.setTimeout(() => {
    state.activeYamlStepClearTimer = null;
    if (!state.activeYamlStepCard) return;
    state.activeYamlStepCard.classList.remove('yaml-step-card-active');
    state.activeYamlStepCard = null;
  }, delayMs);
}

function cancelActiveYamlStepClearTimer() {
  if (!state.activeYamlStepClearTimer) return;
  clearTimeout(state.activeYamlStepClearTimer);
  state.activeYamlStepClearTimer = null;
}

function clearSelectedYamlRegion(root = null) {
  if (root && state.selectedYamlRegion && !root.contains(state.selectedYamlRegion)) return;
  if (state.selectedYamlRegion) {
    state.selectedYamlRegion.classList.remove('yaml-region-selected');
  }
  if (state.selectedYamlStepCard && state.selectedYamlStepCard !== state.selectedYamlRegion) {
    state.selectedYamlStepCard.classList.remove('yaml-region-selected');
  }
  if (state.selectedYamlCaseSummary && state.selectedYamlCaseSummary !== state.selectedYamlRegion) {
    state.selectedYamlCaseSummary.classList.remove('yaml-region-selected');
  }
  if (state.selectedYamlCaseTitle && state.selectedYamlCaseTitle !== state.selectedYamlRegion) {
    state.selectedYamlCaseTitle.classList.remove('yaml-region-selected');
  }
  state.selectedYamlRegion = null;
  state.selectedYamlStepCard = null;
  state.selectedYamlCaseSummary = null;
  state.selectedYamlCaseTitle = null;
}

function selectYamlRegion(region) {
  if (state.selectedYamlRegion === region) return;
  clearSelectedYamlRegion();
  const stepCard = region.closest('.yaml-step-card');
  const caseTitle = region.closest('.yaml-case-title-row');
  const caseSummary = region.closest('.yaml-case-summary')
    || (caseTitle?.nextElementSibling?.classList.contains('yaml-case-summary') ? caseTitle.nextElementSibling : null);
  state.selectedYamlRegion = region;
  state.selectedYamlStepCard = stepCard;
  state.selectedYamlCaseSummary = caseSummary;
  state.selectedYamlCaseTitle = caseTitle || (caseSummary?.previousElementSibling?.classList.contains('yaml-case-title-row') ? caseSummary.previousElementSibling : null);
  region.classList.add('yaml-region-selected');
  if (stepCard && stepCard !== region) stepCard.classList.add('yaml-region-selected');
  if (caseSummary && caseSummary !== region) caseSummary.classList.add('yaml-region-selected');
  if (state.selectedYamlCaseTitle && state.selectedYamlCaseTitle !== region) state.selectedYamlCaseTitle.classList.add('yaml-region-selected');
}

function handleYamlRegionClick(event) {
  const region = event.target.closest(YAML_SELECTABLE_REGION_SELECTOR);
  if (region && (els.yamlInputViewer.contains(region) || els.yamlRecordedViewer.contains(region))) {
    if (state.currentRequestId || state.finishingRun) return;
    selectYamlRegion(region);
    if (els.yamlInputViewer.contains(region) || els.yamlRecordedViewer.contains(region)) {
      if (els.yamlInputViewer.contains(region) && currentRunMode() !== 'strict-yaml') return;
      if ((region.closest('.yaml-case-title-row') || region.closest('.yaml-case-summary')) && !region.closest('.yaml-step-card')) {
        showCompletedRunReplayPreview();
      } else {
        const stepCard = region.closest('.yaml-step-card');
        if (stepCard) loadStepArtifactsForCard(stepCard);
      }
    }
    return;
  }
  if (state.currentRequestId || state.finishingRun) return;
  clearSelectedYamlRegion();
}

function completedRunId() {
  return !state.currentRequestId && state.replayRequestId ? state.replayRequestId : '';
}

async function showCompletedRunReplayPreview(runId = completedRunId()) {
  if (!runId) return;
  clearStepArtifactPreview();
  showRightTab('preview');
  try {
    const replayVideo = await ensureReplayVideoGenerated(runId);
    if (replayVideo?.videoUrl) {
      await showReplayVideoPreview(replayVideo.videoUrl);
    } else {
      clearPreview('No replay video is available for this run.');
    }
  } catch (error) {
    clearPreview(`Replay video could not be loaded: ${error.message}`);
  }
}

function handleProgressRunIdClick() {
  if (state.currentRequestId || state.finishingRun) return;
  const runId = els.progressRunId.dataset.runId || '';
  if (!runId) return;
  clearSelectedProgressItem();
  selectProgressRunId();
  showCompletedRunReplayPreview(runId);
}

function selectProgressRunId() {
  state.selectedProgressRunId = true;
  els.progressRunId.classList.add('progress-run-id-selected');
}

function clearSelectedProgressRunId() {
  state.selectedProgressRunId = false;
  els.progressRunId.classList.remove('progress-run-id-selected');
}

async function loadStepArtifactsForCard(stepCard) {
  const runId = completedRunId();
  if (!runId) return;
  const stepIdentifier = stepCard.dataset.yamlStepId || stepCard.dataset.yamlStepIndex || '';
  if (!stepIdentifier) return;
  const previewKey = `${runId}:${stepIdentifier}`;
  state.stepArtifactPreviewActive = true;
  state.stepArtifactStepKey = previewKey;
  showRightTab('preview');
  const shouldShowLoading = els.stepArtifactPreview.hidden || !els.stepArtifactPreview.hasChildNodes();
  if (shouldShowLoading) renderStepArtifactLoading(stepCard);
  try {
    const payload = await api(`/step-artifacts/${encodeURIComponent(runId)}/${encodeURIComponent(stepIdentifier)}`);
    if (state.stepArtifactStepKey !== previewKey) return;
    await preloadStepArtifactScreenshots(payload);
    if (state.stepArtifactStepKey !== previewKey) return;
    renderStepArtifactPreview(payload, stepCard);
  } catch (error) {
    if (state.stepArtifactStepKey !== previewKey) return;
    renderStepArtifactError(stepCard, error.message);
  }
}

function clearStepArtifactPreview() {
  state.stepArtifactPreviewActive = false;
  state.stepArtifactStepKey = null;
  if (!els.stepArtifactPreview) return;
  els.stepArtifactPreview.hidden = true;
  els.stepArtifactPreview.innerHTML = '';
}

function showStepArtifactContainer() {
  cancelPendingReplayVideoReadyWait();
  if (els.replayVideo.src) {
    els.replayVideo.pause();
  }
  els.replayVideo.hidden = true;
  els.replayVideo.style.display = 'none';
  els.screenshot.removeAttribute('src');
  els.screenshot.style.display = 'none';
  els.previewEmpty.style.display = 'none';
  els.stepArtifactPreview.hidden = false;
}

function renderStepArtifactLoading(stepCard) {
  showStepArtifactContainer();
  const shell = stepArtifactShell(stepCard, 'Loading artifacts...');
  els.stepArtifactPreview.replaceChildren(shell);
}

function renderStepArtifactError(stepCard, message) {
  showStepArtifactContainer();
  const shell = stepArtifactShell(stepCard);
  const error = document.createElement('div');
  error.className = 'step-artifact-error';
  error.textContent = message || 'Unable to load step artifacts.';
  shell.appendChild(error);
  els.stepArtifactPreview.replaceChildren(shell);
}

function renderStepArtifactPreview(payload, stepCard) {
  showStepArtifactContainer();
  const artifacts = Array.isArray(payload?.artifacts) ? payload.artifacts : [];
  const shell = stepArtifactShell(stepCard, payload?.message || 'No artifacts for this step yet.');
  if (artifacts.length > 0) {
    shell.querySelector('.step-artifact-empty')?.remove();
    const screenshots = artifacts.filter((artifact) => artifact.kind === 'screenshot' && artifact.contentBase64);
    const textArtifacts = artifacts.filter((artifact) => artifact.kind !== 'screenshot' && typeof artifact.content === 'string');
    if (screenshots.length > 0) shell.appendChild(renderStepArtifactScreenshots(screenshots));
    if (textArtifacts.length > 0) shell.appendChild(renderStepArtifactTextArtifacts(textArtifacts));
  }
  els.stepArtifactPreview.replaceChildren(shell);
}

async function preloadStepArtifactScreenshots(payload) {
  const artifacts = Array.isArray(payload?.artifacts) ? payload.artifacts : [];
  const sources = artifacts
    .filter((artifact) => artifact.kind === 'screenshot' && artifact.contentBase64)
    .map((artifact) => stepArtifactImageSrc(artifact));
  await Promise.allSettled(sources.map((src) => loadImageElement(src)));
}

function stepArtifactShell(stepCard, emptyMessage = '') {
  const shell = document.createElement('div');
  shell.className = 'step-artifact-shell';
  const title = document.createElement('div');
  title.className = 'step-artifact-title';
  title.textContent = stepArtifactTitle(stepCard);
  shell.appendChild(title);
  if (emptyMessage) {
    const empty = document.createElement('div');
    empty.className = 'step-artifact-empty';
    empty.textContent = emptyMessage;
    shell.appendChild(empty);
  }
  return shell;
}

function stepArtifactTitle(stepCard) {
  const index = stepCard.dataset.yamlStepIndex || '?';
  const action = stepCard.dataset.yamlAction || 'command';
  return `${String(index).padStart(2, '0')} ${action}`;
}

function renderStepArtifactScreenshots(screenshots) {
  const section = document.createElement('section');
  section.className = 'step-artifact-section';
  const heading = document.createElement('div');
  heading.className = 'step-artifact-section-title';
  heading.textContent = 'Screenshots';
  section.appendChild(heading);
  const primary = primaryScreenshotArtifacts(screenshots);
  const row = document.createElement('div');
  row.className = `step-artifact-screenshot-row${primary.length === 2 ? ' step-artifact-compare' : ''}`;
  row.appendChild(renderStepArtifactImage(primary[0]));
  if (primary.length === 2) {
    const connector = document.createElement('div');
    connector.className = 'step-artifact-connector';
    connector.setAttribute('aria-hidden', 'true');
    row.appendChild(connector);
    row.appendChild(renderStepArtifactImage(primary[1]));
  }
  section.appendChild(row);
  return section;
}

function primaryScreenshotArtifacts(screenshots) {
  const before = screenshots.find((artifact) => stepArtifactLabel(artifact).toLowerCase().includes('before'));
  const after = screenshots.find((artifact) => stepArtifactLabel(artifact).toLowerCase().includes('after'));
  if (before && after && before !== after) return [before, after];
  if (screenshots.length > 1) return [screenshots[0], screenshots[screenshots.length - 1]];
  return [screenshots[0]];
}

function renderStepArtifactImage(artifact) {
  const card = document.createElement('figure');
  card.className = 'step-artifact-image-card';
  const label = document.createElement('figcaption');
  label.className = 'step-artifact-image-label';
  label.textContent = stepArtifactLabel(artifact);
  const image = document.createElement('img');
  image.alt = label.textContent;
  image.src = stepArtifactImageSrc(artifact);
  card.appendChild(label);
  card.appendChild(image);
  return card;
}

function stepArtifactImageSrc(artifact) {
  return `data:${artifact.mimeType || 'image/png'};base64,${artifact.contentBase64}`;
}

function renderStepArtifactTextArtifacts(artifacts) {
  const section = document.createElement('section');
  section.className = 'step-artifact-section';
  const heading = document.createElement('div');
  heading.className = 'step-artifact-section-title';
  heading.textContent = 'Structured artifacts';
  section.appendChild(heading);
  for (const artifact of artifacts) {
    const card = document.createElement('div');
    card.className = 'step-artifact-text-card';
    const label = document.createElement('div');
    label.className = 'step-artifact-text-label';
    label.textContent = `${artifact.kind || 'artifact'} · ${stepArtifactLabel(artifact)}`;
    const pre = document.createElement('pre');
    pre.className = isXmlStepArtifact(artifact) ? 'step-artifact-xml' : '';
    pre.textContent = artifact.content || '';
    card.appendChild(label);
    card.appendChild(pre);
    section.appendChild(card);
  }
  return section;
}

function isXmlStepArtifact(artifact) {
  const content = String(artifact.content || '').trimStart();
  const mimeType = String(artifact.mimeType || '').toLowerCase();
  const path = String(artifact.path || '').toLowerCase();
  return mimeType.includes('xml') || path.endsWith('.xml') || content.startsWith('<');
}

function stepArtifactLabel(artifact) {
  const combined = `${artifact.reason || ''} ${artifact.phase || ''}`.toLowerCase();
  if (combined.includes('before') || combined.includes('prepare')) return 'Before';
  if (combined.includes('after') || combined.includes('finalize')) return 'After';
  if (combined.includes('failure')) return 'Failure';
  return artifact.phase || artifact.reason || artifact.kind || 'Artifact';
}

function recordingStatusDetails(recording) {
  const messages = [];
  for (const warning of recording.warnings || []) messages.push(`Warning: ${formatProgressValue(warning)}`);
  for (const error of recording.errors || []) messages.push(`Error: ${formatProgressValue(error)}`);
  if ((recording.skippedToolCalls || []).length > 0) messages.push(`Skipped tool calls: ${recording.skippedToolCalls.length}`);
  return messages.join('\n') || 'No recorded YAML content.';
}

function renderMarkdown(markdown) {
  const lines = String(markdown || '').replace(/\r\n/g, '\n').split('\n');
  const html = [];
  let inCode = false;
  let codeLines = [];
  let inList = false;

  const closeList = () => {
    if (inList) {
      html.push('</ul>');
      inList = false;
    }
  };
  const flushCode = () => {
    html.push(`<pre><code>${escapeHtml(codeLines.join('\n'))}</code></pre>`);
    codeLines = [];
  };

  for (const line of lines) {
    if (line.trim().startsWith('```')) {
      if (inCode) {
        inCode = false;
        flushCode();
      } else {
        closeList();
        inCode = true;
        codeLines = [];
      }
      continue;
    }
    if (inCode) {
      codeLines.push(line);
      continue;
    }

    const heading = line.match(/^(#{1,4})\s+(.*)$/);
    if (heading) {
      closeList();
      const level = heading[1].length;
      html.push(`<h${level}>${formatInlineMarkdown(heading[2])}</h${level}>`);
      continue;
    }

    const bullet = line.match(/^\s*[-*]\s+(.*)$/);
    if (bullet) {
      if (!inList) {
        html.push('<ul>');
        inList = true;
      }
      html.push(`<li>${formatInlineMarkdown(bullet[1])}</li>`);
      continue;
    }

    if (!line.trim()) {
      closeList();
      continue;
    }

    closeList();
    html.push(`<p>${formatInlineMarkdown(line)}</p>`);
  }
  if (inCode) flushCode();
  closeList();
  return html.join('\n');
}

function formatInlineMarkdown(value) {
  return escapeHtml(value)
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function showRightTab(tabName) {
  const tabs = [
    { name: 'preview', button: els.previewTab, pane: els.previewPane },
    { name: 'report', button: els.reportTab, pane: els.reportPane },
  ];
  const selected = tabs.some((tab) => tab.name === tabName) ? tabName : 'preview';
  for (const tab of tabs) {
    const active = tab.name === selected;
    tab.pane.hidden = !active;
    tab.button.classList.toggle('active', active);
    tab.button.setAttribute('aria-selected', String(active));
  }
}

function appendProgress(content, backendSequence = null, details = [], status = 'neutral') {
  const hasBackendSequence = Number.isInteger(backendSequence) && backendSequence >= 0;
  if (hasBackendSequence) {
    state.progressSequence = Math.max(state.progressSequence, backendSequence);
  } else {
    state.progressSequence += 1;
  }
  const item = document.createElement('div');
  item.className = 'progress-item';
  item.tabIndex = 0;
  const sequence = String(hasBackendSequence ? backendSequence : state.progressSequence).padStart(3, '0');
  const number = document.createElement('span');
  number.className = 'progress-number';
  number.textContent = `${sequence}.`;
  const statusDot = document.createElement('span');
  statusDot.className = `progress-status-dot progress-status-${status}`;
  statusDot.title = status;
  const body = document.createElement('span');
  body.className = 'progress-text';
  renderProgressText(body, content);
  item.appendChild(number);
  item.appendChild(statusDot);
  item.appendChild(body);
  const eventKey = hasBackendSequence ? String(backendSequence) : `local-${state.progressSequence}`;
  for (const detail of details) {
    item.appendChild(renderProgressDetail(eventKey, detail.label, detail.value));
  }
  els.progress.appendChild(item);
  activateProgressItem(item);
  scheduleProgressScroll();
}

function activateProgressItem(item) {
  cancelActiveProgressItemClearTimer();
  if (state.activeProgressItem === item) return;
  clearActiveProgressItem();
  state.activeProgressItem = item;
  item.classList.add('progress-item-active');
}

function clearActiveProgressItem() {
  if (!state.activeProgressItem) return;
  cancelActiveProgressItemClearTimer();
  state.activeProgressItem.classList.remove('progress-item-active');
  state.activeProgressItem = null;
}

function scheduleClearActiveProgressItem(delayMs = 900) {
  cancelActiveProgressItemClearTimer();
  state.activeProgressItemClearTimer = window.setTimeout(() => {
    state.activeProgressItemClearTimer = null;
    if (!state.activeProgressItem) return;
    state.activeProgressItem.classList.remove('progress-item-active');
    state.activeProgressItem = null;
  }, delayMs);
}

function cancelActiveProgressItemClearTimer() {
  if (!state.activeProgressItemClearTimer) return;
  clearTimeout(state.activeProgressItemClearTimer);
  state.activeProgressItemClearTimer = null;
}

function clearSelectedProgressItem() {
  if (!state.selectedProgressItem) return;
  state.selectedProgressItem.classList.remove('progress-item-selected');
  state.selectedProgressItem = null;
}

function selectProgressItem(item) {
  if (state.selectedProgressItem === item) return;
  clearSelectedProgressItem();
  state.selectedProgressItem = item;
  item.classList.add('progress-item-selected');
}

function handleProgressItemClick(event) {
  if (event.target.closest('#progress-run-id')) return;
  const item = event.target.closest('.progress-item');
  if (item && els.progress.contains(item)) {
    if (state.currentRequestId || state.finishingRun) return;
    clearSelectedProgressRunId();
    selectProgressItem(item);
    return;
  }
  clearSelectedProgressRunId();
  clearSelectedProgressItem();
}

function scheduleProgressScroll() {
  if (state.progressScrollScheduled) return;
  state.progressScrollScheduled = true;
  window.requestAnimationFrame(() => {
    state.progressScrollScheduled = false;
    els.progress.scrollTop = els.progress.scrollHeight;
  });
}

function captureProgressDetailState() {
  for (const detail of els.progress.querySelectorAll('.progress-detail[data-detail-key]')) {
    state.progressDetailOpenState.set(detail.dataset.detailKey, detail.open);
  }
}

function renderProgressText(root, content) {
  const normalized = typeof content === 'string' ? { title: content, message: '', toolName: '' } : content;
  const titleRow = document.createElement('div');
  titleRow.className = 'progress-title-row';

  const title = document.createElement('span');
  title.className = 'progress-title';
  title.textContent = normalized.title || 'Event';
  titleRow.appendChild(title);

  if (normalized.toolName) {
    const tool = document.createElement('span');
    tool.className = 'progress-tool';
    tool.textContent = normalized.toolName;
    titleRow.appendChild(tool);
  }

  root.appendChild(titleRow);

  if (normalized.message) {
    const message = document.createElement('div');
    message.className = 'progress-message';
    message.textContent = normalized.message;
    root.appendChild(message);
  }
}

function eventStatus(event) {
  if (event.type === 'tool_call_failed' || event.type === 'run_failed') return 'failed';
  if (event.type === 'run_completed') return statusFromValue(event.payload?.status);
  const payloadStatus = statusFromValue(event.payload?.status);
  if (payloadStatus !== 'neutral') return payloadStatus;
  if (hasDisplayValue(event.payload?.error_message) || hasDisplayValue(event.payload?.failure_category)) {
    return 'failed';
  }
  const output = parseMaybeJson(event.tool_output_preview);
  const outputStatus = statusFromValue(output?.status ?? output?.result?.status);
  if (outputStatus !== 'neutral') return outputStatus;
  if (event.type === 'tool_call_completed') return 'success';
  return 'neutral';
}

function statusFromValue(value) {
  if (typeof value !== 'string') return 'neutral';
  const normalized = value.toLowerCase();
  if (['success', 'passed', 'pass', 'completed', 'recorded'].includes(normalized)) return 'success';
  if (['failed', 'failure', 'error', 'cancelled', 'skipped'].includes(normalized)) return 'failed';
  return 'neutral';
}

function parseMaybeJson(value) {
  if (typeof value !== 'string') return value;
  const trimmed = value.trim();
  if (!trimmed) return null;
  try {
    return JSON.parse(trimmed);
  } catch {
    return null;
  }
}

function eventLabel(event) {
  return {
    title: event.title || event.type || 'Event',
    message: event.message || '',
    toolName: event.tool_name || '',
  };
}

function eventDetails(event) {
  const details = [];
  if (hasDisplayValue(event.tool_arguments)) {
    details.push({ label: 'Input', value: event.tool_arguments });
  }
  if (hasDisplayValue(event.tool_output_preview)) {
    details.push({ label: 'Output', value: event.tool_output_preview });
  }
  if (hasMeaningfulPayload(event.payload)) {
    details.push({ label: 'Payload', value: event.payload });
  }
  return details;
}

function renderProgressDetail(eventKey, label, value) {
  const detailKey = `${eventKey}:${label}`;
  const detail = document.createElement('details');
  detail.className = 'progress-detail';
  detail.dataset.detailKey = detailKey;
  detail.open = state.progressDetailOpenState.get(detailKey) === true;
  detail.addEventListener('toggle', () => {
    state.progressDetailOpenState.set(detailKey, detail.open);
  });
  const summary = document.createElement('summary');
  summary.textContent = label;
  const pre = document.createElement('pre');
  pre.textContent = formatProgressValue(value);
  detail.appendChild(summary);
  detail.appendChild(pre);
  return detail;
}

function formatProgressValue(value) {
  if (typeof value === 'string') {
    const trimmed = value.trim();
    if (!trimmed) return '';
    try {
      return JSON.stringify(JSON.parse(trimmed), null, 2);
    } catch {
      return trimmed;
    }
  }
  if (value === null || value === undefined) return '';
  if (typeof value === 'object') return JSON.stringify(value, null, 2);
  return String(value);
}

function hasDisplayValue(value) {
  if (value === null || value === undefined) return false;
  if (typeof value === 'string') return value.trim().length > 0;
  return true;
}

function hasMeaningfulPayload(payload) {
  if (!payload || typeof payload !== 'object') return false;
  return Object.entries(payload).some(([, value]) => hasDisplayValue(value));
}

async function ensureReplayVideoGenerated(requestId, frames = null) {
  if (!requestId) return { error: 'missing replay request id' };
  if (state.replayVideoInFlight) return { error: 'replay video generation is already running' };
  const totalStartedAt = performance.now();
  state.replayVideoInFlight = true;
  try {
    const existing = await loadReplayVideo(requestId);
    if (existing.available && existing.videoUrl) return { videoUrl: existing.videoUrl, blob: null };
    const replayFrames = frames || (await loadReplayFrames(requestId)).frames;
    if (replayFrames.length === 0) return { error: 'no replay frames found' };
    const generated = await generateReplayVideo(replayFrames);
    if (!generated || !generated.blob || generated.blob.size === 0) return { error: 'MediaRecorder produced an empty video' };
    const { blob: videoBlob, durationMs } = generated;
    const seekable = await makeReplaySeekable(videoBlob, durationMs);
    const uploadBlob = seekable.blob;
    if (!seekable.ok) {
      appendProgress(
        {
          title: 'Replay video is not seekable',
          message: `Failed to rewrite WebM index: ${seekable.error}. Uploading the original recording; playback may not support seeking.`,
        },
        null,
        [],
        'failed',
      );
    }
    const uploaded = await uploadReplayVideo(requestId, uploadBlob);
    replayVideoDurationLog('total', totalStartedAt, { frameCount: replayFrames.length, size: uploadBlob.size });
    return { videoUrl: uploaded.videoUrl, blob: uploadBlob };
  } catch (error) {
    console.warn('Unable to generate replay video', error);
    return { error: error.message || String(error) };
  } finally {
    state.replayVideoInFlight = false;
  }
}

function replayVideoDurationLog(stage, startedAt, metadata = {}) {
  console.info('[replay-video] duration', {
    stage,
    elapsedMs: Math.round(performance.now() - startedAt),
    ...metadata,
  });
}

function appendReplayVideoGeneratingProgress() {
  appendProgress(
    {
      title: 'Generating replay video...',
      message: 'Encoding replay frames and saving the video.',
    },
    null,
    [],
  );
}

function appendReplayFramesProgress(frames) {
  appendProgress(
    {
      title: 'Replay frames loaded',
      message: `${frames.length} screenshot${frames.length === 1 ? '' : 's'} will be used for the replay video.`,
    },
    null,
    [{ label: 'Screenshots', value: replayFrameSummaries(frames) }],
    frames.length > 0 ? 'success' : 'failed',
  );
}

function replayFrameSummaries(frames) {
  return frames.map((frame) => ({
    index: frame.index ?? null,
    timestamp: frame.timestamp ?? null,
    path: frame.path || '',
  }));
}

async function loadReplayVideo(requestId) {
  return api(`/replay-video/${encodeURIComponent(requestId)}`);
}

async function uploadReplayVideo(requestId, videoBlob) {
  const videoBase64 = await blobToBase64(videoBlob);
  return api(`/replay-video/${encodeURIComponent(requestId)}`, {
    method: 'POST',
    body: JSON.stringify({ mimeType: 'video/webm', videoBase64 }),
  });
}

async function loadReplayFrames(requestId) {
  const replay = await api(`/replay/${encodeURIComponent(requestId)}`);
  const frames = (replay.frames || [])
    .filter((frame) => typeof frame.screenshot === 'string')
    .map((frame, index) => ({
      index: Number.isFinite(Number(frame.index)) ? Number(frame.index) : index + 1,
      timestamp: Number.isFinite(Number(frame.timestamp)) ? Number(frame.timestamp) : null,
      path: typeof frame.path === 'string' ? frame.path : '',
      src: `data:image/png;base64,${frame.screenshot}`,
    }));
  return { frames };
}

async function refreshPreviewFromReplay(requestId) {
  if (!requestId) return;
  try {
    const replay = await loadReplayFrames(requestId);
    const frame = replay.frames[replay.frames.length - 1];
    if (frame) showReplayFrame(frame);
  } catch {
    // The screenshot artifact may have been announced before the replay endpoint can read it.
  }
}

function replayFrameDelay(current, next) {
  if (typeof current.timestamp === 'number' && typeof next.timestamp === 'number') {
    const rawDelay = Math.max(0, next.timestamp - current.timestamp);
    if (rawDelay === 0) return REPLAY_FAST_SAME_EVENT_DELAY_MS;
    return Math.min(
      REPLAY_FAST_MAX_DELAY_MS,
      Math.max(REPLAY_FAST_ACTION_DELAY_MS, rawDelay / REPLAY_FAST_TIME_SCALE),
    );
  }
  return REPLAY_FAST_FALLBACK_DELAY_MS;
}

async function generateReplayVideo(frames) {
  if (!window.MediaRecorder || frames.length === 0) return null;
  const mimeType = replayVideoMimeType();
  if (!mimeType) return null;
  const canvas = document.createElement('canvas');
  const context = canvas.getContext('2d');
  if (!context || !canvas.captureStream) return null;
  const firstImage = await loadImageElement(frames[0].src);
  canvas.width = firstImage.naturalWidth || firstImage.width;
  canvas.height = firstImage.naturalHeight || firstImage.height;
  context.drawImage(firstImage, 0, 0, canvas.width, canvas.height);
  console.info('[replay-video] draw screenshot', replayFrameDrawLogEntry(frames[0], 1, replayFrameDisplayDuration(frames, 0)));
  const chunks = [];
  const stream = canvas.captureStream(30);
  const videoTrack = stream.getVideoTracks()[0];
  const requestCanvasFrame = () => {
    if (videoTrack && typeof videoTrack.requestFrame === 'function') {
      videoTrack.requestFrame();
    }
  };
  const recorder = new MediaRecorder(stream, { mimeType });
  recorder.ondataavailable = (event) => {
    if (event.data.size > 0) chunks.push(event.data);
  };
  recorder.start();
  const recordingStartedAt = performance.now();
  const renderStartedAt = recordingStartedAt;
  requestCanvasFrame();
  for (let index = 1; index < frames.length; index += 1) {
    await waitMs(replayFrameDelay(frames[index - 1], frames[index]));
    const image = await loadImageElement(frames[index].src);
    context.drawImage(image, 0, 0, canvas.width, canvas.height);
    console.info('[replay-video] draw screenshot', replayFrameDrawLogEntry(frames[index], index + 1, replayFrameDisplayDuration(frames, index)));
    requestCanvasFrame();
  }
  await waitMs(REPLAY_FAST_FINAL_FRAME_HOLD_MS);
  requestCanvasFrame();
  const recordingEndedAt = await new Promise((resolve) => {
    recorder.onstop = () => {
      const endedAt = performance.now();
      replayVideoDurationLog('render and record timeline', renderStartedAt, { chunkCount: chunks.length, frameCount: frames.length });
      resolve(endedAt);
    };
    recorder.stop();
  });
  stream.getTracks().forEach((track) => track.stop());
  const blob = new Blob(chunks, { type: recorder.mimeType || 'video/webm' });
  return { blob, durationMs: Math.max(0, recordingEndedAt - recordingStartedAt) };
}

function replayFrameDisplayDuration(frames, index) {
  const nextFrame = frames[index + 1] || null;
  return nextFrame ? replayFrameDelay(frames[index], nextFrame) : REPLAY_FAST_FINAL_FRAME_HOLD_MS;
}

function replayFrameDrawLogEntry(frame, fallbackIndex, durationMs) {
  return {
    index: frame?.index ?? fallbackIndex,
    path: frame?.path || '',
    durationMs,
  };
}

function replayVideoMimeType() {
  const candidates = ['video/webm;codecs=vp9', 'video/webm;codecs=vp8', 'video/webm'];
  return candidates.find((mimeType) => MediaRecorder.isTypeSupported(mimeType)) || '';
}

async function showReplayVideoPreview(videoUrl) {
  clearStepArtifactPreview();
  cancelPendingReplayVideoReadyWait();
  if (els.replayVideo.src !== videoUrl) {
    els.replayVideo.src = videoUrl;
  }
  els.replayVideo.pause();
  try {
    els.replayVideo.currentTime = 0;
  } catch {
    // Some browsers reject seeking before metadata is available.
  }
  await waitForReplayVideoReady();
  try {
    els.replayVideo.currentTime = 0;
  } catch {
    // Some browsers reject seeking before metadata is available.
  }
  els.screenshot.style.display = 'none';
  els.previewEmpty.style.display = 'none';
  els.replayVideo.hidden = false;
  els.replayVideo.style.display = 'block';
}

function waitForReplayVideoReady() {
  if (els.replayVideo.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA) return Promise.resolve();
  return new Promise((resolve) => {
    const complete = () => {
      cleanup();
      resolve();
    };
    const cleanup = () => {
      els.replayVideo.removeEventListener('loadeddata', complete);
      els.replayVideo.removeEventListener('canplay', complete);
      els.replayVideo.removeEventListener('error', complete);
      state.pendingReplayVideoCleanup = null;
    };
    state.pendingReplayVideoCleanup = cleanup;
    els.replayVideo.addEventListener('loadeddata', complete, { once: true });
    els.replayVideo.addEventListener('canplay', complete, { once: true });
    els.replayVideo.addEventListener('error', complete, { once: true });
    els.replayVideo.load();
  });
}

function cancelPendingReplayVideoReadyWait() {
  if (!state.pendingReplayVideoCleanup) return;
  state.pendingReplayVideoCleanup();
}

async function makeReplaySeekable(blob, durationMsOverride = null) {
  const tsebml = window.EBML || window.tsebml || window.ts_ebml || window.tsEBML;
  if (!tsebml || !tsebml.Decoder || !tsebml.Reader || !tsebml.tools) {
    return { ok: false, blob, error: 'ts-ebml is not loaded' };
  }
  try {
    const buffer = await blob.arrayBuffer();
    const decoder = new tsebml.Decoder();
    const reader = new tsebml.Reader();
    reader.logging = false;
    reader.drop_default_duration = false;
    const elements = decoder.decode(buffer);
    for (const element of elements) reader.read(element);
    reader.stop();
    const readerDuration = Number.isFinite(reader.duration) && reader.duration > 0 ? reader.duration : 0;
    const overrideDuration = Number.isFinite(durationMsOverride) && durationMsOverride > 0 ? durationMsOverride : 0;
    const duration = readerDuration || overrideDuration;
    if (duration <= 0) {
      return { ok: false, blob, error: 'unable to determine replay duration' };
    }
    const readerCues = Array.isArray(reader.cues) ? reader.cues : [];
    const trackNumber = reader.trackInfo?.trackNumber || 1;
    const cues = readerCues.length > 0 ? readerCues : buildCuesFromClusters(elements, trackNumber);
    if (cues.length === 0) {
      return { ok: false, blob, error: 'no cluster timestamps were found in the recording' };
    }
    const metadatas = Array.isArray(reader.metadatas) && reader.metadatas.length > 0 ? reader.metadatas : elements;
    const refined = tsebml.tools.makeMetadataSeekable(metadatas, duration, cues);
    const body = buffer.slice(reader.metadataSize);
    return { ok: true, blob: new Blob([refined, body], { type: blob.type || 'video/webm' }) };
  } catch (error) {
    return { ok: false, blob, error: error?.message || String(error) };
  }
}

function buildCuesFromClusters(elements, trackNumber) {
  const cues = [];
  for (let index = 0; index < elements.length; index += 1) {
    const element = elements[index];
    if (element?.type !== 'm' || element.name !== 'Cluster' || element.isEnd) continue;
    const clusterPosition = element.tagStart;
    if (!Number.isFinite(clusterPosition)) continue;
    let cueTime = null;
    for (let lookahead = index + 1; lookahead < elements.length; lookahead += 1) {
      const child = elements[lookahead];
      if (child?.type === 'm' && child.name === 'Cluster') break;
      if ((child?.name === 'Timestamp' || child?.name === 'Timecode') && Number.isFinite(child.value)) {
        cueTime = child.value;
        break;
      }
    }
    if (cueTime === null) continue;
    cues.push({
      CueTrack: trackNumber,
      CueClusterPosition: clusterPosition,
      CueTime: cueTime,
    });
  }
  return cues;
}

function showReplayFrame(frame) {
  clearStepArtifactPreview();
  cancelPendingReplayVideoReadyWait();
  els.replayVideo.hidden = true;
  els.replayVideo.style.display = 'none';
  els.screenshot.src = frame.src;
  els.screenshot.style.display = 'block';
  els.previewEmpty.style.display = 'none';
}

function preloadImage(src) {
  return loadImageElement(src).then(() => undefined);
}

function loadImageElement(src) {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = reject;
    image.src = src;
  });
}

function waitMs(durationMs) {
  return new Promise((resolve) => window.setTimeout(resolve, durationMs));
}

function blobToBase64(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(',', 2)[1] || '');
    reader.onerror = reject;
    reader.readAsDataURL(blob);
  });
}

function clearPreview(message = '') {
  clearStepArtifactPreview();
  cancelPendingReplayVideoReadyWait();
  els.previewEmpty.textContent = message;
  els.previewEmpty.style.display = 'block';
  if (els.replayVideo.src) {
    els.replayVideo.pause();
    els.replayVideo.removeAttribute('src');
    els.replayVideo.load();
  }
  els.replayVideo.hidden = true;
  els.replayVideo.style.display = 'none';
  els.screenshot.removeAttribute('src');
  els.screenshot.style.display = 'none';
}

function initPanelResizer() {
  if (!els.shell || !els.controlPanel || !els.panelResizer) return;
  restoreControlPanelWidth();

  els.panelResizer.addEventListener('pointerdown', (event) => {
    if (event.button !== 0) return;
    event.preventDefault();
    els.panelResizer.setPointerCapture?.(event.pointerId);
    els.shell.classList.add('resizing-panels');

    const onPointerMove = (moveEvent) => {
      applyControlPanelWidth(widthFromPointer(moveEvent.clientX));
    };
    const onPointerUp = () => {
      els.shell.classList.remove('resizing-panels');
      window.removeEventListener('pointermove', onPointerMove);
      window.removeEventListener('pointerup', onPointerUp);
      persistControlPanelWidth();
    };

    window.addEventListener('pointermove', onPointerMove);
    window.addEventListener('pointerup', onPointerUp, { once: true });
  });

  els.panelResizer.addEventListener('keydown', (event) => {
    if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return;
    event.preventDefault();
    const delta = (event.shiftKey ? 40 : 16) * (event.key === 'ArrowLeft' ? -1 : 1);
    applyControlPanelWidth(currentControlPanelWidth() + delta);
    persistControlPanelWidth();
  });
}

function widthFromPointer(clientX) {
  const shellRect = els.shell.getBoundingClientRect();
  const shellStyle = window.getComputedStyle(els.shell);
  const paddingLeft = Number.parseFloat(shellStyle.paddingLeft) || 0;
  return clientX - shellRect.left - paddingLeft;
}

function currentControlPanelWidth() {
  return els.controlPanel.getBoundingClientRect().width;
}

function applyControlPanelWidth(width) {
  const clamped = clampControlPanelWidth(width);
  els.shell.style.setProperty('--control-panel-width', `${Math.round(clamped)}px`);
  els.panelResizer.setAttribute('aria-valuenow', String(Math.round(clamped)));
}

function clampControlPanelWidth(width) {
  const shellStyle = window.getComputedStyle(els.shell);
  const paddingLeft = Number.parseFloat(shellStyle.paddingLeft) || 0;
  const paddingRight = Number.parseFloat(shellStyle.paddingRight) || 0;
  const available = els.shell.clientWidth - paddingLeft - paddingRight;
  const maxWidth = Math.max(
    CONTROL_PANEL_MIN_WIDTH,
    Math.min(CONTROL_PANEL_MAX_WIDTH, available - PREVIEW_PANEL_MIN_WIDTH),
  );
  return Math.min(Math.max(width, CONTROL_PANEL_MIN_WIDTH), maxWidth);
}

function restoreControlPanelWidth() {
  try {
    const saved = Number(window.localStorage.getItem(CONTROL_PANEL_WIDTH_STORAGE_KEY));
    if (Number.isFinite(saved) && saved > 0) applyControlPanelWidth(saved);
  } catch {
    // localStorage is optional for the resizer.
  }
}

function persistControlPanelWidth() {
  try {
    window.localStorage.setItem(CONTROL_PANEL_WIDTH_STORAGE_KEY, String(Math.round(currentControlPanelWidth())));
  } catch {
    // localStorage is optional for the resizer.
  }
}

els.refresh.addEventListener('click', clearPage);
els.runSelected.addEventListener('click', runSelected);
els.progressRunId.addEventListener('click', handleProgressRunIdClick);
els.yamlInputTab.addEventListener('click', () => showYamlView('input'));
els.yamlRecordedTab.addEventListener('click', () => showYamlView('recorded'));
els.yamlProgressTab.addEventListener('click', () => showYamlView('progress'));
document.addEventListener('click', handleYamlRegionClick);
document.addEventListener('click', handleProgressItemClick);
els.caseYaml.addEventListener('keydown', (event) => {
  if (event.key !== 'Enter') return;
  event.preventDefault();
  loadInputYaml();
});
els.caseYaml.addEventListener('blur', () => {
  const path = els.caseYaml.value.trim();
  if (path && path !== state.yamlInputLastPreviewPath) loadInputYaml();
});
for (const input of els.runModeInputs) {
  input.addEventListener('change', () => {
    switchRunMode();
    if ((currentRunMode() === 'yaml' || currentRunMode() === 'strict-yaml') && !state.currentRequestId) {
      els.caseYaml.focus();
    }
  });
}
els.previewTab.addEventListener('click', () => showRightTab('preview'));
els.reportTab.addEventListener('click', () => showRightTab('report'));
clearYamlInput();
clearRecordedYaml();
initPanelResizer();
updateRunMode();
showRightTab('preview');
refreshAll();

