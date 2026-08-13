import { useEffect, useState } from 'react';
import { ControlPlaneApiError, controlPlaneClient, toApiError } from '../../../api/controlPlaneClient';
import type { UiSnapshotResponse } from '../../../api/types';
import { formatUiTreeContent, isStructuredXmlTree } from '../replay/uiTreeFormat';

function UiTreeContent({ content }: { content: string }) {
  const formatted = formatUiTreeContent(content);
  const structured = isStructuredXmlTree(content);
  return <pre aria-label={structured ? 'Structured XML UI Tree' : undefined}>{formatted}</pre>;
}

export function UiSnapshotView({ requestId, revision }: { requestId: string | null; revision: number }) {
  const [state, setState] = useState<'empty' | 'loading' | 'available' | 'unavailable' | 'oversized' | 'error'>('empty');
  const [snapshot, setSnapshot] = useState<UiSnapshotResponse | null>(null);
  const [message, setMessage] = useState('');
  useEffect(() => {
    setSnapshot(null);
    if (!requestId || revision <= 0) { setState('empty'); return; }
    const controller = new AbortController();
    setState('loading');
    void controlPlaneClient.uiSnapshot(requestId, controller.signal).then((data) => { setSnapshot(data); setState('available'); }).catch((error) => {
      if (controller.signal.aborted) return;
      setMessage(toApiError(error).message);
      setState(error instanceof ControlPlaneApiError && error.status === 413 ? 'oversized' : error instanceof ControlPlaneApiError && error.status === 404 ? 'unavailable' : 'error');
    });
    return () => controller.abort();
  }, [requestId, revision]);
  if (state === 'available' && snapshot) return <div className="ui-snapshot"><div className="evidence-meta">Revision {snapshot.revision} · {snapshot.format}{snapshot.stepId ? ` · ${snapshot.stepId}` : ''}</div><UiTreeContent content={snapshot.content} /></div>;
  const copy = {
    empty: ['UI Tree not yet captured', 'The latest normalized UI snapshot will appear after evidence capture.'],
    loading: ['Loading UI Tree', 'Reading the latest snapshot revision…'],
    unavailable: ['UI Tree unavailable', message || 'The captured snapshot cannot be read.'],
    oversized: ['UI Tree is too large to display', message || 'Inspect the persisted artifact outside Control Plane.'],
    error: ['UI Tree failed to load', message || 'Retry when a newer revision is available.'],
  }[state as Exclude<typeof state, 'available'>];
  return <div className={`evidence-message evidence-message--${state}`} role={state === 'error' ? 'alert' : 'status'}><strong>{copy[0]}</strong><p>{copy[1]}</p></div>;
}
