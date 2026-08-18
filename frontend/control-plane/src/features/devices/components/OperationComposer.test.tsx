import { createRef } from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ReadinessResponse } from '../../../api/types';
import { OperationComposer } from './OperationComposer';

const ready: ReadinessResponse = {
  workspaceName: 'test', platformId: 'web',
  workspace: { status: 'ready', message: 'Workspace ready', action: '' },
  platform: { status: 'ready', message: 'Platform ready', action: '' },
  provider: { status: 'ready', message: 'Provider ready', action: '' },
  target: { status: 'ready', message: 'Target ready', action: '' },
  strict: { status: 'ready', message: 'Strict ready', action: '' },
};

it('shows strict case facts without claiming human review', async () => {
  const onModeChange = vi.fn();
  render(<OperationComposer mode="strict" goal="" casePath="flow.fsq.yaml" cases={[{
    path: 'flow.fsq.yaml', id: 'flow', name: 'Create flow', platform: 'web', commandCount: 6,
    requiresAiAssertion: true, validationStatus: 'validated', selectable: true, diagnostics: [],
  }]} casesState="ready" readiness={ready} discoveryLoading={false} canStart primaryInputRef={createRef()} onModeChange={onModeChange} onGoalChange={vi.fn()} onCaseChange={vi.fn()} onStart={vi.fn()} />);
  expect(screen.getByText('validated')).toBeInTheDocument();
  expect(screen.getByText('Provider required')).toBeInTheDocument();
  expect(screen.queryByText(/reviewed/i)).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole('radio', { name: 'Explore' }));
  expect(onModeChange).toHaveBeenCalledWith('explore');
});

it('shows an empty Strict Replay source while readiness remains available', () => {
  render(<OperationComposer mode="strict" goal="" casePath="" cases={[]} casesState="ready" readiness={ready} discoveryLoading={false} canStart={false} primaryInputRef={createRef()} onModeChange={vi.fn()} onGoalChange={vi.fn()} onCaseChange={vi.fn()} onStart={vi.fn()} />);

  expect(screen.getByRole('option', { name: 'No validated cases available' })).toBeInTheDocument();
  expect(screen.getByText('Workspace ready')).toBeInTheDocument();
  expect(screen.getByText('Strict ready')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Start strict replay' })).toBeDisabled();
});
