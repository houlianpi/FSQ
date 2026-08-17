import { useRef } from 'react';
import type { ControlPlanePageId } from '../../app/shell/navigation';
import './overview.css';

interface OverviewPageProps {
  onNavigate: (page: ControlPlanePageId) => void;
}

const workflow = [
  ['Explore', 'Turn a human goal into key actions.'],
  ['Capture', 'Record screenshots, UI trees, and tool facts.'],
  ['Verify', 'Judge the goal from evidence, not self-report.'],
  ['Save Case', 'Review actual successful actions as YAML.'],
  ['Replay', 'Run deterministically for regression.'],
] as const;

export function OverviewPage({ onNavigate }: OverviewPageProps) {
  const workflowRef = useRef<HTMLDivElement>(null);
  const showWorkflow = () => workflowRef.current?.scrollIntoView?.({
    behavior: window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth',
    block: 'center',
  });

  return <div className="cp-overview">
    <section className="cp-overview-card cp-overview-start" aria-labelledby="start-run-heading">
      <div className="cp-overview-card-head">
        <div className="cp-overview-start-copy">
          <h1 id="start-run-heading">Start a run</h1>
          <p>Start with the core loop, follow a guided tutorial, or launch a task on one of your connected devices.</p>
        </div>
        <button className="button" type="button" onClick={showWorkflow}>How FSQ works</button>
      </div>
      <div className="cp-overview-card-body">
        <div className="cp-launch-grid">
          <button className="cp-launch-card" type="button" onClick={() => onNavigate('devices')}>
            <span className="cp-launch-number">01 / DYNAMIC LOOP</span>
            <h2>Explore with AI</h2>
            <p>Describe a user-visible goal. FSQ plans, operates your app, captures every step, verifies the result, and drafts a replayable case.</p>
            <span className="cp-launch-footer"><span className="cp-tag cp-tag--accent">Uses configured LLM</span><span className="cp-launch-arrow">→</span></span>
          </button>
          <button className="cp-launch-card" type="button" onClick={() => onNavigate('devices')}>
            <span className="cp-launch-number">02 / STRICT LOOP</span>
            <h2>Replay a Case</h2>
            <p>Select a reviewed YAML case. FSQ executes authored commands exactly and produces fresh evidence for regression testing.</p>
            <span className="cp-launch-footer"><span className="cp-tag">No planning LLM</span><span className="cp-launch-arrow">→</span></span>
          </button>
        </div>
      </div>
    </section>

    <section ref={workflowRef} className="cp-overview-card cp-loop-strip" aria-label="FSQ workflow">
      {workflow.map(([title, description], index) => <div className="cp-loop-step" key={title}>
        <span className="mono">{String(index + 1).padStart(2, '0')}</span><strong>{title}</strong><small>{description}</small>
      </div>)}
    </section>

    <div className="cp-dashboard-grid">
      <section className="cp-overview-card" aria-labelledby="recent-heading">
        <div className="cp-overview-card-head">
          <div><h2 id="recent-heading">Recent activity</h2><p>Evidence from this workspace</p></div>
          <button className="button cp-button-small" type="button" onClick={() => onNavigate('workspace')}>Open workspace</button>
        </div>
        <div className="cp-overview-card-body cp-activity-list">
          <button className="cp-activity-row" type="button" onClick={() => onNavigate('devices')}><span><strong>Create project flow</strong><small>AI explore · Web · 4m ago</small></span><span className="cp-tag cp-tag--success">success</span></button>
          <button className="cp-activity-row" type="button" onClick={() => onNavigate('devices')}><span><strong>Checkout smoke</strong><small>Strict replay · Web · 38m ago</small></span><span className="cp-tag cp-tag--failed">failed</span></button>
          <button className="cp-activity-row" type="button" onClick={() => onNavigate('devices')}><span><strong>Settings profile</strong><small>AI explore · macOS · yesterday</small></span><span className="cp-tag cp-tag--warning">inconclusive</span></button>
        </div>
      </section>
      <section className="cp-overview-card" aria-labelledby="environment-heading">
        <div className="cp-overview-card-head">
          <div><h2 id="environment-heading">Environment</h2><p>Ready to run</p></div>
          <span className="cp-tag cp-tag--success">3 / 3</span>
        </div>
        <div className="cp-overview-card-body cp-health-list">
          <div className="cp-health-row"><span className="cp-dot cp-dot--success" /><span><strong>Provider</strong><small>GitHub Copilot · authenticated</small></span><span className="cp-tag cp-tag--success">ready</span></div>
          <div className="cp-health-row"><span className="cp-dot cp-dot--success" /><span><strong>Platform</strong><small>Web · Playwright · Chrome</small></span><span className="cp-tag cp-tag--success">ready</span></div>
          <div className="cp-health-row"><span className="cp-dot cp-dot--success" /><span><strong>Workspace</strong><small>Cases and evidence writable</small></span><span className="cp-tag cp-tag--success">ready</span></div>
          <button className="button cp-button-small cp-manage-config" type="button" onClick={() => onNavigate('config')}>Manage config</button>
        </div>
      </section>
    </div>
  </div>;
}