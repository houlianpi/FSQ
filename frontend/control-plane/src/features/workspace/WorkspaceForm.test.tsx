import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ControlPlaneApiError, controlPlaneClient } from '../../api/controlPlaneClient';
import type { WorkspaceDetail } from '../../api/types';
import { WorkspaceForm } from './WorkspaceForm';

const detail: WorkspaceDetail = {
  name: 'mobile',
  rootPath: 'C:\\projects\\mobile',
  configPath: 'C:\\projects\\mobile\\.fsq\\config.yaml',
  platform: 'android',
  target: { appId: 'com.example.original' },
  env: { TEST_PASSWORD: 'saved-secret' },
  revision: 'sha256:original',
};

afterEach(() => vi.restoreAllMocks());

it('clears the previous target on platform change and submits the complete masked environment', async () => {
  const created = { ...detail, name: 'web-check', platform: 'web' as const, target: { browserExecutablePath: 'C:\\Browser\\browser.exe' } };
  const create = vi.spyOn(controlPlaneClient, 'createWorkspace').mockResolvedValue(created);
  const onSaved = vi.fn();
  const user = userEvent.setup();
  render(<WorkspaceForm mode="create" onCancel={vi.fn()} onSaved={onSaved} />);

  await user.type(screen.getByLabelText('Workspace name'), 'web-check');
  await user.type(screen.getByLabelText('Parent path'), 'C:\\projects');
  await user.type(screen.getByLabelText('App ID'), 'com.example.old');
  await user.selectOptions(screen.getByLabelText('Platform'), 'web');
  await user.type(screen.getByLabelText('Web path'), 'C:\\Browser\\browser.exe');
  await user.click(screen.getByText('Environment'));
  await user.click(screen.getByRole('button', { name: 'Add environment value' }));
  await user.type(screen.getByLabelText('Name'), 'TEST_PASSWORD');
  const secret = screen.getByLabelText('Value');
  await user.type(secret, 'new-secret');
  expect(secret).toHaveAttribute('type', 'password');
  await user.click(screen.getByRole('button', { name: 'Show value for TEST_PASSWORD' }));
  expect(secret).toHaveAttribute('type', 'text');
  await user.click(screen.getByRole('button', { name: 'Create workspace' }));

  expect(create).toHaveBeenCalledWith({
    name: 'web-check',
    parentPath: 'C:\\projects',
    platform: 'web',
    target: { browserExecutablePath: 'C:\\Browser\\browser.exe' },
    env: { TEST_PASSWORD: 'new-secret' },
  });
  expect(onSaved).toHaveBeenCalledWith(created);
});

it('preserves an edit draft on revision conflict and reloads only when requested', async () => {
  const conflict = new ControlPlaneApiError(409, {
    code: 'workspace_conflict',
    message: 'Workspace configuration changed on disk.',
    action: 'Reload the latest configuration before saving again.',
  });
  const update = vi.spyOn(controlPlaneClient, 'updateWorkspace').mockRejectedValue(conflict);
  const reload = vi.fn();
  const user = userEvent.setup();
  render(<WorkspaceForm mode="edit" detail={detail} onCancel={vi.fn()} onSaved={vi.fn()} onReloadLatest={reload} />);

  const appId = screen.getByLabelText('App ID');
  await user.clear(appId);
  await user.type(appId, 'com.example.draft');
  const secret = screen.getByLabelText('Value');
  await user.clear(secret);
  await user.type(secret, 'draft-secret');
  await user.click(screen.getByRole('button', { name: 'Save changes' }));

  expect(update).toHaveBeenCalledWith('mobile', {
    target: { appId: 'com.example.draft' },
    env: { TEST_PASSWORD: 'draft-secret' },
    expectedRevision: 'sha256:original',
  });
  expect(await screen.findByText(conflict.body.message)).toBeVisible();
  expect(appId).toHaveValue('com.example.draft');
  expect(secret).toHaveValue('draft-secret');
  expect(reload).not.toHaveBeenCalled();

  await user.click(screen.getByRole('button', { name: 'Reload latest' }));
  expect(reload).toHaveBeenCalledOnce();
});