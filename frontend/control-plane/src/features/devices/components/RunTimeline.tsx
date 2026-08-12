import { useEffect, type RefObject } from 'react';
import type { RunSnapshot } from '../../../api/types';

const cancellable = new Set(['preparing', 'running', 'finalizing']);

interface RunTimelineProps {
  snapshot: RunSnapshot | null;
  connection: string;
  resultHeadingRef: RefObject<HTMLHeadingElement | null>;
  onCancel: () => void;
  onNewRun: () => void;
}

function formatTime(value?: string) {
  if (!value) return '';
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? '' : date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

export function RunTimeline({ snapshot, connection, resultHeadingRef, onCancel, onNewRun }: RunTimelineProps) {
  useEffect(() => { if (snapshot?.terminal) resultHeadingRef.current?.focus(); }, [resultHeadingRef, snapshot?.terminal]);
  if (!snapshot) return <div className="run-loading" role="status"><span className="spinner" aria-hidden="true" />Preparing run details…</div>;
  const source = snapshot.mode === 'explore' ? snapshot.source.goal : snapshot.source.casePath;
  return <div className="run-timeline">
    <div className="run-source-summary"><span><strong>Run source · {snapshot.mode === 'explore' ? 'Explore' : 'Strict Replay'}</strong><small>{source ?? 'Source unavailable'}</small></span><span className={`status-badge status-badge--${snapshot.status}`}>{snapshot.status}</span></div>
    <div className="stream-state" role="status">Updates: {connection}</div>
    {snapshot.events.length ? <ol className="timeline-list">
      {snapshot.events.map((event) => <li key={event.sequence} className={`timeline-row timeline-row--${event.status ?? 'running'}`}>
        <span className="timeline-index">{String(event.sequence).padStart(2, '0')}</span>
        <span><strong>{event.label || event.tool || event.phase || 'Run update'}</strong><small>{[event.phase, event.message].filter(Boolean).join(' · ')}</small></span>
        <span><span className="status-badge">{event.status ?? 'running'}</span><time dateTime={event.time}>{formatTime(event.time)}</time></span>
      </li>)}
    </ol> : <p className="empty-state">No timeline events have been emitted yet.</p>}
    {snapshot.terminal ? <section className={`result-summary result-summary--${snapshot.status}`}>
      <h3 ref={resultHeadingRef} tabIndex={-1}>Run {snapshot.status}</h3>
      <p>{snapshot.summary || 'The run ended without an additional summary.'}</p>
      {snapshot.runId && <p className="mono">Run ID: {snapshot.runId}</p>}
      <button className="button button--primary" type="button" onClick={onNewRun}>New run</button>
    </section> : cancellable.has(snapshot.status) && <button className="button button--danger cancel-button" type="button" disabled={snapshot.cancelRequested} onClick={onCancel}>{snapshot.cancelRequested ? 'Cancellation requested…' : 'Cancel run'}</button>}
  </div>;
}
