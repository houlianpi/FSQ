import { useEffect } from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { controlPlaneClient } from '../api/controlPlaneClient';
import { ControlPlaneApp } from './ControlPlaneApp';

vi.mock('../api/controlPlaneClient', () => ({
  controlPlaneClient: { workspaces: vi.fn().mockResolvedValue({ workspaces: [] }) },
  toApiError: vi.fn((error) => error),
}));

vi.mock('../features/devices/DevicesPage', () => ({
  DevicesPage: ({ workspaceRegistryReady, launchIntent, onLaunchIntentConsumed, renderShell }: { workspaceRegistryReady: boolean; launchIntent?: { id: number; mode: string; workspaceName: string; platform?: string; casePath?: string } | null; onLaunchIntentConsumed?: (id: number) => void; renderShell: (toolbar: React.ReactNode, content: React.ReactNode) => React.ReactNode }) =>
    renderShell(null, <div>Devices content<span>Registry {workspaceRegistryReady ? 'ready' : 'pending'}</span><span>{launchIntent ? `${launchIntent.mode}:${launchIntent.workspaceName}:${launchIntent.platform ?? ''}:${launchIntent.casePath ?? ''}` : 'No launch intent'}</span>{launchIntent && <button type="button" onClick={() => onLaunchIntentConsumed?.(launchIntent.id)}>Consume launch intent</button>}</div>),
}));
vi.mock('../features/config/ConfigPage', () => ({
  ConfigPage: ({ onDirtyChange }: { onDirtyChange?: (dirty: boolean) => void }) => <div>Config content<button type="button" onClick={() => onDirtyChange?.(true)}>Make draft dirty</button></div>,
}));
vi.mock('../features/overview/OverviewPage', () => ({
  OverviewPage: ({ onNavigate }: { onNavigate: (page: 'devices') => void }) => <div>Overview content<button type="button" onClick={() => onNavigate('devices')}>Start dynamic</button></div>,
}));
vi.mock('../features/workspace/WorkspacePage', () => ({
  WorkspaceTitlebar: ({ workspace, onConfigure }: { workspace: { name: string }; onConfigure: () => void }) => <div><h1 id="workspace-heading" tabIndex={-1}>{workspace.name}</h1><button type="button" onClick={onConfigure}>Configure workspace</button></div>,
  WorkspacePage: ({ createRequested, configurationOpen, selectedName, onDirtyChange, onCancelCreate, onCreated, onRegistryChanged, onPresentationChange, onRecordCase, onReplayCase }: { createRequested: boolean; configurationOpen: boolean; selectedName: string | null; onDirtyChange?: (dirty: boolean) => void; onCancelCreate: () => void; onCreated: (detail: object) => void; onRegistryChanged: () => void; onPresentationChange?: (presentation: 'default' | 'full-bleed') => void; onRecordCase?: () => void; onReplayCase?: (platform: 'web', casePath: string) => void }) => {
    useEffect(() => {
      onPresentationChange?.(selectedName && !createRequested && !configurationOpen ? 'full-bleed' : 'default');
    }, [configurationOpen, createRequested, onPresentationChange, selectedName]);
    return <div>
      {createRequested ? 'Create workspace content' : selectedName ? `Workspace ${selectedName}` : 'Workspace content'}
      <button type="button" onClick={() => onDirtyChange?.(true)}>Make workspace draft dirty</button>
      {createRequested && <button type="button" onClick={() => onCreated({ name: 'created', rootPath: 'C:\\projects\\created', status: 'available', message: 'Available.', platforms: [] })}>Complete creation</button>}
      {selectedName && !createRequested && <><button type="button" onClick={onRecordCase}>Record case from browser</button><button type="button" onClick={() => onReplayCase?.('web', 'flows/login.fsq.yaml')}>Replay case from browser</button></>}
      <button type="button" onClick={createRequested ? onCancelCreate : onRegistryChanged}>Cancel registry fixture</button>
    </div>;
  },
}));

beforeEach(() => vi.mocked(controlPlaneClient.workspaces).mockResolvedValue({ workspaces: [] }));
afterEach(() => vi.restoreAllMocks());

