import { useEffect, useLayoutEffect, useMemo, useRef, useState, type RefObject } from 'react';
import type { RunSnapshot, TimelineEvent } from '../../../api/types';

const cancellable = new Set(['preparing', 'running', 'finalizing']);
const LONG_MESSAGE_LENGTH = 140;
const FOLLOW_THRESHOLD = 32;

interface RunTimelineProps {
  snapshot: RunSnapshot | null;
  connection: string;
  selectedStepId: string | null;
  resultHeadingRef: RefObject<HTMLHeadingElement | null>;
  onSelectStep: (stepId: string | null) => void;
  onCancel: () => void;
  onNewRun: () => void;
}

function formatTime(value?: string) {
  if (!value) return '';
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? '' : date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function EventMessage({ event }: { event: TimelineEvent }) {
  const [expanded, setExpanded] = useState(false);
  const [overflowing, setOverflowing] = useState(false);
  const messageRef = useRef<HTMLElement>(null);
  const message = event.message ?? '';
  const messageId = `timeline-message-${event.sequence}`;
  useLayoutEffect(() => {
    const element = messageRef.current;
    if (!element) return;
    const measure = () => {
      if (expanded) return;
      setOverflowing(element.clientWidth > 0 ? element.scrollWidth > element.clientWidth : message.length > LONG_MESSAGE_LENGTH);
    };
    measure();
    const frame = requestAnimationFrame(measure);
    const observer = globalThis.ResizeObserver ? new ResizeObserver(measure) : null;
    observer?.observe(element);
    return () => { cancelAnimationFrame(frame); observer?.disconnect(); };
  }, [expanded, message]);
  if (!message) return null;
  return <span className="event-message-wrap">
    <small ref={messageRef} id={messageId} className={!expanded ? 'event-message event-message--clamped' : 'event-message'}>{message}</small>
    {overflowing && <button className="message-disclosure" type="button" title={expanded ? 'Collapse message' : 'Expand message'} aria-label={expanded ? 'Collapse message' : 'Expand message'} aria-expanded={expanded} aria-controls={messageId} onClick={(clickEvent) => { clickEvent.stopPropagation(); setExpanded((value) => !value); }}>{expanded ? '⌃' : '⌄'}</button>}
  </span>;
}

export function RunTimeline({ snapshot, connection, selectedStepId, resultHeadingRef, onSelectStep, onCancel, onNewRun }: RunTimelineProps) {
  useEffect(() => { if (snapshot?.terminal) resultHeadingRef.current?.focus(); }, [resultHeadingRef, snapshot?.terminal]);
  const events = useMemo(() => [...(snapshot?.events ?? [])].sort((left, right) => left.sequence - right.sequence), [snapshot?.events]);
  const scrollRef = useRef<HTMLDivElement>(null);
  const previousLastSequence = useRef(0);
  const [following, setFollowing] = useState(true);
  const [unseen, setUnseen] = useState(0);
  const lastSequence = snapshot?.events.at(-1)?.sequence ?? 0;
  useEffect(() => {
    const previous = previousLastSequence.current;
    previousLastSequence.current = lastSequence;
    if (!lastSequence || lastSequence <= previous) return;
    if (following) {
      scrollRef.current?.scrollTo?.({ top: scrollRef.current.scrollHeight, behavior: 'auto' });
      setUnseen(0);
    } else {
      setUnseen((value) => value + (snapshot?.events.filter((event) => event.sequence > previous).length ?? 0));
    }
  }, [following, lastSequence, snapshot?.events]);
  if (!snapshot) return <div className="run-loading" role="status"><span className="spinner" aria-hidden="true" />Preparing run details…</div>;
  const source = snapshot.mode === 'explore' ? snapshot.source.goal : snapshot.source.casePath;
  const onTimelineScroll = () => {
    const element = scrollRef.current;
    if (!element) return;
    const atBottom = element.scrollHeight - element.scrollTop - element.clientHeight <= FOLLOW_THRESHOLD;
    setFollowing(atBottom);
    if (atBottom) setUnseen(0);
  };
  const jumpToLatest = () => {
    const element = scrollRef.current;
    if (!element) return;
    element.scrollTop = Math.max(0, element.scrollHeight - element.clientHeight);
    const atBottom = element.scrollHeight - element.scrollTop - element.clientHeight <= FOLLOW_THRESHOLD;
    setFollowing(atBottom);
    if (atBottom) setUnseen(0);
    element.focus();
  };
  return <div className="run-timeline">
    <div className="run-source-summary"><span><strong>Run source · {snapshot.mode === 'explore' ? 'Explore' : 'Strict Replay'}</strong><small>{source ?? 'Source unavailable'}</small></span><span className={`status-badge status-badge--${snapshot.status}`}>{snapshot.status}</span></div>
    <div className="stream-state" role="status">Updates: {connection}</div>
    <div className="timeline-history">
      <div className="timeline-scroll" ref={scrollRef} onScroll={onTimelineScroll} data-following={following} tabIndex={-1} aria-label="Run timeline history">
        {events.length ? <ol className="timeline-list">
          {events.map((event) => {
            const label = event.label || event.tool || event.phase || 'Run update';
            const selectable = snapshot.terminal && Boolean(event.stepId);
            const selected = selectable && selectedStepId === event.stepId;
            const selectAction = () => onSelectStep(selected ? null : event.stepId ?? null);
            return <li key={event.sequence} className={`timeline-row timeline-row--${event.status ?? 'running'}${selectable ? ' timeline-row--selectable' : ''}${selected ? ' timeline-row--selected' : ''}`} onClick={selectable ? selectAction : undefined}>
              {selectable ? <button className="timeline-action-select" type="button" aria-label={`Select action ${label}`} aria-pressed={selected}>
                <span className="timeline-index">{String(event.sequence).padStart(2, '0')}</span>
                <span className="timeline-event-title"><strong>{label}</strong></span>
                <span className="timeline-event-meta"><span className="status-badge">{event.status ?? 'running'}</span><time dateTime={event.time}>{formatTime(event.time)}</time></span>
              </button> : <><span className="timeline-index">{String(event.sequence).padStart(2, '0')}</span><span className="timeline-event-title"><strong>{label}</strong></span><span className="timeline-event-meta"><span className="status-badge">{event.status ?? 'running'}</span><time dateTime={event.time}>{formatTime(event.time)}</time></span></>}
              <span className="timeline-event-main"><EventMessage event={event} /></span>
            </li>;
          })}
        </ol> : <p className="empty-state">No timeline events have been emitted yet.</p>}
      </div>
      {!snapshot.terminal && !following && <button className="jump-latest" type="button" onClick={jumpToLatest}>Jump to latest{unseen ? ` · ${unseen} new` : ''}</button>}
    </div>
    {snapshot.terminal ? <section className={`result-summary result-summary--${snapshot.status}`}>
      <h3 ref={resultHeadingRef} tabIndex={-1}>Run {snapshot.status}</h3>
      <p>{snapshot.summary || 'The run ended without an additional summary.'}</p>
      {snapshot.runId && <p className="mono">Run ID: {snapshot.runId}</p>}
      <button className="button button--primary" type="button" onClick={onNewRun}>New run</button>
    </section> : cancellable.has(snapshot.status) && <button className="button button--danger cancel-button" type="button" disabled={snapshot.cancelRequested} onClick={onCancel}>{snapshot.cancelRequested ? 'Cancellation requested…' : 'Cancel run'}</button>}
  </div>;
}
