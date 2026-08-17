import { useEffect, useRef, useState } from 'react';
import { ControlPlaneApiError, controlPlaneClient, toApiError, validateRunSnapshot, type ControlPlaneClient } from '../../../api/controlPlaneClient';
import type { ApiErrorBody, RunSnapshot, TimelineEvent } from '../../../api/types';

const MAX_RECONNECTS = 3;
const POLL_INTERVAL_MS = 2000;

function mergeEvents(existing: TimelineEvent[], incoming: TimelineEvent[]): TimelineEvent[] {
  const bySequence = new Map(existing.map((event) => [event.sequence, event]));
  for (const event of incoming) bySequence.set(event.sequence, event);
  return [...bySequence.values()].sort((a, b) => a.sequence - b.sequence);
}

function mergeSnapshot(previous: RunSnapshot | null, incoming: RunSnapshot): RunSnapshot {
  return { ...incoming, events: mergeEvents(previous?.events ?? [], incoming.events ?? []) };
}

export interface RunStreamState {
  snapshot: RunSnapshot | null;
  connection: 'idle' | 'connecting' | 'live' | 'reconnecting' | 'polling' | 'ended';
  error: ApiErrorBody | null;
}

export function useRunStream(requestId: string | null, client: ControlPlaneClient = controlPlaneClient): RunStreamState {
  const [snapshot, setSnapshot] = useState<RunSnapshot | null>(null);
  const [connection, setConnection] = useState<RunStreamState['connection']>('idle');
  const [error, setError] = useState<ApiErrorBody | null>(null);
  const sequenceRef = useRef(0);
  const terminalRef = useRef(false);

  useEffect(() => {
    setSnapshot(null);
    sequenceRef.current = 0;
    terminalRef.current = false;
    setError(null);
    if (!requestId) { setConnection('idle'); return; }

    let disposed = false;
    let source: EventSource | null = null;
    let retryTimer: number | null = null;
    let pollTimer: number | null = null;
    let reconnects = 0;
    const controller = new AbortController();

    const endMissingRequest = (caught: unknown) => {
      if (!(caught instanceof ControlPlaneApiError) || caught.status !== 404) return false;
      terminalRef.current = true;
      source?.close();
      if (retryTimer !== null) window.clearTimeout(retryTimer);
      if (pollTimer !== null) window.clearTimeout(pollTimer);
      setConnection('ended');
      setError({
        code: 'run_ended',
        message: 'The prior live run is no longer available. The Control Plane server may have restarted.',
        action: 'Start a new run or reattach to the active run shown by the server.',
      });
      return true;
    };

    const accept = (incoming: RunSnapshot, ensureTerminalHydrated = false) => {
      if (disposed) return;
      const incomingSequence = Math.max(0, ...(incoming.events ?? []).map((event) => event.sequence));
      sequenceRef.current = Math.max(sequenceRef.current, incomingSequence);
      setSnapshot((previous) => mergeSnapshot(previous, incoming));
      if (incoming.terminal) {
        terminalRef.current = true;
        source?.close();
        setConnection('ended');
        if (ensureTerminalHydrated) {
          void client.runSnapshot(requestId, controller.signal).then((hydrated) => {
            if (!disposed) setSnapshot((previous) => mergeSnapshot(previous, hydrated));
          }).catch((caught) => {
            if (!disposed && !controller.signal.aborted && !endMissingRequest(caught)) setError(toApiError(caught));
          });
        }
      }
    };

    const poll = async () => {
      if (disposed) return;
      setConnection('polling');
      try {
        const incoming = await client.runSnapshot(requestId, controller.signal);
        accept(incoming);
        setError(null);
        if (!incoming.terminal) pollTimer = window.setTimeout(poll, POLL_INTERVAL_MS);
      } catch (caught) {
        if (disposed || controller.signal.aborted) return;
        if (endMissingRequest(caught)) return;
        setError(toApiError(caught));
        pollTimer = window.setTimeout(poll, POLL_INTERVAL_MS);
      }
    };

    const connect = () => {
      if (disposed) return;
      setConnection(reconnects ? 'reconnecting' : 'connecting');
      source = new EventSource(client.streamUrl(requestId, sequenceRef.current));
      source.addEventListener('open', () => { if (!disposed) { setConnection('live'); setError(null); } });
      source.addEventListener('snapshot', (event) => {
        try { accept(validateRunSnapshot(JSON.parse((event as MessageEvent<string>).data), 'run stream'), true); }
        catch { setError({ code: 'invalid_stream', message: 'A live update could not be read.', action: 'Snapshot polling will recover current state.' }); }
      });
      source.onerror = () => {
        source?.close();
        if (disposed || terminalRef.current) return;
        reconnects += 1;
        if (reconnects <= MAX_RECONNECTS) {
          setConnection('reconnecting');
          retryTimer = window.setTimeout(connect, 400 * (2 ** (reconnects - 1)));
        } else {
          void poll();
        }
      };
    };

    void client.runSnapshot(requestId, controller.signal).then(accept).catch((caught) => {
      if (!controller.signal.aborted && !endMissingRequest(caught)) setError(toApiError(caught));
    });
    if ('EventSource' in window) connect(); else void poll();

    return () => {
      disposed = true;
      controller.abort();
      source?.close();
      if (retryTimer !== null) window.clearTimeout(retryTimer);
      if (pollTimer !== null) window.clearTimeout(pollTimer);
    };
  }, [client, requestId]);

  return { snapshot, connection, error };
}
