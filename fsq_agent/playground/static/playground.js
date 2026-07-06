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
  yamlActiveView: 'input',
  yamlInputContent: '',
  yamlRecordedContent: '',
  yamlInputDisplay: null,
  yamlRecordedDisplay: null,
  yamlInputLastPreviewPath: '',
  currentExecutionMode: null,
  platformId: null,
  platformLabel: null,
};

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
  yamlCopy: document.getElementById('yaml-copy'),
  yamlInputTab: document.getElementById('yaml-input-tab'),
  yamlRecordedTab: document.getElementById('yaml-recorded-tab'),
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
  progressTab: document.getElementById('progress-tab'),
  reportTab: document.getElementById('report-tab'),
  previewPane: document.getElementById('preview-pane'),
  progressPane: document.getElementById('progress-pane'),
  reportPane: document.getElementById('report-pane'),
  reportContent: document.getElementById('report-content'),
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
  stopProgressUpdates();
  state.replayRequestId = null;
  state.previewToken = null;
  state.currentRequestId = null;
  state.progressSequence = 0;
  state.lastProgressSequence = 0;
  state.progressDetailOpenState.clear();
  state.currentExecutionMode = null;

  els.goal.value = '';
  els.caseYaml.value = '';
  clearYamlInput();
  clearRecordedYaml();
  clearRunId();
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
    if (state.currentRequestId) {
      setRunButtonCancel();
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

function updateRunMode() {
  const mode = currentRunMode();
  const hasInputYaml = mode === 'yaml' || mode === 'strict-yaml';
  els.goal.hidden = hasInputYaml;
  els.yamlPathRow.hidden = !hasInputYaml;
  els.caseYaml.disabled = !hasInputYaml || Boolean(state.currentRequestId);
  els.yamlSection.hidden = false;
  els.yamlTabs.hidden = false;
  if (mode === 'goal') {
    const hasRecordedYaml = Boolean(state.yamlRecordedContent || state.yamlRecordedDisplay);
    els.yamlCopy.hidden = !hasRecordedYaml;
    els.yamlInputTab.hidden = true;
    els.yamlRecordedTab.hidden = false;
    showYamlView('recorded');
  } else if (mode === 'strict-yaml') {
    els.yamlCopy.hidden = false;
    els.yamlInputTab.hidden = false;
    els.yamlRecordedTab.hidden = true;
    showYamlView('input');
  } else {
    els.yamlCopy.hidden = false;
    els.yamlInputTab.hidden = false;
    els.yamlRecordedTab.hidden = false;
    showYamlView('input');
  }
  if (!state.currentRequestId) setRunButtonIdle();
}

async function startExecution(payload) {
  if (!(await ensureSession())) return;
  state.currentExecutionMode = payload.strictCaseYamlPath ? 'strict-yaml' : (payload.caseYamlPath ? 'yaml' : 'goal');
  state.progressSequence = 0;
  state.lastProgressSequence = 0;
  state.progressDetailOpenState.clear();
  state.replayRequestId = null;
  clearRecordedYaml();
  clearRunId();
  els.progress.innerHTML = '';
  els.reportContent.textContent = 'No report yet.';
  clearPreview('Loading live preview...');
  showRightTab('progress');
  try {
    const result = await api('/execute', { method: 'POST', body: JSON.stringify(payload) });
    state.currentRequestId = result.requestId;
    state.replayRequestId = result.requestId;
    setRunButtonCancel();
    updateRunMode();
    startProgressPolling();
    await refreshStatus();
  } catch (error) {
    state.currentExecutionMode = null;
    updateRunMode();
    appendProgress(`Error: ${error.message}`);
  }
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
  els.runSelected.classList.add('cancel');
  els.runSelected.disabled = disabled;
}

function setRunButtonIdle({ disabled = false } = {}) {
  els.runSelected.textContent = 'Run';
  els.runSelected.classList.add('primary');
  els.runSelected.classList.remove('cancel');
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
    appendProgress(eventLabel(event), event.sequence, eventDetails(event), eventStatus(event));
    updateLastProgressSequence(event.sequence);
  }
  if (progress.preview?.token && progress.preview.token !== state.previewToken) {
    await refreshPreview(progress.requestId, progress.preview.token);
  }
  if (progress.status !== 'running') {
    stopProgressUpdates();
    state.currentRequestId = null;
    setRunButtonIdle({ disabled: true });
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
    setRunButtonIdle();
    state.currentExecutionMode = null;
    updateRunMode();
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
  els.progressRunId.hidden = false;
}

function clearRunId() {
  els.progressRunId.textContent = '';
  els.progressRunId.hidden = true;
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
  updateYamlCopyButton();
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
    setYamlRecordedStatus(recordingStatusSummary(yaml), statusFromValue(yaml.status));
    els.yamlSection.hidden = false;
    showYamlView('recorded');
  } catch (error) {
    state.yamlRecordedContent = '';
    state.yamlRecordedDisplay = null;
    renderYamlEmpty(els.yamlRecordedViewer, error.message);
    setYamlRecordedStatus(error.message, 'error');
    els.yamlSection.hidden = false;
    showYamlView('recorded');
  }
  updateYamlCopyButton();
}

