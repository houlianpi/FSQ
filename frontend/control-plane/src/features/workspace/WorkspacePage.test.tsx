import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { controlPlaneClient } from '../../api/controlPlaneClient';
import type { WorkspaceDetail, WorkspacePlatformDetail } from '../../api/types';
import { WorkspacePage } from './WorkspacePage';

const summary = (name: string): WorkspaceDetail => ({
  name,
  rootPath: `C:\\projects\\${name}`,
  status: 'available',
  message: 'Available.',
  platforms: [
    { platform: 'android', configPath: 'android.yaml', status: 'available', message: 'Available.', target: { appId: `com.example.${name}` }, env: [], revision: 'sha256:android' },
    { platform: 'web', configPath: 'web.yaml', status: 'available', message: 'Available.', target: { browserChannel: 'chrome', browserExecutablePath: 'C:\\chrome.exe' }, env: [], revision: 'sha256:web' },
  ],
});

const props = {
  createRequested: false,
  configurationOpen: true,
  onRetryRegistry: vi.fn(),
  onRequestCreate: vi.fn(),
  onCancelCreate: vi.fn(),
  onConfigurationOpenChange: vi.fn(),
  onCreated: vi.fn(),
  onRegistryChanged: vi.fn(),
};

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => { resolve = done; });
  return { promise, resolve };
}

afterEach(() => vi.restoreAllMocks());

it('discards an aborted platform detail response after the workspace changes', async () => {
  const oldDetail = deferred<WorkspacePlatformDetail>();
  vi.spyOn(controlPlaneClient, 'workspace').mockImplementation((name) => Promise.resolve(summary(name)));
  const platformRequest = vi.spyOn(controlPlaneClient, 'workspacePlatform').mockReturnValue(oldDetail.promise);
  const user = userEvent.setup();
  const { rerender } = render(<WorkspacePage {...props} selectedName="alpha" />);
  await user.click(await screen.findByRole('button', { name: 'Edit' }));
  const signal = platformRequest.mock.calls[0]?.[2];

  rerender(<WorkspacePage {...props} selectedName="beta" />);
  await screen.findByRole('heading', { name: 'beta' });
  oldDetail.resolve({ ...summary('alpha').platforms[0], name: 'alpha', rootPath: 'C:\\projects\\alpha', env: { SECRET: 'old-value' } } as WorkspacePlatformDetail);
  await waitFor(() => expect(signal?.aborted).toBe(true));

  expect(screen.queryByRole('group', { name: 'Edit Android' })).not.toBeInTheDocument();
  expect(screen.queryByDisplayValue('old-value')).not.toBeInTheDocument();
});

it('implements selected tab-panel relationships and keyboard navigation', async () => {
  vi.spyOn(controlPlaneClient, 'workspace').mockResolvedValue(summary('alpha'));
  const user = userEvent.setup();
  render(<WorkspacePage {...props} selectedName="alpha" />);
  const android = await screen.findByRole('tab', { name: /Android/ });
  const web = screen.getByRole('tab', { name: /Web/ });
  android.focus();
  await user.keyboard('{End}');

  expect(web).toHaveFocus();
  expect(web).toHaveAttribute('aria-selected', 'true');
  expect(screen.getByRole('tabpanel')).toHaveAttribute('aria-labelledby', web.id);
});
