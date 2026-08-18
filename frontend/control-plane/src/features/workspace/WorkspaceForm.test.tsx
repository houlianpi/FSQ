import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ControlPlaneApiError, controlPlaneClient } from '../../api/controlPlaneClient';
import type { WorkspaceDetail, WorkspacePlatformDetail } from '../../api/types';
import { WorkspaceForm } from './WorkspaceForm';

const detail: WorkspacePlatformDetail = {
  name: 'mobile',
  rootPath: 'C:\\projects\\mobile',
  configPath: 'C:\\projects\\mobile\\.fsq\\config\\config.android.yaml',
  platform: 'android',
  target: { appId: 'com.example.original' },
  env: { TEST_PASSWORD: 'saved-secret' },
  revision: 'sha256:original',
};
const workspace: WorkspaceDetail = {
  name: 'mobile', rootPath: 'C:\\projects\\mobile', status: 'available', message: 'Workspace is available.',
  platforms: [{
    platform: 'android', configPath: detail.configPath, status: 'available', message: 'Platform is available.',
    target: detail.target, env: [{ name: 'TEST_PASSWORD', configured: true }], revision: detail.revision,
  }],
};

afterEach(() => vi.restoreAllMocks());

it('clears the previous target on platform change and submits the complete masked environment', async () => {
  const created: WorkspaceDetail = {
    name: 'web-check', rootPath: 'C:\\projects\\web-check', status: 'available', message: 'Workspace is available.',
    platforms: [{ platform: 'web', configPath: 'C:\\projects\\web-check\\.fsq\\config\\config.web.yaml', status: 'available', message: 'Platform is available.', target: { browserChannel: 'chrome', browserExecutablePath: 'C:\\Browser\\browser.exe' }, env: [{ name: 'TEST_PASSWORD', configured: true }], revision: 'sha256:created' }],
  };
  const pickParent = vi.spyOn(controlPlaneClient, 'pickWorkspaceParentDirectory').mockResolvedValue({ status: 'selected', parentPath: 'C:\\projects' });
  const create = vi.spyOn(controlPlaneClient, 'createWorkspace').mockResolvedValue(created);
  const onSaved = vi.fn();
  const user = userEvent.setup();
  render(<WorkspaceForm mode="create" onCancel={vi.fn()} onSaved={onSaved} />);

  expect(screen.getByLabelText('Workspace name')).toBeVisible();
  expect(screen.getByLabelText('Parent folder')).toHaveAttribute('readonly');
  expect(screen.queryByRole('combobox', { name: 'Platform 1' })).not.toBeInTheDocument();
  expect(screen.queryByRole('heading', { name: 'Target' })).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText('Workspace name'), { target: { value: 'web-check' } });
  await user.click(screen.getByRole('button', { name: 'Choose folder' }));
  expect(pickParent).toHaveBeenCalledOnce();
  expect(screen.getByLabelText('Parent folder')).toHaveValue('C:\\projects');
  await user.click(screen.getByRole('button', { name: 'Add platform' }));
  expect(screen.getByRole('combobox', { name: 'Platform 1' })).toBeVisible();
  await user.selectOptions(screen.getByRole('combobox', { name: 'Platform 1' }), 'web');
  fireEvent.change(screen.getByLabelText('Web path'), { target: { value: 'C:\\Browser\\browser.exe' } });
  await user.click(screen.getByText('Environment'));
  await user.click(screen.getByRole('button', { name: 'Add environment value' }));
  fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'TEST_PASSWORD' } });
  const secret = screen.getByLabelText('Value');
  fireEvent.change(secret, { target: { value: 'new-secret' } });
  expect(secret).toHaveAttribute('type', 'password');
  const reveal = screen.getByRole('button', { name: 'Show value for TEST_PASSWORD' });
  expect(reveal).toHaveAttribute('title', 'Show value for TEST_PASSWORD');
  await user.click(reveal);
  expect(secret).toHaveAttribute('type', 'text');
  await user.click(screen.getByRole('button', { name: 'Create workspace' }));

  expect(create).toHaveBeenCalledWith({
    name: 'web-check',
    parentPath: 'C:\\projects',
    platforms: [{ platform: 'web', target: { browserChannel: 'chrome', browserExecutablePath: 'C:\\Browser\\browser.exe' }, env: { TEST_PASSWORD: 'new-secret' } }],
  });
  expect(onSaved).toHaveBeenCalledWith(created);
});

it('submits all unsaved platform drafts in one workspace creation request', async () => {
  vi.spyOn(controlPlaneClient, 'pickWorkspaceParentDirectory').mockResolvedValue({ status: 'selected', parentPath: 'C:\\projects' });
  const create = vi.spyOn(controlPlaneClient, 'createWorkspace').mockResolvedValue(workspace);
  const user = userEvent.setup();
  render(<WorkspaceForm mode="create" onCancel={vi.fn()} onSaved={vi.fn()} />);

  await user.type(screen.getByLabelText('Workspace name'), 'mobile');
  await user.click(screen.getByRole('button', { name: 'Choose folder' }));
  await user.click(screen.getByRole('button', { name: 'Add platform' }));
  await user.selectOptions(screen.getByRole('combobox', { name: 'Platform 1' }), 'android');
  await user.type(screen.getByLabelText('App ID'), 'com.example.mobile');
  await user.click(screen.getByRole('button', { name: 'Add platform' }));
  expect(screen.getAllByRole('heading', { name: /Platform \d/ })).toHaveLength(2);
  await user.selectOptions(screen.getByRole('combobox', { name: 'Platform 2' }), 'web');
  await user.type(screen.getByLabelText('Web path'), 'C:\\Browser\\browser.exe');
  await user.click(screen.getByRole('button', { name: 'Create workspace' }));

  expect(create).toHaveBeenCalledWith({
    name: 'mobile', parentPath: 'C:\\projects',
    platforms: [
      { platform: 'android', target: { appId: 'com.example.mobile' }, env: {} },
      { platform: 'web', target: { browserChannel: 'chrome', browserExecutablePath: 'C:\\Browser\\browser.exe' }, env: {} },
    ],
  });
});

