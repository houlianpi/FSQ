import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ControlPlaneShell } from './ControlPlaneShell';

it('renders reusable shell content with truthful navigation semantics', () => {
  render(<ControlPlaneShell activePage="devices" title="Test page" description="Independent outlet"><div>Arbitrary page outlet</div></ControlPlaneShell>);
  expect(screen.getByText('Arbitrary page outlet')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Devices' })).toHaveAttribute('aria-current', 'page');
  expect(screen.getByRole('button', { name: 'Config' })).toBeEnabled();
  expect(screen.getByRole('button', { name: 'Overview' })).toBeEnabled();
  expect(screen.getByRole('button', { name: 'Workspace' })).toBeEnabled();
  expect(screen.getByRole('button', { name: 'Create workspace' })).toBeEnabled();
  expect(screen.getAllByText('Unavailable')).toHaveLength(2);

  const sidebar = screen.getByLabelText('Control Plane sidebar');
  expect(Array.from(sidebar.querySelectorAll('.cp-nav-item > span'), (item) => item.textContent)).toEqual([
    'Overview', 'Workspace', 'Devices', 'Runs', 'Config', 'Settings',
  ]);
});

it('matches the prototype navigation glyphs and unified Workspace disclosure', async () => {
  const user = userEvent.setup();
  const onNavigate = vi.fn();
  render(
    <ControlPlaneShell
      activePage="workspace"
      title="Workspace"
      description="Test"
      workspaces={[{ id: 'control-plane-demo', label: 'Control Plane Demo', description: '~/projects/fsq-control-plane-demo' }]}
      selectedWorkspaceId="control-plane-demo"
      onNavigate={onNavigate}
    >
      <div>Outlet</div>
    </ControlPlaneShell>,
  );

  expect(screen.getByRole('button', { name: 'Overview' }).querySelector('.lucide-layout-dashboard')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Workspace' }).querySelector('.lucide-file-text')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Devices' }).querySelector('.lucide-monitor')).toBeInTheDocument();
  expect(screen.getByText('Runs').closest('.cp-nav-item')?.querySelector('.lucide-rotate-ccw-clock')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Config' }).querySelector('.lucide-settings')).toBeInTheDocument();
  expect(screen.getByText('Settings').closest('.cp-nav-item')?.querySelector('.lucide-circle-question-mark')).toBeInTheDocument();

  const workspace = screen.getByRole('button', { name: 'Workspace' });
  expect(workspace).toHaveAttribute('aria-expanded', 'true');
  expect(workspace).toHaveAttribute('data-active', 'true');
  expect(screen.queryByRole('button', { name: 'Collapse workspaces' })).not.toBeInTheDocument();
  expect(screen.getByText('CP')).toHaveClass('cp-project-glyph');

  await user.click(workspace);
  expect(onNavigate).toHaveBeenCalledWith('workspace');
  expect(workspace).toHaveAttribute('aria-expanded', 'false');
  expect(screen.queryByText('Control Plane Demo')).not.toBeInTheDocument();
});

it('opens and closes the accessible drawer with focus restoration', async () => {
  const user = userEvent.setup();
  render(<ControlPlaneShell activePage="devices" title="Devices" description="Test"><div>Outlet</div></ControlPlaneShell>);
  const open = screen.getByRole('button', { name: 'Open navigation' });
  await user.click(open);
  expect(open).toHaveAttribute('aria-expanded', 'true');
  const close = screen.getByRole('button', { name: 'Close navigation' });
  expect(close).toHaveFocus();
  await user.keyboard('{Escape}');
  await waitFor(() => expect(open).toHaveFocus());
  expect(open).toHaveAttribute('aria-expanded', 'false');
});

it('traps forward and reverse keyboard focus inside the open drawer', async () => {
  const user = userEvent.setup();
  render(<ControlPlaneShell activePage="devices" title="Devices" description="Test"><button>Outlet action</button></ControlPlaneShell>);
  const open = screen.getByRole('button', { name: 'Open navigation' });
  await user.click(open);
  const close = screen.getByRole('button', { name: 'Close navigation' });
  const config = screen.getByRole('button', { name: 'Config' });

  close.focus();
  await user.keyboard('{Shift>}{Tab}{/Shift}');
  expect(config).toHaveFocus();
  await user.keyboard('{Tab}');
  expect(close).toHaveFocus();
  await user.click(screen.getByRole('button', { name: 'Dismiss navigation overlay' }));
  await waitFor(() => expect(open).toHaveFocus());
});
