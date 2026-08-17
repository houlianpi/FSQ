import { useEffect, useMemo, useState } from 'react';
import { controlPlaneClient, toApiError } from '../../../api/controlPlaneClient';
import type { PlatformId, StepArtifact, StepArtifactsResponse } from '../../../api/types';
import { changedSegments, diffLines } from '../replay/uiDiff';
import { formatUiTreeContent, isStructuredXmlTree } from '../replay/uiTreeFormat';

interface Props {
  requestId: string;
  stepId: string;
  kind: 'screen' | 'ui-tree';
  platform: PlatformId;
}

function preferred(artifacts: StepArtifact[], phase: 'before' | 'after') {
  return artifacts.find((artifact) => artifact.phase === phase) ?? null;
}

function InlineLine({ before, after, side }: { before: string; after: string; side: 'before' | 'after' }) {
  const segments = changedSegments(before, after)[side];
  return <>{segments[0]}{segments[1] && <mark>{segments[1]}</mark>}{segments[2]}</>;
}

function UiTreePre({ content }: { content: string }) {
  const formatted = formatUiTreeContent(content);
  const structured = isStructuredXmlTree(content);
  return <pre aria-label={structured ? 'Structured XML UI Tree' : undefined}>{formatted}</pre>;
}

export function StepEvidenceView({ requestId, stepId, kind, platform }: Props) {
  const [state, setState] = useState<'loading' | 'available' | 'empty' | 'error'>('loading');
  const [payload, setPayload] = useState<StepArtifactsResponse | null>(null);
  const [message, setMessage] = useState('');
  useEffect(() => {
    const controller = new AbortController();
    setState('loading'); setPayload(null); setMessage('');
    void controlPlaneClient.stepArtifacts(requestId, stepId, controller.signal).then((data) => {
      setPayload(data); setState(data.available ? 'available' : 'empty');
    }).catch((error) => { if (!controller.signal.aborted) { setMessage(toApiError(error).message); setState('error'); } });
    return () => controller.abort();
  }, [requestId, stepId]);
  const artifacts = useMemo(() => payload?.artifacts ?? [], [payload]);
  if (state === 'loading') return <div className="evidence-message" role="status"><strong>Loading Action evidence</strong><p>Reading persisted Before and After artifacts…</p></div>;
  if (state === 'error') return <div className="evidence-message evidence-message--error" role="alert"><strong>Action evidence failed to load</strong><p>{message}</p></div>;
  const expectedKind = kind === 'screen' ? 'screenshot' : 'ui_snapshot';
  const matching = artifacts.filter((artifact) => artifact.kind === expectedKind);
  if (state === 'empty' || !matching.length) return <div className="evidence-message" role="status"><strong>{kind === 'screen' ? 'No screenshots for this Action' : 'No UI Tree for this Action'}</strong><p>The run remains valid; this Action did not capture that evidence kind.</p></div>;
  const before = preferred(matching, 'before');
  const after = preferred(matching, 'after');
  if (kind === 'screen') {
    const shown = [before, after].filter((item): item is StepArtifact => Boolean(item?.contentBase64));
    if (!shown.length) return <div className="evidence-message" role="alert"><strong>Action screenshots unavailable</strong><p>{matching.map((item) => item.error).filter(Boolean).join(' ')}</p></div>;
    return <div className={`step-screenshot-comparison${platform === 'android' ? ' step-screenshot-comparison--android' : ''}`}>
      {shown.map((artifact) => <figure key={artifact.phase} className="step-screenshot-card"><figcaption>{artifact.phase === 'before' ? 'Before' : 'After'}</figcaption><img src={`data:${artifact.mimeType};base64,${artifact.contentBase64}`} alt={`${artifact.phase} screenshot for selected Action`} /></figure>)}
    </div>;
  }
  if (!before?.content || !after?.content) {
    const only = before?.content ? before : after;
    return only?.content ? <div className="ui-snapshot"><div className="evidence-meta">{only.phase === 'before' ? 'Before' : 'After'} · selected Action</div><UiTreePre content={only.content} /></div> : <div className="evidence-message" role="alert"><strong>Action UI Tree unavailable</strong><p>{matching.map((item) => item.error).filter(Boolean).join(' ')}</p></div>;
  }
  const rows = diffLines(formatUiTreeContent(before.content), formatUiTreeContent(after.content));
  return <div className="ui-diff" aria-label="Before and After UI Tree diff">
    <div className="ui-diff-header"><strong>Before</strong><strong>After</strong></div>
    <div className="ui-diff-body">
      <div className="ui-diff-pane">{rows.map((row, index) => <div key={index} className={`ui-diff-row ui-diff-row--${row.kind}`}><span>{row.beforeNumber ?? ''}</span><code>{row.kind === 'changed' ? <InlineLine before={row.before} after={row.after} side="before" /> : row.before}</code></div>)}</div>
      <div className="ui-diff-pane">{rows.map((row, index) => <div key={index} className={`ui-diff-row ui-diff-row--${row.kind}`}><span>{row.afterNumber ?? ''}</span><code>{row.kind === 'changed' ? <InlineLine before={row.before} after={row.after} side="after" /> : row.after}</code></div>)}</div>
    </div>
  </div>;
}
