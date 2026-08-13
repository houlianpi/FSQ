import EBML from 'ts-ebml/dist/EBML.js';
import type { ReplayFrame } from '../../../api/types';

const { Decoder, Reader, tools: ebmlTools } = EBML;
const SAME_FRAME_DELAY_MS = 100;
const MIN_FRAME_DELAY_MS = 250;
const MAX_FRAME_DELAY_MS = 750;
const FALLBACK_FRAME_DELAY_MS = 350;
const FINAL_FRAME_DELAY_MS = 400;
const TIME_SCALE = 10;

function delayFor(current: ReplayFrame, next?: ReplayFrame) {
  if (next && current.timestamp !== null && next.timestamp !== null) {
    const delay = Math.max(0, next.timestamp - current.timestamp);
    if (delay === 0) return SAME_FRAME_DELAY_MS;
    return Math.min(MAX_FRAME_DELAY_MS, Math.max(MIN_FRAME_DELAY_MS, delay / TIME_SCALE));
  }
  return next ? FALLBACK_FRAME_DELAY_MS : FINAL_FRAME_DELAY_MS;
}

function wait(duration: number, signal: AbortSignal) {
  return new Promise<void>((resolve, reject) => {
    const timer = window.setTimeout(resolve, duration);
    signal.addEventListener('abort', () => { window.clearTimeout(timer); reject(new DOMException('Aborted', 'AbortError')); }, { once: true });
  });
}

function loadImage(frame: ReplayFrame, signal: AbortSignal) {
  return new Promise<HTMLImageElement>((resolve, reject) => {
    const image = new Image();
    const abort = () => { image.src = ''; reject(new DOMException('Aborted', 'AbortError')); };
    signal.addEventListener('abort', abort, { once: true });
    image.onload = () => { signal.removeEventListener('abort', abort); resolve(image); };
    image.onerror = () => { signal.removeEventListener('abort', abort); reject(new Error(`Replay frame ${frame.index} could not be decoded.`)); };
    if (!frame.contentBase64) { reject(new Error(`Replay frame ${frame.index} has no image content.`)); return; }
    image.src = `data:${frame.mimeType};base64,${frame.contentBase64}`;
  });
}

function mimeType() {
  return ['video/webm;codecs=vp9', 'video/webm;codecs=vp8', 'video/webm'].find((candidate) => MediaRecorder.isTypeSupported(candidate)) ?? '';
}

function buildCues(elements: Array<Record<string, unknown>>, trackNumber: number) {
  const cues: Array<Record<string, number>> = [];
  elements.forEach((element, index) => {
    if (element.type !== 'm' || element.name !== 'Cluster' || element.isEnd) return;
    const position = Number(element.tagStart);
    if (!Number.isFinite(position)) return;
    for (const child of elements.slice(index + 1)) {
      if (child.type === 'm' && child.name === 'Cluster') break;
      if ((child.name === 'Timestamp' || child.name === 'Timecode') && Number.isFinite(Number(child.value))) {
        cues.push({ CueTrack: trackNumber, CueClusterPosition: position, CueTime: Number(child.value) });
        break;
      }
    }
  });
  return cues;
}

async function makeSeekable(blob: Blob, durationMs: number, signal: AbortSignal) {
  const buffer = await blob.arrayBuffer();
  const decoder = new Decoder();
  const reader = new Reader();
  reader.logging = false;
  reader.drop_default_duration = false;
  const elements = decoder.decode(buffer) as Array<Record<string, unknown>>;
  elements.forEach((element) => reader.read(element));
  reader.stop();
  const duration = Number(reader.duration) > 0 ? Number(reader.duration) : durationMs;
  const cues = Array.isArray(reader.cues) && reader.cues.length ? reader.cues : buildCues(elements, Number(reader.trackInfo?.trackNumber) || 1);
  if (!duration || !cues.length) throw new Error('Replay video could not be indexed for seeking.');
  const metadata = Array.isArray(reader.metadatas) && reader.metadatas.length ? reader.metadatas : elements;
  const refined = ebmlTools.makeMetadataSeekable(metadata, duration, cues);
  const seekable = new Blob([new Uint8Array(refined).buffer, buffer.slice(reader.metadataSize)], { type: 'video/webm' });
  if (!await validateReplayBlob(seekable, true, signal)) {
    if (signal.aborted) throw new DOMException('Aborted', 'AbortError');
    throw new Error('Replay video is not seekable.');
  }
  return seekable;
}

