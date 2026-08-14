import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { controlPlaneClient } from '../api/controlPlaneClient';
import { ControlPlaneApp } from './ControlPlaneApp';

vi.mock('../api/controlPlaneClient', () => ({
  controlPlaneClient: { workspaces: vi.fn().mockResolvedValue({ workspaces: [] }) },
  toApiError: vi.fn((error) => error),
}));

vi.mock('../features/devices/DevicesPage', () => ({
  DevicesPage: ({ renderShell }: { renderShell: (toolbar: React.ReactNode, content: React.ReactNode) => React.ReactNode }) =>
    renderShell(null, <div>Devices content</div>),
}));
vi.mock('../features/config/ConfigPage', () => ({
  ConfigPage: ({ onDirtyChange }: { onDirtyChange?: (dirty: boolean) => void }) => <div>Config content<button type="button" onClick={() => onDirtyChange?.(true)}>Make draft dirty</button></div>,
}));
vi.mock('../features/overview/OverviewPage', () => ({
  OverviewPage: ({ onNavigate }: { onNavigate: (page: 'devices') => void }) => <div>Overview content<button type="button" onClick={() => onNavigate('devices')}>Start dynamic</button></div>,
}));
vi.mock('../features/workspace/WorkspacePage', () => ({
  WorkspacePage: ({ createRequested, selectedName, onDirtyChange, onCancelCreate, onRegistryChanged }: { createRequested: boolean; selectedName: string | null; onDirtyChange?: (dirty: boolean) => void; onCancelCreate: () => void; onRegistryChanged: () => void }) => <div>
    {createRequested ? 'Create workspace content' : selectedName ? `Workspace ${selectedName}` : 'Workspace content'}
    <button type="button" onClick={() => onDirtyChange?.(true)}>Make workspace draft dirty</button>
    <button type="button" onClick={createRequested ? onCancelCreate : onRegistryChanged}>Cancel registry fixture</button>
  </div>,
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

  await waitFor(() => expect(openNavigation).toHaveAttribute('aria-expanded', 'true'));
  expect(createWorkspace).toHaveFocus();
  matchMedia.mockRestore();
});

it('restores the previous workspace selection when creation is cancelled', async () => {
  vi.mocked(controlPlaneClient.workspaces).mockResolvedValue({ workspaces: [
    { name: 'mobile', configPath: 'C:\\projects\\mobile\\.fsq\\config.yaml', rootPath: 'C:\\projects\\mobile', status: 'available', platform: 'android', message: 'Workspace is available.' },
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
    { name: 'mobile', configPath: 'C:\\projects\\mobile\\.fsq\\config.yaml', rootPath: 'C:\\projects\\mobile', status: 'available', platform: 'android', message: 'Workspace is available.' },
    { name: 'broken', configPath: 'C:\\projects\\broken\\.fsq\\config.yaml', rootPath: 'C:\\projects\\broken', status: 'unavailable', message: 'Configuration is unavailable.', action: 'Repair config.yaml.' },
  ] });
  const user = userEvent.setup();
  render(<ControlPlaneApp />);

  const broken = await screen.findByText('broken');
  expect(broken.closest('[aria-disabled="true"]')).toHaveAttribute('title', 'Configuration is unavailable. Repair config.yaml.');
  expect(screen.queryByRole('button', { name: /broken/i })).not.toBeInTheDocument();

  await user.click(screen.getByRole('button', { name: /mobile/i }));
  expect(screen.getByText('Workspace mobile')).toBeVisible();
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