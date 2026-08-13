import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import type { TimelineEvent } from '../../../api/types';

const LONG_MESSAGE_LENGTH = 140;
const FOLLOW_THRESHOLD = 32;

function LogMessage({ event }: { event: TimelineEvent }) {
  const [expanded, setExpanded] = useState(false);
  const [overflowing, setOverflowing] = useState(false);
  const messageRef = useRef<HTMLSpanElement>(null);
  const message = event.message ?? '—';
  const messageId = `log-message-${event.sequence}`;
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
  return <div className="event-message-wrap">
    <span ref={messageRef} id={messageId} className={!expanded ? 'event-message event-message--clamped' : 'event-message'}>{message}</span>
    {overflowing && <button className="message-disclosure" type="button" title={expanded ? 'Collapse message' : 'Expand message'} aria-label={expanded ? 'Collapse message' : 'Expand message'} aria-expanded={expanded} aria-controls={messageId} onClick={() => setExpanded((value) => !value)}>{expanded ? '⌃' : '⌄'}</button>}
  </div>;
}

export function RunLogsView({ events, active }: { events: TimelineEvent[]; active: boolean }) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const previousLastSequence = useRef(0);
  const [following, setFollowing] = useState(true);
  const [unseen, setUnseen] = useState(0);
  const lastSequence = events.at(-1)?.sequence ?? 0;
  useEffect(() => {
    const previous = previousLastSequence.current;
    previousLastSequence.current = lastSequence;
    if (!lastSequence || lastSequence <= previous) return;
    if (following) {
      scrollRef.current?.scrollTo?.({ top: scrollRef.current.scrollHeight, behavior: 'auto' });
      setUnseen(0);
    } else {
      setUnseen((value) => value + events.filter((event) => event.sequence > previous).length);
    }
  }, [events, following, lastSequence]);
  if (!events.length) return <div className="evidence-message"><strong>Logs not yet available</strong><p>Safe structured events will appear as the run progresses.</p></div>;
  const onScroll = () => {
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
  return <div className="logs-region">
    <div className="logs-table-wrap" ref={scrollRef} onScroll={onScroll} data-following={following} tabIndex={-1} aria-label="Structured run logs history"><table className="logs-table"><caption className="visually-hidden">Structured run logs</caption><thead><tr><th>Time</th><th>Level</th><th>Phase</th><th>Tool</th><th>Status</th><th>Message</th></tr></thead><tbody>
      {events.map((event) => <tr key={event.sequence}><td><time dateTime={event.time}>{event.time ? new Date(event.time).toLocaleTimeString() : '—'}</time></td><td>{event.level ?? 'info'}</td><td>{event.phase ?? '—'}</td><td>{event.tool ?? event.label ?? '—'}</td><td>{event.status ?? '—'}</td><td><LogMessage event={event} /></td></tr>)}
    </tbody></table></div>
    {active && !following && <button className="jump-latest jump-latest--logs" type="button" onClick={jumpToLatest}>Jump to latest{unseen ? ` · ${unseen} new` : ''}</button>}
  </div>;
}