it('focuses the first invalid field in the first invalid platform section', async () => {
  vi.spyOn(controlPlaneClient, 'pickWorkspaceParentDirectory').mockResolvedValue({ status: 'selected', parentPath: 'C:\\projects' });
  const user = userEvent.setup();
  render(<WorkspaceForm mode="create" onCancel={vi.fn()} onSaved={vi.fn()} />);
  await user.type(screen.getByLabelText('Workspace name'), 'mobile');
  await user.click(screen.getByRole('button', { name: 'Choose folder' }));
  await user.click(screen.getByRole('button', { name: 'Add platform' }));
  const platform = screen.getByRole('combobox', { name: 'Platform 1' });

  await user.click(screen.getByRole('button', { name: 'Create workspace' }));

  expect(platform).toHaveFocus();
});

it('requires parent-folder selection before validating platform drafts', async () => {
  const user = userEvent.setup();
  render(<WorkspaceForm mode="create" onCancel={vi.fn()} onSaved={vi.fn()} />);
  await user.type(screen.getByLabelText('Workspace name'), 'mobile');

  await user.click(screen.getByRole('button', { name: 'Create workspace' }));

  expect(screen.getByText('Choose a parent folder.')).toBeVisible();
  expect(screen.getByRole('button', { name: 'Choose folder' })).toHaveFocus();
});

it('locks picker actions while pending and preserves selection across cancel and failure', async () => {
  let resolveSelection!: (value: { status: 'selected'; parentPath: string }) => void;
  const firstSelection = new Promise<{ status: 'selected'; parentPath: string }>((resolve) => { resolveSelection = resolve; });
  const pickParent = vi.spyOn(controlPlaneClient, 'pickWorkspaceParentDirectory')
    .mockReturnValueOnce(firstSelection)
    .mockResolvedValueOnce({ status: 'cancelled' })
    .mockRejectedValueOnce(new ControlPlaneApiError(503, {
      code: 'directory_picker_unavailable', message: 'Folder selection is unavailable.', action: 'Restore the desktop session and retry.',
    }))
    .mockResolvedValueOnce({ status: 'selected', parentPath: 'C:\\projects two' });
  const user = userEvent.setup();
  render(<WorkspaceForm mode="create" onCancel={vi.fn()} onSaved={vi.fn()} />);

  const choose = screen.getByRole('button', { name: 'Choose folder' });
  await user.click(choose);
  expect(choose).toBeDisabled();
  expect(choose).toHaveAttribute('aria-busy', 'true');
  expect(screen.getByRole('button', { name: 'Create workspace' })).toBeDisabled();

  resolveSelection({ status: 'selected', parentPath: 'C:\\projects one' });
  expect(await screen.findByDisplayValue('C:\\projects one')).toBeVisible();
  await user.click(screen.getByRole('button', { name: 'Choose folder' }));
  expect(screen.getByLabelText('Parent folder')).toHaveValue('C:\\projects one');
  await waitFor(() => expect(screen.getByRole('button', { name: 'Choose folder' })).toHaveFocus());

  await user.click(screen.getByRole('button', { name: 'Choose folder' }));
  expect(await screen.findByText('Folder selection is unavailable.')).toBeVisible();
  expect(screen.getByLabelText('Parent folder')).toHaveValue('C:\\projects one');

  await user.click(screen.getByRole('button', { name: 'Retry folder selection' }));
  expect(await screen.findByDisplayValue('C:\\projects two')).toBeVisible();
  expect(pickParent).toHaveBeenCalledTimes(4);
});

it('ignores a picker response after the create form is abandoned', async () => {
  let resolveSelection!: (value: { status: 'selected'; parentPath: string }) => void;
  vi.spyOn(controlPlaneClient, 'pickWorkspaceParentDirectory').mockReturnValue(new Promise((resolve) => { resolveSelection = resolve; }));
  const onDirtyChange = vi.fn();
  const user = userEvent.setup();
  const view = render(<WorkspaceForm mode="create" onCancel={vi.fn()} onSaved={vi.fn()} onDirtyChange={onDirtyChange} />);

  await user.click(screen.getByRole('button', { name: 'Choose folder' }));
  view.unmount();
  await act(async () => resolveSelection({ status: 'selected', parentPath: 'C:\\late-response' }));

  expect(onDirtyChange).toHaveBeenLastCalledWith(false);
  expect(screen.queryByDisplayValue('C:\\late-response')).not.toBeInTheDocument();
});

it('preserves an edit draft on revision conflict and reloads only when requested', async () => {
  const conflict = new ControlPlaneApiError(409, {
    code: 'workspace_conflict',
    message: 'Workspace configuration changed on disk.',
    action: 'Reload the latest configuration before saving again.',
  });
  const update = vi.spyOn(controlPlaneClient, 'updateWorkspacePlatform').mockRejectedValue(conflict);
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

  expect(update).toHaveBeenCalledWith('mobile', 'android', {
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