it('defaults to Overview and selects available pages through centralized navigation', async () => {
  const user = userEvent.setup();
  render(<ControlPlaneApp />);
  expect(screen.getByText('Overview content')).toBeVisible();

  await user.click(screen.getByRole('button', { name: 'Start dynamic' }));
  expect(screen.getByText('Devices content')).toBeVisible();

  await user.click(screen.getByRole('button', { name: 'Config' }));
  expect(screen.getByText('Config content')).toBeVisible();
  expect(screen.getByRole('button', { name: 'Config' })).toHaveAttribute('aria-current', 'page');

  await user.click(screen.getByRole('button', { name: 'Devices' }));
  expect(screen.getByText('Devices content')).toBeVisible();

  await user.click(screen.getByRole('button', { name: 'Create workspace' }));
  expect(screen.getByText('Create workspace content')).toBeVisible();
});

it('hands Workspace case actions to Devices and clears them for ordinary navigation', async () => {
  vi.mocked(controlPlaneClient.workspaces).mockResolvedValue({ workspaces: [
    { name: 'web-app', rootPath: 'C:\\projects\\web-app', status: 'available', message: 'Available.', platforms: [{ platform: 'web', configPath: 'web.yaml', status: 'available', message: 'Available.' }] },
  ] });
  const user = userEvent.setup();
  render(<ControlPlaneApp />);

  await user.click(await screen.findByRole('button', { name: /web-app/i }));
  await user.click(screen.getByRole('button', { name: 'Record case from browser' }));
  expect(screen.getByText('explore:web-app::')).toBeVisible();

  await user.click(screen.getByRole('button', { name: /web-app/i }));
  await user.click(screen.getByRole('button', { name: 'Replay case from browser' }));
  expect(screen.getByText('strict:web-app:web:flows/login.fsq.yaml')).toBeVisible();

  await user.click(screen.getByRole('button', { name: 'Consume launch intent' }));
  await user.click(screen.getByRole('button', { name: /web-app/i }));
  await user.click(screen.getByRole('button', { name: 'Devices' }));
  expect(screen.getByText('No launch intent')).toBeVisible();
});

it('does not authenticate retained workspace platforms after a registry refresh fails', async () => {
  vi.mocked(controlPlaneClient.workspaces)
    .mockResolvedValueOnce({ workspaces: [
      { name: 'web-app', rootPath: 'C:\\projects\\web-app', status: 'available', message: 'Available.', platforms: [{ platform: 'web', configPath: 'web.yaml', status: 'available', message: 'Available.' }] },
    ] })
    .mockRejectedValueOnce({ code: 'network_error', message: 'Registry unavailable.', action: 'Retry locally.' });
  const user = userEvent.setup();
  render(<ControlPlaneApp />);

  await user.click(await screen.findByRole('button', { name: /web-app/i }));
  await user.click(screen.getByRole('button', { name: 'Cancel registry fixture' }));
  await waitFor(() => expect(controlPlaneClient.workspaces).toHaveBeenCalledTimes(2));
  await user.click(screen.getByRole('button', { name: 'Replay case from browser' }));

  expect(screen.getByText('Registry pending')).toBeVisible();
  expect(screen.getByText('strict:web-app:web:flows/login.fsq.yaml')).toBeVisible();
});

it('keeps Config active when the user rejects dirty-draft navigation', async () => {
  const confirm = vi.spyOn(window, 'confirm').mockReturnValueOnce(false).mockReturnValueOnce(true);
  const user = userEvent.setup();
  render(<ControlPlaneApp />);
  await user.click(screen.getByRole('button', { name: 'Devices' }));
  await user.click(screen.getByRole('button', { name: 'Config' }));
  await user.click(screen.getByRole('button', { name: 'Make draft dirty' }));

  await user.click(screen.getByRole('button', { name: 'Devices' }));
  expect(screen.getByText('Config content')).toBeVisible();
  await user.click(screen.getByRole('button', { name: 'Devices' }));

  expect(confirm).toHaveBeenCalledTimes(2);
  expect(screen.getByText('Devices content')).toBeVisible();
});

