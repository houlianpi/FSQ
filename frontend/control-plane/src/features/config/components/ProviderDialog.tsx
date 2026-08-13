import { useEffect, useRef, useState } from 'react';
import type { ApiErrorBody, GitHubDeviceFlowResponse } from '../../../api/types';
import { DialogFrame } from './DialogFrame';

interface ProviderDialogProps {
  initialGithubModel: string;
  deviceFlow: GitHubDeviceFlowResponse | null;
  deviceFlowPending: 'starting' | 'waiting' | 'cancelling' | null;
  deviceFlowError: ApiErrorBody | null;
  onSelectAzure: () => void;
  onStartGithub: (modelName: string) => Promise<unknown>;
  onCancelAuthentication: () => Promise<void>;
  onClose: () => void;
}

export function ProviderDialog(props: ProviderDialogProps) {
  const [step, setStep] = useState<'choice' | 'github'>('choice');
  const [modelName, setModelName] = useState(props.initialGithubModel);
  const [copied, setCopied] = useState(false);
  const modelRef = useRef<HTMLInputElement>(null);
  const flow = props.deviceFlow;
  const waiting = flow?.status === 'waiting';
  const failed = flow && ['failed', 'expired'].includes(flow.status);

  useEffect(() => {
    if (step === 'github' && !flow && props.deviceFlowPending !== 'starting') modelRef.current?.focus();
  }, [flow, props.deviceFlowPending, step]);

  const copyCode = async () => {
    if (!flow) return;
    await navigator.clipboard?.writeText(flow.userCode);
    setCopied(true);
  };

  if (step === 'choice') return <DialogFrame title="Choose model provider" onClose={props.onClose}>
    <p className="config-dialog-intro">One provider is active at a time. A replacement takes effect only after it is saved.</p>
    <div className="provider-options">
      <button type="button" className="provider-option" data-dialog-initial onClick={props.onSelectAzure}>
        <strong>Azure GPT</strong><span>Use an Azure OpenAI-compatible endpoint and API key.</span>
      </button>
      <button type="button" className="provider-option" onClick={() => setStep('github')}>
        <strong>GitHub Copilot GPT</strong><span>Authenticate this computer through GitHub device flow.</span>
      </button>
    </div>
    <div className="config-dialog-actions"><button className="button" type="button" onClick={props.onClose}>Cancel</button></div>
  </DialogFrame>;

  if (props.deviceFlowPending === 'starting' && !flow) return <DialogFrame title="Connect GitHub Copilot GPT" onClose={props.onClose}>
    <p className="config-status" role="status">Requesting a GitHub device code...</p>
    <div className="config-dialog-actions"><button className="button" type="button" onClick={props.onClose}>Cancel</button></div>
  </DialogFrame>;

  if (flow && (waiting || failed)) return <DialogFrame title="Connect GitHub Copilot GPT" onClose={props.onClose}>
    {waiting ? <>
      <p className="config-status" role="status">Waiting for authorization in GitHub.</p>
      <a className="verification-link" href={flow.verificationUri} target="_blank" rel="noreferrer">Open GitHub verification</a>
      <div className="device-code-block">
        <span>User code</span><strong className="mono">{flow.userCode}</strong>
        <button className="config-icon-button" type="button" aria-label="Copy user code" title="Copy user code" onClick={() => void copyCode()}>⧉</button>
      </div>
      {copied && <p className="field-help" role="status">Code copied.</p>}
      <p className="field-help">Expires <time dateTime={flow.expiresAt}>{new Date(flow.expiresAt).toLocaleString()}</time></p>
    </> : <div className="config-error" role="alert"><strong>{flow.message ?? 'GitHub authentication failed.'}</strong><span>Request a new device code and try again.</span></div>}
    <div className="config-dialog-actions">
      {failed && <button className="button button--primary" type="button" onClick={() => void props.onStartGithub(modelName)}>Retry</button>}
      <button className="button" type="button" disabled={props.deviceFlowPending === 'cancelling'} onClick={() => void props.onCancelAuthentication()}>
        {waiting ? 'Cancel authentication' : 'Cancel'}
      </button>
    </div>
  </DialogFrame>;

  return <DialogFrame title="GitHub Copilot GPT" onClose={props.onClose}>
    <form onSubmit={(event) => { event.preventDefault(); void props.onStartGithub(modelName); }}>
      <div className="config-field">
        <label htmlFor="github-model-name">Model name</label>
        <input id="github-model-name" ref={modelRef} data-dialog-initial required value={modelName} onChange={(event) => setModelName(event.target.value)} autoComplete="off" />
        <small>Use a GPT 5 or later model available through your Copilot plan.</small>
      </div>
      {props.deviceFlowError && <div className="config-error" role="alert"><strong>{props.deviceFlowError.message}</strong><span>{props.deviceFlowError.action}</span></div>}
      <div className="config-dialog-actions">
        <button className="button" type="button" onClick={() => setStep('choice')}>Back</button>
        <button className="button button--primary" type="submit" disabled={!modelName.trim()}>Continue</button>
      </div>
    </form>
  </DialogFrame>;
}