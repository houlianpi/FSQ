import { useRef, useState } from 'react';
import { ArrowRight, Bot, CheckCircle2, FileCheck2, FolderOpen, Gauge, ListChecks, Play, Settings2, Sparkles, X } from 'lucide-react';
import type { ControlPlanePageId } from '../../app/shell/navigation';
import './overview.css';

interface OverviewPageProps {
  onNavigate: (page: ControlPlanePageId) => void;
}

const workflow = [
  ['Define', 'Choose a workspace, target, and task source.'],
  ['Plan', 'FSQ turns intent into observable test steps.'],
  ['Operate', 'Platform capabilities act on the selected application.'],
  ['Capture', 'Screens, UI state, logs, and artifacts record the run.'],
  ['Verify', 'Evidence supports a clear pass, fail, or inconclusive result.'],
] as const;

export function OverviewPage({ onNavigate }: OverviewPageProps) {
  const [explanationOpen, setExplanationOpen] = useState(false);
  const explanationTrigger = useRef<HTMLButtonElement>(null);

  const closeExplanation = () => {
    setExplanationOpen(false);
    requestAnimationFrame(() => explanationTrigger.current?.focus());
  };

  return <div className="cp-overview">
    <section className="cp-overview-intro" aria-labelledby="start-run-heading">
      <div>
        <span className="cp-kicker"><Gauge aria-hidden="true" />Test control center</span>
        <h1 id="start-run-heading">Start a run</h1>
        <p>Move from an intent or authored case to observable application evidence.</p>
      </div>
      <button ref={explanationTrigger} className="button" type="button" onClick={() => setExplanationOpen(true)}>
        <Sparkles aria-hidden="true" />How FSQ works
      </button>
    </section>

    <div className="cp-run-entry-grid">
      <article className="cp-run-entry cp-run-entry--dynamic">
        <span className="cp-run-entry-icon"><Bot aria-hidden="true" /></span>
        <div><p>Dynamic</p><h2>Explore from a goal</h2><span>Describe the outcome. FSQ plans and operates while preserving evidence at every step.</span></div>
        <button className="button button--primary" type="button" onClick={() => onNavigate('devices')}>Open Dynamic <ArrowRight aria-hidden="true" /></button>
      </article>
      <article className="cp-run-entry cp-run-entry--strict">
        <span className="cp-run-entry-icon"><FileCheck2 aria-hidden="true" /></span>
        <div><p>Strict</p><h2>Replay an authored case</h2><span>Run deterministic FSQ steps against a selected target with bounded lifecycle rules.</span></div>
        <button className="button" type="button" onClick={() => onNavigate('devices')}>Open Strict <ArrowRight aria-hidden="true" /></button>
      </article>
    </div>

    <section className="cp-workflow" aria-labelledby="workflow-heading">
      <div className="cp-section-heading"><div><span className="cp-kicker"><ListChecks aria-hidden="true" />Execution model</span><h2 id="workflow-heading">One workflow, visible end to end</h2></div></div>
      <ol>{workflow.map(([title, description], index) => <li key={title}><span>{String(index + 1).padStart(2, '0')}</span><div><strong>{title}</strong><small>{description}</small></div></li>)}</ol>
    </section>

    <div className="cp-overview-lower">
      <section className="cp-sample-section" aria-labelledby="recent-heading">
        <div className="cp-section-heading"><div><span className="cp-kicker"><Play aria-hidden="true" />Illustrative</span><h2 id="recent-heading">Recent activity</h2></div></div>
        <div className="cp-activity-sample"><span className="cp-status-dot cp-status-dot--success" /><div><strong>Checkout smoke path</strong><small>Strict · Android · 18 commands</small></div><span>Passed</span></div>
        <div className="cp-activity-sample"><span className="cp-status-dot" /><div><strong>Search and save</strong><small>Dynamic · Web · evidence captured</small></div><span>Inconclusive</span></div>
      </section>
      <section className="cp-sample-section" aria-labelledby="environment-heading">
        <div className="cp-section-heading"><div><span className="cp-kicker"><Settings2 aria-hidden="true" />Illustrative</span><h2 id="environment-heading">Environment</h2></div></div>
        <dl className="cp-environment-sample"><div><dt>Workspace</dt><dd>Not selected</dd></div><div><dt>Provider</dt><dd>Configure locally</dd></div><div><dt>Targets</dt><dd>4 platforms</dd></div></dl>
        <div className="cp-overview-actions"><button className="button" type="button" onClick={() => onNavigate('workspace')}><FolderOpen aria-hidden="true" />Open workspace</button><button className="button" type="button" onClick={() => onNavigate('config')}><Settings2 aria-hidden="true" />Manage config</button></div>
      </section>
    </div>

    {explanationOpen && <div className="cp-dialog-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) closeExplanation(); }}>
      <section className="cp-overview-dialog" role="dialog" aria-modal="true" aria-labelledby="how-fsq-heading">
        <button className="cp-icon-button" type="button" aria-label="Close explanation" onClick={closeExplanation}><X aria-hidden="true" /></button>
        <CheckCircle2 aria-hidden="true" className="cp-overview-dialog-mark" />
        <h2 id="how-fsq-heading">Evidence before conclusions</h2>
        <p>FSQ separates planning, application actions, captured observations, and verification so a run result can be inspected rather than merely asserted.</p>
        <button className="button button--primary" type="button" onClick={closeExplanation}>Got it</button>
      </section>
    </div>}
  </div>;
}