import { useEffect, useLayoutEffect, useRef, useState, type CSSProperties } from 'react';
import type { TimelineEvent } from '../../../api/types';

const LONG_MESSAGE_LENGTH = 140;
const FOLLOW_THRESHOLD = 32;
const LOG_COLUMNS = [
  { key: 'time', label: 'Time', defaultWidth: 82, minWidth: 56 },
  { key: 'level', label: 'Level', defaultWidth: 58, minWidth: 48 },
  { key: 'phase', label: 'Phase', defaultWidth: 86, minWidth: 58 },
  { key: 'tool', label: 'Tool', defaultWidth: 128, minWidth: 72 },
  { key: 'status', label: 'Status', defaultWidth: 82, minWidth: 58 },
  { key: 'message', label: 'Message', defaultWidth: 280, minWidth: 180 },
  { key: 'event', label: 'Event', defaultWidth: 180, minWidth: 110 },
] as const;

type LogColumnKey = typeof LOG_COLUMNS[number]['key'];
type LogColumnWidths = Record<LogColumnKey, number>;

interface LogStyle extends CSSProperties {
  '--logs-table-width': string;
  [key: `--log-${string}-width`]: string;
}

const defaultColumnWidths = Object.fromEntries(LOG_COLUMNS.map((column) => [column.key, column.defaultWidth])) as LogColumnWidths;

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

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

function EventDetails({ event }: { event: TimelineEvent }) {
  return <details className="log-event-details">
    <summary>Details</summary>
    <pre className="log-event-json">{JSON.stringify(event, null, 2)}</pre>
  </details>;
}

export function RunLogsView({ events, active }: { events: TimelineEvent[]; active: boolean }) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const previousLastSequence = useRef(0);
  const [following, setFollowing] = useState(true);
  const [columnWidths, setColumnWidths] = useState<LogColumnWidths>(defaultColumnWidths);
  const lastSequence = events.at(-1)?.sequence ?? 0;
  useEffect(() => {
    const previous = previousLastSequence.current;
    previousLastSequence.current = lastSequence;
    if (!lastSequence || lastSequence <= previous) return;
    if (following) {
      scrollRef.current?.scrollTo?.({ top: scrollRef.current.scrollHeight, behavior: 'auto' });
    }
  }, [events, following, lastSequence]);
  if (!events.length) return <div className="evidence-message"><strong>Logs not yet available</strong><p>Safe structured events will appear as the run progresses.</p></div>;
  const onScroll = () => {
    const element = scrollRef.current;
    if (!element) return;
    const atBottom = element.scrollHeight - element.scrollTop - element.clientHeight <= FOLLOW_THRESHOLD;
    setFollowing(atBottom);
  };
  const onColumnResizeStart = (boundaryIndex: number) => (event: React.PointerEvent<HTMLButtonElement>) => {
    event.preventDefault();
    const leftColumn = LOG_COLUMNS[boundaryIndex];
    const rightColumn = LOG_COLUMNS[boundaryIndex + 1];
    if (!leftColumn || !rightColumn) return;
    const startX = event.clientX;
    const startLeftWidth = columnWidths[leftColumn.key];
    const startRightWidth = columnWidths[rightColumn.key];
    const pairWidth = startLeftWidth + startRightWidth;
    const minLeftWidth = leftColumn.minWidth;
    const minRightWidth = rightColumn.minWidth;
    const onMove = (moveEvent: PointerEvent) => {
      const nextLeftWidth = clamp(startLeftWidth + moveEvent.clientX - startX, minLeftWidth, pairWidth - minRightWidth);
      setColumnWidths((current) => ({
        ...current,
        [leftColumn.key]: nextLeftWidth,
        [rightColumn.key]: pairWidth - nextLeftWidth,
      }));
    };
    const onUp = () => {
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerup', onUp);
    };
    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onUp, { once: true });
  };
  const tableWidth = LOG_COLUMNS.reduce((total, column) => total + columnWidths[column.key], 0);
  const tableStyle = LOG_COLUMNS.reduce<LogStyle>((style, column) => {
    style[`--log-${column.key}-width`] = `${columnWidths[column.key]}px`;
    return style;
  }, { '--logs-table-width': `${tableWidth}px` });
  return <div className="logs-region">
    <div className="logs-table-wrap" ref={scrollRef} onScroll={onScroll} data-following={following} tabIndex={-1} aria-label="Structured run logs history"><table className="logs-table" style={tableStyle}><caption className="visually-hidden">Structured run logs</caption><colgroup>{LOG_COLUMNS.map((column) => <col key={column.key} style={{ width: `var(--log-${column.key}-width)` }} />)}</colgroup><thead><tr>{LOG_COLUMNS.map((column, index) => <th key={column.key}><span className="log-column-heading"><span>{column.label}</span>{index < LOG_COLUMNS.length - 1 && <button className="log-column-resizer" type="button" aria-label={`Resize ${column.label} and ${LOG_COLUMNS[index + 1].label} columns`} onPointerDown={onColumnResizeStart(index)} />}</span></th>)}</tr></thead><tbody>
      {events.map((event) => <tr key={event.sequence}><td><time dateTime={event.time}>{event.time ? new Date(event.time).toLocaleTimeString() : '—'}</time></td><td>{event.level ?? 'info'}</td><td>{event.phase ?? '—'}</td><td>{event.tool ?? event.label ?? '—'}</td><td>{event.status ?? '—'}</td><td><LogMessage event={event} /></td><td><EventDetails event={event} /></td></tr>)}
    </tbody></table></div>
  </div>;
}