it('keeps a dirty Workspace draft until page navigation is confirmed', async () => {
  const confirm = vi.spyOn(window, 'confirm').mockReturnValueOnce(false).mockReturnValueOnce(true);
  const user = userEvent.setup();
  render(<ControlPlaneApp />);
  await user.click(screen.getByRole('button', { name: 'Create workspace' }));
  await user.click(screen.getByRole('button', { name: 'Make workspace draft dirty' }));

  await user.click(screen.getByRole('button', { name: 'Devices' }));
  expect(screen.getByText('Create workspace content')).toBeVisible();
  await user.click(screen.getByRole('button', { name: 'Devices' }));

  expect(confirm).toHaveBeenCalledTimes(2);
  expect(screen.getByText('Devices content')).toBeVisible();
});

it('restores focus to the initiating control when workspace creation is cancelled', async () => {
  const user = userEvent.setup();
  render(<ControlPlaneApp />);
  const createWorkspace = screen.getByRole('button', { name: 'Create workspace' });

  await user.click(createWorkspace);
  await user.click(screen.getByRole('button', { name: 'Cancel registry fixture' }));

  await waitFor(() => expect(createWorkspace).toHaveFocus());
});

it('focuses the workspace heading after successful creation', async () => {
  vi.mocked(controlPlaneClient.workspaces)
    .mockResolvedValueOnce({ workspaces: [] })
    .mockResolvedValue({ workspaces: [
      { name: 'created', rootPath: 'C:\\projects\\created', status: 'available', message: 'Available.', platforms: [] },
    ] });
  const user = userEvent.setup();
  render(<ControlPlaneApp />);
  await user.click(screen.getByRole('button', { name: 'Create workspace' }));
  await user.click(screen.getByRole('button', { name: 'Complete creation' }));

  await waitFor(() => expect(screen.getByRole('heading', { name: 'created' })).toHaveFocus());
});

it('reopens narrow navigation before restoring create-cancel focus', async () => {
  const matchMedia = vi.spyOn(window, 'matchMedia').mockReturnValue({
    matches: true,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  } as unknown as MediaQueryList);
  const user = userEvent.setup();
  render(<ControlPlaneApp />);
  const openNavigation = screen.getByRole('button', { name: 'Open navigation' });
  await user.click(openNavigation);
  const createWorkspace = screen.getByRole('button', { name: 'Create workspace' });
  await user.click(createWorkspace);

  await user.click(screen.getByRole('button', { name: 'Cancel registry fixture' }));

  await waitFor(() => {
    expect(openNavigation).toHaveAttribute('aria-expanded', 'true');
    expect(createWorkspace).toHaveFocus();
  });
  matchMedia.mockRestore();
});

it('restores the previous workspace selection when creation is cancelled', async () => {
  vi.mocked(controlPlaneClient.workspaces).mockResolvedValue({ workspaces: [
    { name: 'mobile', rootPath: 'C:\\projects\\mobile', status: 'available', message: 'Workspace is available.', platforms: [{ platform: 'android', configPath: 'C:\\projects\\mobile\\.fsq\\config\\config.android.yaml', status: 'available', message: 'Platform is available.' }] },
  ] });
  const user = userEvent.setup();
  render(<ControlPlaneApp />);
  await user.click(await screen.findByRole('button', { name: /mobile/i }));
  await user.click(screen.getByRole('button', { name: 'Create workspace' }));

  await user.click(screen.getByRole('button', { name: 'Cancel registry fixture' }));

  expect(screen.getByText('Workspace mobile')).toBeVisible();
});

