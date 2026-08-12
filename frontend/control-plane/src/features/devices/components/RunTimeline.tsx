import { useEffect, useMemo, useRef, useState, type RefObject } from 'react';
import type { RunSnapshot, TimelineEvent } from '../../../api/types';

const cancellable = new Set(['preparing', 'running', 'finalizing']);
const LONG_MESSAGE_LENGTH = 140;
const FOLLOW_THRESHOLD = 32;

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

interface TimelineGroup {
  key: string;
  phase: string;
  events: TimelineEvent[];
  status: string;
}

function phaseLabel(value?: string) {
  const phase = value?.trim();
  if (!phase) return 'Run';
  return phase.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function groupEvents(events: TimelineEvent[]): TimelineGroup[] {
  const groups: TimelineGroup[] = [];
  for (const event of events) {
    const phase = phaseLabel(event.phase);
    const current = groups.at(-1);
    if (!current || current.phase !== phase) {
      groups.push({ key: `${event.sequence}-${phase}`, phase, events: [event], status: event.status ?? 'running' });
      continue;
    }
    current.events.push(event);
    current.status = event.status ?? current.status;
  }
  return groups;
}

function EventMessage({ event }: { event: TimelineEvent }) {
  const [expanded, setExpanded] = useState(false);
  const message = event.message ?? '';
  const long = message.length > LONG_MESSAGE_LENGTH;
  const messageId = `timeline-message-${event.sequence}`;
  if (!message) return null;
  return <span className="event-message-wrap">
    <small id={messageId} className={long && !expanded ? 'event-message event-message--clamped' : 'event-message'}>{message}</small>
    {long && <button className="message-disclosure" type="button" aria-expanded={expanded} aria-controls={messageId} onClick={() => setExpanded((value) => !value)}>{expanded ? 'Collapse message' : 'Expand message'}</button>}
  </span>;
}

export function RunTimeline({ snapshot, connection, resultHeadingRef, onCancel, onNewRun }: RunTimelineProps) {
  useEffect(() => { if (snapshot?.terminal) resultHeadingRef.current?.focus(); }, [resultHeadingRef, snapshot?.terminal]);
  const groups = useMemo(() => groupEvents(snapshot?.events ?? []), [snapshot?.events]);
  const [groupChoices, setGroupChoices] = useState<Record<string, boolean>>({});
  const scrollRef = useRef<HTMLDivElement>(null);
  const previousLastSequence = useRef(0);
  const [following, setFollowing] = useState(true);
  const [unseen, setUnseen] = useState(0);
  const [jumpFocused, setJumpFocused] = useState(false);
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
  useEffect(() => {
    const validKeys = new Set(groups.map((group) => group.key));
    setGroupChoices((choices) => Object.fromEntries(Object.entries(choices).filter(([key]) => validKeys.has(key))));
  }, [groups]);
  if (!snapshot) return <div className="run-loading" role="status"><span className="spinner" aria-hidden="true" />Preparing run details…</div>;
  const source = snapshot.mode === 'explore' ? snapshot.source.goal : snapshot.source.casePath;
  const latestGroupKey = groups.at(-1)?.key;
  const onTimelineScroll = () => {
    const element = scrollRef.current;
    if (!element) return;
    const atBottom = element.scrollHeight - element.scrollTop - element.clientHeight <= FOLLOW_THRESHOLD;
    setFollowing(atBottom);
    if (atBottom) setUnseen(0);
  };
  const jumpToLatest = () => {
    const reducedMotion = globalThis.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false;
    scrollRef.current?.scrollTo?.({ top: scrollRef.current.scrollHeight, behavior: reducedMotion ? 'auto' : 'smooth' });
    setFollowing(true);
    setUnseen(0);
  };
  return <div className="run-timeline">
    <div className="run-source-summary"><span><strong>Run source · {snapshot.mode === 'explore' ? 'Explore' : 'Strict Replay'}</strong><small>{source ?? 'Source unavailable'}</small></span><span className={`status-badge status-badge--${snapshot.status}`}>{snapshot.status}</span></div>
    <div className="stream-state" role="status">Updates: {connection}</div>
    <div className="timeline-history">
      <div className="timeline-scroll" ref={scrollRef} onScroll={onTimelineScroll} data-following={following}>
        {groups.length ? <div className="timeline-groups">
          {groups.map((group) => {
            const expanded = groupChoices[group.key] ?? group.key === latestGroupKey;
            const panelId = `timeline-group-${group.key.replace(/[^a-zA-Z0-9_-]/g, '-')}`;
            return <section className="timeline-group" key={group.key}>
              <button className="timeline-group-toggle" type="button" aria-expanded={expanded} aria-controls={panelId} onClick={() => setGroupChoices((choices) => ({ ...choices, [group.key]: !expanded }))}>
                <span><strong>{group.phase}</strong><small>{group.events.length} {group.events.length === 1 ? 'event' : 'events'}</small></span>
                <span><span className="status-badge">{group.status}</span><span aria-hidden="true">{expanded ? '−' : '+'}</span></span>
              </button>
              <ol id={panelId} className="timeline-list" hidden={!expanded}>
                {group.events.map((event) => <li key={event.sequence} className={`timeline-row timeline-row--${event.status ?? 'running'}`}>
                  <span className="timeline-index">{String(event.sequence).padStart(2, '0')}</span>
                  <span className="timeline-event-main"><strong>{event.label || event.tool || event.phase || 'Run update'}</strong><EventMessage event={event} /></span>
                  <span className="timeline-event-meta"><span className="status-badge">{event.status ?? 'running'}</span><time dateTime={event.time}>{formatTime(event.time)}</time></span>
                </li>)}
              </ol>
            </section>;
          })}
        </div> : <p className="empty-state">No timeline events have been emitted yet.</p>}
      </div>
      {(!following || jumpFocused) && <button className="jump-latest" type="button" onFocus={() => setJumpFocused(true)} onBlur={() => setJumpFocused(false)} onClick={jumpToLatest}>Jump to latest{unseen ? ` · ${unseen} new` : ''}</button>}
    </div>
    {snapshot.terminal ? <section className={`result-summary result-summary--${snapshot.status}`}>
      <h3 ref={resultHeadingRef} tabIndex={-1}>Run {snapshot.status}</h3>
      <p>{snapshot.summary || 'The run ended without an additional summary.'}</p>
      {snapshot.runId && <p className="mono">Run ID: {snapshot.runId}</p>}
      <button className="button button--primary" type="button" onClick={onNewRun}>New run</button>
    </section> : cancellable.has(snapshot.status) && <button className="button button--danger cancel-button" type="button" disabled={snapshot.cancelRequested} onClick={onCancel}>{snapshot.cancelRequested ? 'Cancellation requested…' : 'Cancel run'}</button>}
  </div>;
}
