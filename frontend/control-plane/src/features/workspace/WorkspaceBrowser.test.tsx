import { act, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { controlPlaneClient } from '../../api/controlPlaneClient';
import type { WorkspaceEntriesResponse, WorkspaceFileResponse } from '../../api/types';
import { WorkspaceBrowser } from './WorkspaceBrowser';

vi.mock('../../api/controlPlaneClient', () => ({
  controlPlaneClient: { workspaceEntries: vi.fn(), workspaceFile: vi.fn() },
  toApiError: vi.fn((error) => error),
}));

const entries = (path: string, names: string[]): WorkspaceEntriesResponse => ({
  path,
  entries: names.map((name) => ({
    path: path ? `${path}/${name}` : name,
    name,
    kind: name.includes('.') ? 'file' : 'directory',
    size: name.includes('.') ? 10 : null,
    modifiedTime: '2030-01-01T00:00:00Z',
  })),
  truncated: false,
});

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((accept) => { resolve = accept; });
  return { promise, resolve };
}

const file = (name: string, content: string): WorkspaceFileResponse => ({
  path: `cases/${name}`,
  name,
  mediaType: 'text/yaml',
  presentation: 'code',
  size: content.length,
  lineCount: 1,
  modifiedTime: '2030-01-01T00:00:00Z',
  content,
});

afterEach(() => vi.clearAllMocks());

it('renders a distinct successful empty tree state', async () => {
  vi.mocked(controlPlaneClient.workspaceEntries).mockResolvedValue(entries('', []));

  render(<WorkspaceBrowser workspaceName="alpha" />);

  expect(await screen.findByText('No cases or knowledge files')).toBeVisible();
  expect(screen.queryByText('Loading workspace files…')).not.toBeInTheDocument();
});

it('ignores stale root and nested responses after the selected workspace changes', async () => {
  const alphaRoot = deferred<WorkspaceEntriesResponse>();
  const alphaCases = deferred<WorkspaceEntriesResponse>();
  const betaCases = deferred<WorkspaceEntriesResponse>();
  vi.mocked(controlPlaneClient.workspaceEntries).mockImplementation((workspace, path) => {
    if (workspace === 'alpha' && path === '') return alphaRoot.promise;
    if (workspace === 'alpha') return alphaCases.promise;
    if (path === '') return Promise.resolve(entries('', ['cases']));
    return betaCases.promise;
  });

  const user = userEvent.setup();
  const view = render(<WorkspaceBrowser workspaceName="alpha" />);
  view.rerender(<WorkspaceBrowser workspaceName="beta" />);
  await user.click(await screen.findByRole('button', { name: 'cases' }));
  expect(screen.getByText('Loading…')).toBeVisible();

  alphaRoot.resolve(entries('', ['alpha-only.md']));
  alphaCases.resolve(entries('cases', ['alpha-case.yaml']));
  await Promise.resolve();

  expect(screen.queryByText('alpha-only.md')).not.toBeInTheDocument();
  expect(screen.getByText('Loading…')).toBeVisible();

  betaCases.resolve(entries('cases', ['beta-case.yaml']));
  expect(await screen.findByRole('button', { name: 'beta-case.yaml' })).toBeVisible();
});

it('suppresses raw HTML in Markdown preview and exposes it only in the code tab', async () => {
  vi.mocked(controlPlaneClient.workspaceEntries)
    .mockResolvedValueOnce(entries('', ['knowledge']))
    .mockResolvedValueOnce(entries('knowledge', ['project.md']));
  vi.mocked(controlPlaneClient.workspaceFile).mockResolvedValue({
    path: 'knowledge/project.md',
    name: 'project.md',
    mediaType: 'text/markdown',
    presentation: 'markdown',
    size: 45,
    lineCount: 3,
    modifiedTime: '2030-01-01T00:00:00Z',
    content: '# Safe heading\n<script>alert("unsafe")</script>',
  } satisfies WorkspaceFileResponse);

  const user = userEvent.setup();
  const { container } = render(<WorkspaceBrowser workspaceName="alpha" />);
  await user.click(await screen.findByRole('button', { name: 'knowledge' }));
  await user.click(await screen.findByRole('button', { name: 'project.md' }));

  expect(await screen.findByRole('heading', { name: 'Safe heading' })).toBeVisible();
  expect(container.querySelector('.cp-markdown script')).toBeNull();
  expect(screen.queryByText('alert("unsafe")')).not.toBeInTheDocument();

  await user.click(screen.getByRole('tab', { name: 'Code' }));
  expect(screen.getByText(/<script>alert\("unsafe"\)<\/script>/)).toBeVisible();
});

it('keeps the latest file selection when an earlier request finishes last', async () => {
  const first = deferred<WorkspaceFileResponse>();
  const second = deferred<WorkspaceFileResponse>();
  vi.mocked(controlPlaneClient.workspaceEntries)
    .mockResolvedValueOnce(entries('', ['cases']))
    .mockResolvedValueOnce(entries('cases', ['first.yaml', 'second.yaml']));
  vi.mocked(controlPlaneClient.workspaceFile)
    .mockImplementationOnce(() => first.promise)
    .mockImplementationOnce(() => second.promise);

  const user = userEvent.setup();
  render(<WorkspaceBrowser workspaceName="alpha" />);
  await user.click(await screen.findByRole('button', { name: 'cases' }));
  await user.click(await screen.findByRole('button', { name: 'first.yaml' }));
  await user.click(screen.getByRole('button', { name: 'second.yaml' }));
  await act(async () => second.resolve(file('second.yaml', 'second: selected')));
  expect(await screen.findByText('second: selected')).toBeVisible();

  await act(async () => first.resolve(file('first.yaml', 'first: stale')));
  expect(screen.getByText('second: selected')).toBeVisible();
  expect(screen.queryByText('first: stale')).not.toBeInTheDocument();
});