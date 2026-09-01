import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { WorkspaceRegistryEntry } from '../../api/types';
import { OverviewPage } from './OverviewPage';

const workspace: WorkspaceRegistryEntry = {
  name: 'TodoMVC Release', rootPath: '/private/path', status: 'partial', message: 'One platform needs attention.',
  platforms: [
    { platform: 'web', configPath: '/private/web.yaml', status: 'available', message: 'Ready.' },
    { platform: 'android', configPath: '/private/android.yaml', status: 'unavailable', message: 'Unavailable.' },
  ],
};

function renderOverview(overrides: Partial<React.ComponentProps<typeof OverviewPage>> = {}) {
  const props: React.ComponentProps<typeof OverviewPage> = {
    workspaces: [], selectedWorkspace: null, registryStatus: 'ready', provider: { status: 'unconfigured' }, onNavigate: vi.fn(), onCreateWorkspace: vi.fn(), onSelectWorkspace: vi.fn(), onClearWorkspace: vi.fn(), onOpenWorkspace: vi.fn(), onConfigureWorkspace: vi.fn(), onRetryWorkspaces: vi.fn(), onRetryProvider: vi.fn(), ...overrides,
  };
  render(<OverviewPage {...props} />);
  return props;
}

it('renders only the global AI region and the three-step Workspace workflow', () => {
  renderOverview();
  expect(screen.getByRole('heading', { name: 'AI Provider' })).toBeVisible();
  expect(screen.getByText((_, element) => element?.tagName === 'P' && element.textContent === 'Loaded from ~/.fsq and shared by every Workspace.')).toBeVisible();
  const flow = screen.getByRole('list', { name: 'Test this Workspace' });
  expect(within(flow).getAllByRole('listitem')).toHaveLength(3);
  expect(within(flow).getByRole('heading', { name: 'Workspace and platform' })).toBeVisible();
  expect(within(flow).getByRole('heading', { name: 'Create or run a Case' })).toBeVisible();
  expect(within(flow).getByRole('heading', { name: 'Inspect the latest Run' })).toBeVisible();
  expect(screen.queryByText('Check readiness')).not.toBeInTheDocument();
  expect(screen.queryByText(/of 6 complete/i)).not.toBeInTheDocument();
});

it('shows safe Provider identity without secret-bearing Config fields and opens Config', async () => {
  const user = userEvent.setup();
  const props = renderOverview({ provider: { status: 'configured', provider: 'Azure OpenAI', modelName: 'gpt-5.5' } });
  expect(screen.getByText('Azure OpenAI')).toBeVisible();
  expect(screen.getByText('gpt-5.5')).toBeVisible();
  expect(screen.queryByText(/api key|endpoint|token/i)).not.toBeInTheDocument();
  await user.click(screen.getByRole('button', { name: 'Manage Provider' }));
  expect(props.onNavigate).toHaveBeenCalledWith('config');
});

it('keeps Provider failure separate and retryable without changing Workspace truth', async () => {
  const user = userEvent.setup();
  const error = { code: 'config_unavailable', message: 'Provider configuration unavailable.', action: 'Open the local Control Plane.' };
  const props = renderOverview({ workspaces: [workspace], selectedWorkspace: workspace, provider: { status: 'error', error } });
  expect(screen.getByRole('alert')).toHaveTextContent(error.message);
  expect(screen.getByRole('heading', { name: 'TodoMVC Release' })).toBeVisible();
  expect(screen.queryByText('Ready')).not.toBeInTheDocument();
  await user.click(screen.getByRole('button', { name: /Retry/ }));
  expect(props.onRetryProvider).toHaveBeenCalledOnce();
});

it('separates opening the Workspace from configuring it', async () => {
  const user = userEvent.setup();
  const props = renderOverview({ workspaces: [workspace], selectedWorkspace: workspace });

  await user.click(screen.getByRole('button', { name: 'Open Workspace' }));
  await user.click(screen.getByRole('button', { name: 'Configure Workspace' }));

  expect(props.onOpenWorkspace).toHaveBeenCalledWith(workspace.name);
  expect(props.onConfigureWorkspace).toHaveBeenCalledWith(workspace.name);
});

