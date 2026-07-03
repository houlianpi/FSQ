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

const els = {
  status: document.getElementById('server-status'),
  refresh: document.getElementById('refresh'),
  deviceSelect: document.getElementById('device-select'),
  sessionMessage: document.getElementById('session-message'),
  goal: document.getElementById('goal'),
  caseYaml: document.getElementById('case-yaml'),
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

  els.goal.value = '';
  els.caseYaml.value = '';
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
  const isYaml = mode === 'yaml' || mode === 'strict-yaml';
  els.goal.hidden = isYaml;
  els.caseYaml.hidden = !isYaml;
  if (!state.currentRequestId) setRunButtonIdle();
}

async function startExecution(payload) {
  if (!(await ensureSession())) return;
  state.progressSequence = 0;
  state.lastProgressSequence = 0;
  state.progressDetailOpenState.clear();
  state.replayRequestId = null;
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
    startProgressPolling();
    await refreshStatus();
  } catch (error) {
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
    state.replayRequestId = progress.result?.runId || progress.runId || state.replayRequestId;
    setRunButtonIdle();
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

els.refresh.addEventListener('click', clearPage);
els.runSelected.addEventListener('click', runSelected);
for (const input of els.runModeInputs) {
  input.addEventListener('change', updateRunMode);
}
els.previewTab.addEventListener('click', () => showRightTab('preview'));
els.progressTab.addEventListener('click', () => showRightTab('progress'));
els.reportTab.addEventListener('click', () => showRightTab('report'));
updateRunMode();
showRightTab('preview');
refreshAll();

