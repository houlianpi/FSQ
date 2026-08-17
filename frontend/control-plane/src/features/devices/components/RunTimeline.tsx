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

export function RunTimeline({ snapshot, connection, selectedStepId, onSelectStep, onCancel, onNewRun }: RunTimelineProps) {
  const events = useMemo(() => [...(snapshot?.events ?? [])].sort((left, right) => left.sequence - right.sequence), [snapshot?.events]);
  const scrollRef = useRef<HTMLDivElement>(null);
  const previousLastSequence = useRef(0);
  const [following, setFollowing] = useState(true);
  const [sourceExpanded, setSourceExpanded] = useState(false);
  const [sourceOverflowing, setSourceOverflowing] = useState(false);
  const sourceRef = useRef<HTMLElement>(null);
  const [unseen, setUnseen] = useState(0);
  const lastSequence = snapshot?.events.at(-1)?.sequence ?? 0;
  const source = snapshot?.mode === 'explore' ? snapshot.source.goal : snapshot?.source.casePath;
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
  useLayoutEffect(() => {
    const element = sourceRef.current;
    if (!element) return;
    const measure = () => {
      if (sourceExpanded) return;
      setSourceOverflowing(element.clientWidth > 0 ? element.scrollWidth > element.clientWidth : Boolean(source && source.length > LONG_MESSAGE_LENGTH));
    };
    measure();
    const frame = requestAnimationFrame(measure);
    const observer = globalThis.ResizeObserver ? new ResizeObserver(measure) : null;
    observer?.observe(element);
    return () => { cancelAnimationFrame(frame); observer?.disconnect(); };
  }, [source, sourceExpanded]);
  if (!snapshot) return <div className="run-loading" role="status"><span className="spinner" aria-hidden="true" />Preparing run details…</div>;
  const activeStepId = !snapshot.terminal ? snapshot.activeStep?.stepId : null;
  let latestActiveStepSequence: number | null = null;
  if (activeStepId) {
    for (const event of events) {
      if (event.stepId === activeStepId) latestActiveStepSequence = event.sequence;
    }
  }
  const activeStepHasNewerOutsideProgress = latestActiveStepSequence != null && events.some((event) => event.sequence > latestActiveStepSequence && event.stepId !== activeStepId);
  const activeStepMatched = Boolean(activeStepId && latestActiveStepSequence != null && !activeStepHasNewerOutsideProgress);
  let latestRunningEvent: TimelineEvent | null = null;
  for (let index = events.length - 1; index >= 0; index -= 1) {
    if (events[index].status === 'running') { latestRunningEvent = events[index]; break; }
  }
  const activeFallbackSequence = !snapshot.terminal && !activeStepMatched ? (latestRunningEvent ?? events.at(-1))?.sequence : null;
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
    <div className={`run-source-summary${sourceExpanded ? ' run-source-summary--expanded' : ''}`}><strong>Run source · {snapshot.mode === 'explore' ? 'Explore' : 'Strict Replay'}</strong><span className="run-source-line"><small ref={sourceRef}>{source ?? 'Source unavailable'}</small>{sourceOverflowing && <button className="message-disclosure run-source-disclosure" type="button" aria-label={sourceExpanded ? 'Collapse run source' : 'Expand run source'} aria-expanded={sourceExpanded} onClick={() => setSourceExpanded((value) => !value)}>{sourceExpanded ? '⌃' : '⌄'}</button>}</span></div>
    <div className="timeline-history">
      <div className="timeline-scroll" ref={scrollRef} onScroll={onTimelineScroll} data-following={following} tabIndex={-1} aria-label="Run timeline history">
        {events.length ? <ol className="timeline-list">
          {events.map((event) => {
            const label = event.label || event.tool || event.phase || 'Run update';
            const selectable = snapshot.terminal && Boolean(event.stepId);
            const selected = selectable && selectedStepId === event.stepId;
            const active = !snapshot.terminal && (activeStepMatched ? event.stepId === activeStepId : event.sequence === activeFallbackSequence);
            const selectAction = () => onSelectStep(selected ? null : event.stepId ?? null);
            const statusClass = event.status ? ` timeline-row--${event.status}` : '';
            const statusBadge = event.status ? <span className={`status-badge status-badge--${event.status}`}>{event.status}</span> : null;
            return <li key={event.sequence} className={`timeline-row${statusClass}${active ? ' timeline-row--active' : ''}${selectable ? ' timeline-row--selectable' : ''}${selected ? ' timeline-row--selected' : ''}`} onClick={selectable ? selectAction : undefined}>
              {selectable ? <button className="timeline-action-select" type="button" aria-label={`Select action ${label}`} aria-pressed={selected}>
                <span className="timeline-index">{String(event.sequence).padStart(2, '0')}</span>
                <span className="timeline-event-title"><strong>{label}</strong></span>
                {statusBadge && <span className="timeline-event-meta">{statusBadge}</span>}
              </button> : <><span className="timeline-index">{String(event.sequence).padStart(2, '0')}</span><span className="timeline-event-title"><strong>{label}</strong></span>{statusBadge && <span className="timeline-event-meta">{statusBadge}</span>}</>}
              <span className="timeline-event-main"><EventMessage event={event} /></span>
            </li>;
          })}
        </ol> : <p className="empty-state">No timeline events have been emitted yet.</p>}
      </div>
      {!snapshot.terminal && !following && <button className="jump-latest" type="button" onClick={jumpToLatest}>Jump to latest{unseen ? ` · ${unseen} new` : ''}</button>}
    </div>
    {!snapshot.terminal && cancellable.has(snapshot.status) && <button className="button button--danger cancel-button" type="button" disabled={snapshot.cancelRequested} onClick={onCancel}>{snapshot.cancelRequested ? 'Cancellation requested…' : 'Cancel run'}</button>}
    {snapshot.terminal && <div className="terminal-actions" aria-label="Completed run actions">
      <button className="button" type="button" disabled title="Save yaml is not available yet">Save yaml</button>
      <button className="button button--primary" type="button" onClick={onNewRun}>New run</button>
    </div>}
  </div>;
}