it('selects available registry entries and exposes unavailable entries only as repair guidance', async () => {
  vi.mocked(controlPlaneClient.workspaces).mockResolvedValue({ workspaces: [
    { name: 'mobile', rootPath: 'C:\\projects\\mobile', status: 'available', message: 'Workspace is available.', platforms: [{ platform: 'android', configPath: 'C:\\projects\\mobile\\.fsq\\config\\config.android.yaml', status: 'available', message: 'Platform is available.' }] },
    { name: 'broken', rootPath: 'C:\\projects\\broken', status: 'unavailable', message: 'Configuration is unavailable.', action: 'Repair config.yaml.', platforms: [{ platform: 'windows', configPath: 'C:\\projects\\broken\\.fsq\\config\\config.windows.yaml', status: 'unavailable', message: 'Platform is unavailable.', action: 'Repair config.windows.yaml.' }] },
  ] });
  const user = userEvent.setup();
  render(<ControlPlaneApp />);

  const broken = await screen.findByText('broken');
  const brokenEntry = broken.closest('[aria-disabled="true"]');
  expect(brokenEntry).toHaveAttribute('title', 'Configuration is unavailable. Repair config.yaml.');
  expect(brokenEntry).toHaveTextContent('windows unavailable');
  expect(brokenEntry).not.toHaveTextContent('C:\\projects');
  expect(screen.queryByRole('button', { name: /broken/i })).not.toBeInTheDocument();

  const mobile = screen.getByRole('button', { name: /mobile/i });
  expect(mobile).toHaveTextContent('android');
  expect(mobile).not.toHaveTextContent('available');
  expect(mobile).not.toHaveTextContent('C:\\projects');
  await user.click(mobile);
  expect(screen.getByText('Workspace mobile')).toBeVisible();
});

it('shows every configured platform and status for a partial workspace without its path', async () => {
  vi.mocked(controlPlaneClient.workspaces).mockResolvedValue({ workspaces: [
    { name: 'partial', rootPath: 'C:\\projects\\partial', status: 'partial', message: 'One platform needs repair.', platforms: [
      { platform: 'android', configPath: 'android.yaml', status: 'available', message: 'Platform is available.' },
      { platform: 'web', configPath: 'web.yaml', status: 'unavailable', message: 'Platform is unavailable.', action: 'Repair web config.' },
    ] },
  ] });
  render(<ControlPlaneApp />);

  const partial = await screen.findByRole('button', { name: /partial/i });
  expect(partial).toHaveTextContent('android, web unavailable');
  expect(partial).not.toHaveTextContent('C:\\projects');
});

it('uses the full-bleed outlet only for the selected workspace browser presentation', async () => {
  vi.mocked(controlPlaneClient.workspaces).mockResolvedValue({ workspaces: [
    { name: 'mobile', rootPath: 'C:\\projects\\mobile', status: 'available', message: 'Workspace is available.', platforms: [] },
  ] });
  const user = userEvent.setup();
  render(<ControlPlaneApp />);
  const outlet = screen.getByRole('main');

  expect(outlet).not.toHaveClass('cp-page-outlet--full-bleed');
  await user.click(await screen.findByRole('button', { name: /mobile/i }));
  await waitFor(() => expect(outlet).toHaveClass('cp-page-outlet--full-bleed'));

  await user.click(screen.getByRole('button', { name: 'Configure workspace' }));
  await waitFor(() => expect(outlet).not.toHaveClass('cp-page-outlet--full-bleed'));
});

it('distinguishes workspace registry loading from empty and retries a failed request', async () => {
  let resolveInitial!: (value: { workspaces: [] }) => void;
  vi.mocked(controlPlaneClient.workspaces)
    .mockImplementationOnce(() => new Promise((resolve) => { resolveInitial = resolve; }))
    .mockRejectedValueOnce({ code: 'network_error', message: 'Registry unavailable.', action: 'Retry locally.' })
    .mockResolvedValueOnce({ workspaces: [] });
  const user = userEvent.setup();
  render(<ControlPlaneApp />);

  expect(screen.getByText('Loading workspaces…')).toBeVisible();
  expect(screen.queryByText('No registered workspaces')).not.toBeInTheDocument();
  resolveInitial({ workspaces: [] });
  expect(await screen.findByText('No registered workspaces')).toBeVisible();

  await user.click(screen.getByRole('button', { name: 'Create workspace' }));
  await user.click(screen.getByRole('button', { name: 'Cancel registry fixture' }));
  expect(await screen.findByText('Registry unavailable.')).toBeVisible();
  await user.click(screen.getByRole('button', { name: 'Retry workspace registry' }));
  await waitFor(() => expect(controlPlaneClient.workspaces).toHaveBeenCalledTimes(3));
  expect(await screen.findByText('No registered workspaces')).toBeVisible();
});
