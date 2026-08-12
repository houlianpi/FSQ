import type { RefObject } from 'react';
import type { CaseRecord, ReadinessResponse, RequestResource, RunMode } from '../../../api/types';
import { PreflightStatus } from './PreflightStatus';

interface OperationComposerProps {
  mode: RunMode;
  goal: string;
  casePath: string;
  cases: CaseRecord[];
  casesState: RequestResource<unknown>['state'];
  readiness: ReadinessResponse | null;
  discoveryLoading: boolean;
  canStart: boolean;
  errorMessage?: string;
  errorAction?: string;
  primaryInputRef: RefObject<HTMLTextAreaElement | HTMLSelectElement | null>;
  onModeChange: (mode: RunMode) => void;
  onGoalChange: (goal: string) => void;
  onCaseChange: (path: string) => void;
  onStart: () => void;
}

export function OperationComposer(props: OperationComposerProps) {
  const selectedCase = props.cases.find((item) => item.path === props.casePath);
  const selectableCases = props.cases.filter((item) => item.selectable);
  return <div className="operation-composer">
    <div className="mode-switch" role="radiogroup" aria-label="Operation mode">
      <button type="button" role="radio" aria-checked={props.mode === 'explore'} className={props.mode === 'explore' ? 'active' : ''} onClick={() => props.onModeChange('explore')}>Explore</button>
      <button type="button" role="radio" aria-checked={props.mode === 'strict'} className={props.mode === 'strict' ? 'active' : ''} onClick={() => props.onModeChange('strict')}>Strict Replay</button>
    </div>
    {props.mode === 'explore' ? <div className="source-pane">
      <label className="field-label" htmlFor="explore-goal">What should FSQ prove?</label>
      <textarea ref={props.primaryInputRef as RefObject<HTMLTextAreaElement>} id="explore-goal" rows={8} value={props.goal} onChange={(event) => props.onGoalChange(event.target.value)} placeholder="Describe the outcome FSQ should verify…" />
      <p className="field-help">FSQ uses the configured model to plan, operate, capture evidence, and verify this goal.</p>
    </div> : <div className="source-pane">
      <label className="field-label" htmlFor="strict-case">Validated case</label>
      <select ref={props.primaryInputRef as RefObject<HTMLSelectElement>} id="strict-case" value={props.casePath} onChange={(event) => props.onCaseChange(event.target.value)} disabled={props.casesState === 'loading'}>
        <option value="">{props.casesState === 'loading' ? 'Discovering cases…' : selectableCases.length ? 'Select a case' : 'No validated cases available'}</option>
        {selectableCases.map((item) => <option key={item.path} value={item.path}>{item.name} · {item.commandCount} commands</option>)}
      </select>
      {selectedCase && <dl className="case-summary">
        <div><dt>Path</dt><dd>{selectedCase.path}</dd></div><div><dt>Platform</dt><dd>{selectedCase.platform ?? 'Unknown'}</dd></div>
        <div><dt>Commands</dt><dd>{selectedCase.commandCount}</dd></div><div><dt>Validation</dt><dd>{selectedCase.validationStatus}</dd></div>
        <div><dt>AI assertion</dt><dd>{selectedCase.requiresAiAssertion ? 'Provider required' : 'Not required'}</dd></div>
      </dl>}
      {props.cases.length > selectableCases.length && <p className="field-help">{props.cases.length - selectableCases.length} invalid or platform-mismatched case(s) are unavailable.</p>}
    </div>}
    <PreflightStatus mode={props.mode} workspace={props.readiness?.workspace} provider={props.readiness?.provider} target={props.readiness?.target} strict={props.readiness?.strict} requiresProvider={selectedCase?.requiresAiAssertion} loading={props.discoveryLoading} />
    {props.errorMessage && <div className="inline-error" role="alert"><strong>{props.errorMessage}</strong>{props.errorAction && <span>{props.errorAction}</span>}</div>}
    <button className="button button--primary start-button" type="button" disabled={!props.canStart} onClick={props.onStart}>{props.mode === 'explore' ? 'Start exploration' : 'Start strict replay'}</button>
  </div>;
}
