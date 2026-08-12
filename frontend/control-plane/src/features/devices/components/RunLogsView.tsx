import { useEffect, useRef, useState } from 'react';
import type { TimelineEvent } from '../../../api/types';

const LONG_MESSAGE_LENGTH = 140;
const FOLLOW_THRESHOLD = 32;

function LogMessage({ event }: { event: TimelineEvent }) {
  const [expanded, setExpanded] = useState(false);
  const message = event.message ?? '—';
  const long = message.length > LONG_MESSAGE_LENGTH;
  const messageId = `log-message-${event.sequence}`;
  return <div className="event-message-wrap">
    <span id={messageId} className={long && !expanded ? 'event-message event-message--clamped' : 'event-message'}>{message}</span>
    {long && <button className="message-disclosure" type="button" aria-expanded={expanded} aria-controls={messageId} onClick={() => setExpanded((value) => !value)}>{expanded ? 'Collapse message' : 'Expand message'}</button>}
  </div>;
}

export function RunLogsView({ events }: { events: TimelineEvent[] }) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const previousLastSequence = useRef(0);
  const [following, setFollowing] = useState(true);
  const [unseen, setUnseen] = useState(0);
  const [jumpFocused, setJumpFocused] = useState(false);
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
    const reducedMotion = globalThis.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false;
    scrollRef.current?.scrollTo?.({ top: scrollRef.current.scrollHeight, behavior: reducedMotion ? 'auto' : 'smooth' });
    setFollowing(true);
    setUnseen(0);
  };
  return <div className="logs-region">
    <div className="logs-table-wrap" ref={scrollRef} onScroll={onScroll} data-following={following}><table className="logs-table"><caption className="visually-hidden">Structured run logs</caption><thead><tr><th>Time</th><th>Level</th><th>Phase</th><th>Tool</th><th>Status</th><th>Message</th></tr></thead><tbody>
      {events.map((event) => <tr key={event.sequence}><td><time dateTime={event.time}>{event.time ? new Date(event.time).toLocaleTimeString() : '—'}</time></td><td>{event.level ?? 'info'}</td><td>{event.phase ?? '—'}</td><td>{event.tool ?? event.label ?? '—'}</td><td>{event.status ?? '—'}</td><td><LogMessage event={event} /></td></tr>)}
    </tbody></table></div>
    {(!following || jumpFocused) && <button className="jump-latest jump-latest--logs" type="button" onFocus={() => setJumpFocused(true)} onBlur={() => setJumpFocused(false)} onClick={jumpToLatest}>Jump to latest{unseen ? ` · ${unseen} new` : ''}</button>}
  </div>;
}
