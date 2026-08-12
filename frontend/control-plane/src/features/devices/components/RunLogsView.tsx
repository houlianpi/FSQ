import type { TimelineEvent } from '../../../api/types';

export function RunLogsView({ events }: { events: TimelineEvent[] }) {
  if (!events.length) return <div className="evidence-message"><strong>Logs not yet available</strong><p>Safe structured events will appear as the run progresses.</p></div>;
  return <div className="logs-table-wrap"><table className="logs-table"><caption className="visually-hidden">Structured run logs</caption><thead><tr><th>Time</th><th>Level</th><th>Phase</th><th>Tool</th><th>Status</th><th>Message</th></tr></thead><tbody>
    {events.map((event) => <tr key={event.sequence}><td><time dateTime={event.time}>{event.time ? new Date(event.time).toLocaleTimeString() : '—'}</time></td><td>{event.level ?? 'info'}</td><td>{event.phase ?? '—'}</td><td>{event.tool ?? event.label ?? '—'}</td><td>{event.status ?? '—'}</td><td>{event.message ?? '—'}</td></tr>)}
  </tbody></table></div>;
}
