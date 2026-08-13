import { useEffect, useState } from 'react';
import { controlPlaneClient, toApiError } from '../../../api/controlPlaneClient';
import { blobToBase64, generateReplayVideo } from '../replay/generateReplayVideo';

export function ReplayVideoView({ requestId }: { requestId: string }) {
  const [state, setState] = useState<'loading' | 'generating' | 'available' | 'unavailable' | 'error'>('loading');
  const [videoUrl, setVideoUrl] = useState<string | null>(null);
  const [message, setMessage] = useState('');
  const [regeneration, setRegeneration] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    const run = async () => {
      setState('loading'); setVideoUrl(null); setMessage('');
      try {
        if (regeneration === 0) {
          const existing = await controlPlaneClient.replayVideo(requestId, controller.signal);
          if (existing.available && existing.videoUrl) { setVideoUrl(existing.videoUrl); setState('available'); return; }
        }
        const replay = await controlPlaneClient.replayFrames(requestId, controller.signal);
        const readableFrames = replay.frames.filter((frame) => frame.contentBase64);
        if (!replay.available || !readableFrames.length) { setMessage(replay.message ?? (replay.frames.map((frame) => frame.error).filter(Boolean).join(' ') || 'No replay frames were captured.')); setState('unavailable'); return; }
        setState('generating');
        const blob = await generateReplayVideo(readableFrames, controller.signal);
        const uploaded = await controlPlaneClient.uploadReplayVideo(requestId, blob.type || 'video/webm', await blobToBase64(blob), controller.signal);
        if (!uploaded.videoUrl) throw new Error('Stored replay video URL is missing.');
        setVideoUrl(uploaded.videoUrl); setState('available');
      } catch (error) {
        if (controller.signal.aborted) return;
        setMessage(toApiError(error).message); setState('error');
      }
    };
    void run();
    return () => controller.abort();
  }, [regeneration, requestId]);
  if (state === 'available' && videoUrl) return <div className="replay-video-view"><video src={`${videoUrl}?generation=${regeneration}`} controls preload="metadata" aria-label="Run replay video" onError={() => {
    if (regeneration === 0) { setRegeneration(1); return; }
    setMessage('The stored replay video could not be played.'); setState('error');
  }} /></div>;
  const copy = {
    loading: ['Loading run replay', 'Checking for a stored replay video and persisted frames…'],
    generating: ['Generating run replay', 'Encoding screenshot frames and storing a seekable WebM…'],
    unavailable: ['Run replay unavailable', message],
    error: ['Run replay failed', message],
  }[state as Exclude<typeof state, 'available'>];
  return <div className={`evidence-message evidence-message--${state}`} role={state === 'error' ? 'alert' : 'status'}><strong>{copy[0]}</strong><p>{copy[1]}</p></div>;
}
