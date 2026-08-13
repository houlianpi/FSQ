import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ControlPlaneApp } from './ControlPlaneApp';

vi.mock('../features/devices/DevicesPage', () => ({
  DevicesPage: ({ renderShell }: { renderShell: (toolbar: React.ReactNode, content: React.ReactNode) => React.ReactNode }) =>
    renderShell(null, <div>Devices content</div>),
}));
vi.mock('../features/config/ConfigPage', () => ({
  ConfigPage: ({ onDirtyChange }: { onDirtyChange?: (dirty: boolean) => void }) => <div>Config content<button type="button" onClick={() => onDirtyChange?.(true)}>Make draft dirty</button></div>,
}));

it('selects the two available pages through centralized navigation', async () => {
  const user = userEvent.setup();
  render(<ControlPlaneApp />);
  expect(screen.getByText('Devices content')).toBeVisible();

  await user.click(screen.getByRole('button', { name: 'Config' }));
  expect(screen.getByText('Config content')).toBeVisible();
  expect(screen.getByRole('button', { name: 'Config' })).toHaveAttribute('aria-current', 'page');

  await user.click(screen.getByRole('button', { name: 'Devices' }));
  expect(screen.getByText('Devices content')).toBeVisible();
});

it('keeps Config active when the user rejects dirty-draft navigation', async () => {
  const confirm = vi.spyOn(window, 'confirm').mockReturnValueOnce(false).mockReturnValueOnce(true);
  const user = userEvent.setup();
  render(<ControlPlaneApp />);
  await user.click(screen.getByRole('button', { name: 'Config' }));
  await user.click(screen.getByRole('button', { name: 'Make draft dirty' }));

  await user.click(screen.getByRole('button', { name: 'Devices' }));
  expect(screen.getByText('Config content')).toBeVisible();
  await user.click(screen.getByRole('button', { name: 'Devices' }));

  expect(confirm).toHaveBeenCalledTimes(2);
  expect(screen.getByText('Devices content')).toBeVisible();
});