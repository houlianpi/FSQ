import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ControlPlaneShell } from './ControlPlaneShell';

it('renders reusable shell content with truthful navigation semantics', () => {
  render(<ControlPlaneShell activePage="devices" title="Test page" description="Independent outlet"><div>Arbitrary page outlet</div></ControlPlaneShell>);
  expect(screen.getByText('Arbitrary page outlet')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Devices' })).toHaveAttribute('aria-current', 'page');
  expect(screen.getByRole('button', { name: 'Config' })).toBeEnabled();
  expect(screen.queryByRole('button', { name: 'Overview' })).not.toBeInTheDocument();
  expect(screen.getByText('Overview').closest('[aria-disabled="true"]')).toBeInTheDocument();
  expect(screen.getAllByText('Unavailable')).toHaveLength(4);
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