function clearYamlInput(message = 'No YAML loaded.') {
  state.yamlInputContent = '';
  state.yamlInputDisplay = null;
  state.yamlInputLastPreviewPath = '';
  setYamlInputStatus(message === 'No YAML loaded.' ? '' : message, 'neutral');
  renderYamlEmpty(els.yamlInputViewer, message);
  updateYamlCopyButton();
}

function clearRecordedYaml() {
  state.yamlRecordedContent = '';
  state.yamlRecordedDisplay = null;
  setYamlRecordedStatus('', 'neutral');
  renderYamlEmpty(els.yamlRecordedViewer, 'No recorded YAML yet.');
  updateYamlCopyButton();
}

function setRecordedYamlNoContent(message, status = 'neutral') {
  state.yamlRecordedContent = '';
  state.yamlRecordedDisplay = null;
  setYamlRecordedStatus(message, status);
  renderYamlEmpty(els.yamlRecordedViewer, message);
  updateYamlCopyButton();
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
  const selectedView = viewName === 'recorded' && recordedAvailable ? 'recorded' : (inputAvailable ? 'input' : 'recorded');
  const showRecorded = selectedView === 'recorded';
  state.yamlActiveView = selectedView;
  els.yamlInputPane.hidden = showRecorded;
  els.yamlRecordedPane.hidden = !showRecorded;
  els.yamlInputTab.classList.toggle('active', inputAvailable && !showRecorded);
  els.yamlRecordedTab.classList.toggle('active', recordedAvailable && showRecorded);
  els.yamlInputTab.setAttribute('aria-selected', String(inputAvailable && !showRecorded));
  els.yamlRecordedTab.setAttribute('aria-selected', String(recordedAvailable && showRecorded));
  updateYamlCopyButton();
}

function updateYamlCopyButton() {
  const content = state.yamlActiveView === 'recorded' ? state.yamlRecordedContent : state.yamlInputContent;
  els.yamlCopy.disabled = !content;
}

async function copyActiveYaml() {
  const content = state.yamlActiveView === 'recorded' ? state.yamlRecordedContent : state.yamlInputContent;
  if (!content) return;
  try {
    await navigator.clipboard.writeText(content);
  } catch {
    const textarea = document.createElement('textarea');
    textarea.value = content;
    textarea.style.position = 'fixed';
    textarea.style.left = '-9999px';
    document.body.appendChild(textarea);
    textarea.select();
    document.execCommand('copy');
    textarea.remove();
  }
}

function renderYamlDisplay(root, display, emptyMessage) {
  root.innerHTML = '';
  if (!display) {
    renderYamlEmpty(root, emptyMessage);
    return;
  }
  const fragment = document.createDocumentFragment();
  fragment.appendChild(renderYamlCaseSummary(display.metadata || {}));
  fragment.appendChild(renderYamlSteps(display.steps || []));
  root.appendChild(fragment);
}

function renderYamlCaseSummary(metadata) {
  const summary = document.createElement('div');
  summary.className = 'yaml-case-summary';

  const titleRow = document.createElement('div');
  titleRow.className = 'yaml-case-title-row';
  const title = document.createElement('div');
  title.className = 'yaml-case-title';
  title.textContent = metadata.title || 'Untitled case';
  titleRow.appendChild(title);
  summary.appendChild(titleRow);

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

function recordingStatusSummary(recording) {
  const parts = [`Recording: ${recording.status || 'missing'}`];
  if (recording.validationStatus) parts.push(`validation: ${recording.validationStatus}`);
  if (Number.isInteger(recording.commandCount)) parts.push(`${recording.commandCount} command${recording.commandCount === 1 ? '' : 's'}`);
  if (recording.draft) parts.push('draft');
  return parts.join(' · ');
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
    { name: 'progress', button: els.progressTab, pane: els.progressPane },
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
  scheduleProgressScroll();
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
els.yamlCopy.addEventListener('click', copyActiveYaml);
els.yamlInputTab.addEventListener('click', () => showYamlView('input'));
els.yamlRecordedTab.addEventListener('click', () => showYamlView('recorded'));
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
    updateRunMode();
    if ((currentRunMode() === 'yaml' || currentRunMode() === 'strict-yaml') && !state.currentRequestId) {
      els.caseYaml.focus();
    }
  });
}
els.previewTab.addEventListener('click', () => showRightTab('preview'));
els.progressTab.addEventListener('click', () => showRightTab('progress'));
els.reportTab.addEventListener('click', () => showRightTab('report'));
clearYamlInput();
clearRecordedYaml();
initPanelResizer();
updateRunMode();
showRightTab('preview');
refreshAll();