export function validateReplayBlob(blob: Blob, requireSeekable = false, signal?: AbortSignal) {
  return new Promise<boolean>((resolve) => {
    const url = URL.createObjectURL(blob);
    const video = document.createElement('video');
    let finished = false;
    const done = (value: boolean) => {
      if (finished) return;
      finished = true;
      window.clearTimeout(timer);
      signal?.removeEventListener('abort', abort);
      video.onloadedmetadata = null; video.onerror = null;
      video.pause(); video.removeAttribute('src'); video.load();
      URL.revokeObjectURL(url);
      resolve(value);
    };
    const abort = () => done(false);
    const timer = window.setTimeout(() => done(false), 5000);
    signal?.addEventListener('abort', abort, { once: true });
    if (signal?.aborted) { done(false); return; }
    video.onloadedmetadata = () => done(video.readyState >= HTMLMediaElement.HAVE_METADATA && (!requireSeekable || hasSeekableRange(video)));
    video.onerror = () => done(false);
    video.src = url;
    video.load();
  });
}

export async function generateReplayVideo(frames: ReplayFrame[], signal: AbortSignal): Promise<Blob> {
  if (!frames.length) throw new Error('No replay frames were captured.');
  if (!globalThis.MediaRecorder) throw new Error('This browser cannot generate replay video.');
  const type = mimeType();
  if (!type) throw new Error('This browser has no supported WebM recorder.');
  const canvas = document.createElement('canvas');
  const context = canvas.getContext('2d');
  if (!context || !canvas.captureStream) throw new Error('Canvas replay capture is unavailable.');
  const baseFrame = [...frames].sort((left, right) => (right.contentBase64?.length ?? 0) - (left.contentBase64?.length ?? 0))[0];
  const base = await loadImage(baseFrame, signal);
  canvas.width = base.naturalWidth || base.width;
  canvas.height = base.naturalHeight || base.height;
  const first = baseFrame === frames[0] ? base : await loadImage(frames[0], signal);
  context.drawImage(first, 0, 0, canvas.width, canvas.height);
  const chunks: Blob[] = [];
  const stream = canvas.captureStream(30);
  const videoTrack = stream.getVideoTracks()[0] as MediaStreamTrack & { requestFrame?: () => void };
  const requestFrame = () => videoTrack?.requestFrame?.();
  const recorder = new MediaRecorder(stream, { mimeType: type });
  recorder.ondataavailable = (event) => { if (event.data.size) chunks.push(event.data); };
  const started = performance.now();
  try {
    recorder.start();
    requestFrame();
    for (let index = 1; index < frames.length; index += 1) {
      await wait(delayFor(frames[index - 1], frames[index]), signal);
      const image = await loadImage(frames[index], signal);
      context.drawImage(image, 0, 0, canvas.width, canvas.height);
      requestFrame();
    }
    await wait(FINAL_FRAME_DELAY_MS, signal);
    requestFrame();
    await new Promise<void>((resolve) => { recorder.onstop = () => resolve(); recorder.stop(); });
  } finally {
    if (recorder.state !== 'inactive') recorder.stop();
    stream.getTracks().forEach((track) => track.stop());
  }
  const blob = new Blob(chunks, { type });
  if (!blob.size) throw new Error('Replay video generation produced no data.');
  const seekable = await makeSeekable(blob, performance.now() - started, signal);
  if (!await validateReplayBlob(seekable, true, signal)) {
    if (signal.aborted) throw new DOMException('Aborted', 'AbortError');
    throw new Error('Generated replay video is not seekable.');
  }
  return seekable;
}

export function blobToBase64(blob: Blob) {
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(',', 2)[1] ?? '');
    reader.onerror = () => reject(reader.error ?? new Error('Replay video could not be read.'));
    reader.readAsDataURL(blob);
  });
}

export function hasSeekableRange(video: Pick<HTMLVideoElement, 'seekable'>) {
  return video.seekable.length > 0;
}