it('shows safe Workspace identity, omits a Case status, and marks Runs as coming soon', async () => {
  const user = userEvent.setup();
  const props = renderOverview({ workspaces: [workspace], selectedWorkspace: workspace });
  expect(screen.getByRole('heading', { name: 'TodoMVC Release' })).toBeVisible();
  expect(screen.getByText('web')).toBeVisible();
  expect(screen.getByText('android')).toBeVisible();
  expect(screen.queryByText('Not evaluated')).not.toBeInTheDocument();
  expect(screen.queryByText('No Run yet')).not.toBeInTheDocument();
  expect(screen.getByText('Coming soon')).toBeVisible();
  expect(screen.queryByText('/private/path')).not.toBeInTheDocument();
  expect(screen.queryByText('/private/web.yaml')).not.toBeInTheDocument();
  await user.click(screen.getByRole('button', { name: 'Open Devices' }));
  expect(props.onNavigate).toHaveBeenNthCalledWith(1, 'devices');
  expect(screen.queryByRole('button', { name: 'View in Devices' })).not.toBeInTheDocument();
});

it('clears the current Overview selection and returns to the Workspace chooser', async () => {
  const user = userEvent.setup();
  const props = renderOverview({ workspaces: [workspace], selectedWorkspace: workspace });

  await user.click(screen.getByRole('button', { name: 'Back to Workspaces' }));

  expect(props.onClearWorkspace).toHaveBeenCalledOnce();
});

it('presents platform availability as one accessible status summary', () => {
  renderOverview({ workspaces: [workspace], selectedWorkspace: workspace });

  const platforms = screen.getByLabelText('Configured platforms');
  expect(within(platforms).getByText('web').parentElement).toHaveTextContent('webavailable');
  expect(within(platforms).getByText('android').parentElement).toHaveTextContent('androidunavailable');
});

it('distinguishes missing Workspace from an unavailable-only platform', () => {
  const { rerender } = render(<OverviewPage workspaces={[]} selectedWorkspace={null} registryStatus="ready" provider={{ status: 'unconfigured' }} onNavigate={vi.fn()} onCreateWorkspace={vi.fn()} onSelectWorkspace={vi.fn()} onClearWorkspace={vi.fn()} onOpenWorkspace={vi.fn()} onConfigureWorkspace={vi.fn()} onRetryWorkspaces={vi.fn()} onRetryProvider={vi.fn()} />);
  expect(screen.getByRole('button', { name: 'Open Devices' })).toHaveAccessibleDescription('Select an available Workspace before continuing.');
  const unavailableOnly = { ...workspace, platforms: [{ platform: 'android' as const, configPath: '/private/android.yaml', status: 'unavailable' as const, message: 'Unavailable.' }] };
  rerender(<OverviewPage workspaces={[unavailableOnly]} selectedWorkspace={unavailableOnly} registryStatus="ready" provider={{ status: 'unconfigured' }} onNavigate={vi.fn()} onCreateWorkspace={vi.fn()} onSelectWorkspace={vi.fn()} onClearWorkspace={vi.fn()} onOpenWorkspace={vi.fn()} onConfigureWorkspace={vi.fn()} onRetryWorkspaces={vi.fn()} onRetryProvider={vi.fn()} />);
  expect(screen.getByText('Needs attention')).toBeVisible();
  expect(screen.getByRole('button', { name: 'Open Devices' })).toHaveAccessibleDescription('Initialize or repair a platform in Workspace until at least one platform is available.');
});

it('does not expose stale Workspace identity while registry is loading or failed', async () => {
  const retry = vi.fn();
  const { rerender } = render(<OverviewPage workspaces={[workspace]} selectedWorkspace={workspace} registryStatus="loading" provider={{ status: 'loading' }} onNavigate={vi.fn()} onCreateWorkspace={vi.fn()} onSelectWorkspace={vi.fn()} onClearWorkspace={vi.fn()} onOpenWorkspace={vi.fn()} onConfigureWorkspace={vi.fn()} onRetryWorkspaces={retry} onRetryProvider={vi.fn()} />);
  expect(screen.getByRole('heading', { name: 'No Workspace selected' })).toBeVisible();
  expect(screen.queryByText('TodoMVC Release')).not.toBeInTheDocument();
  rerender(<OverviewPage workspaces={[workspace]} selectedWorkspace={workspace} registryStatus="error" registryError="Registry unavailable." provider={{ status: 'unconfigured' }} onNavigate={vi.fn()} onCreateWorkspace={vi.fn()} onSelectWorkspace={vi.fn()} onClearWorkspace={vi.fn()} onOpenWorkspace={vi.fn()} onConfigureWorkspace={vi.fn()} onRetryWorkspaces={retry} onRetryProvider={vi.fn()} />);
  expect(screen.getByRole('alert')).toHaveTextContent('Registry unavailable.');
  expect(screen.queryByText('TodoMVC Release')).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: /Retry/ }));
  expect(retry).toHaveBeenCalledOnce();
});
