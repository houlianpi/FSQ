import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { controlPlaneClient } from '../../api/controlPlaneClient';
import type { WorkspaceDetail, WorkspacePlatformDetail } from '../../api/types';
import { WorkspacePage, WorkspaceTitlebar } from './WorkspacePage';

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

it('loads private repair details only on Edit and clears them during registry revalidation',async()=>{
  const response:WorkspaceDetail={...summary('repair'),status:'unavailable',platforms:[{platform:'macos',configPath:'mac.yaml',status:'unavailable',message:'Missing app',action:'Repair',diagnosticAvailable:true,repairAvailable:true}]};
  vi.spyOn(controlPlaneClient,'workspace').mockResolvedValue(response);
  const detail=vi.spyOn(controlPlaneClient,'workspacePlatform').mockResolvedValue({name:'repair',rootPath:'/local',configPath:'mac.yaml',platform:'macos',target:{bundleId:'com.example.app',appPath:'/Missing.app'},env:{PRIVATE:'sensitive-local-value'},revision:'sha256:old'});
  const {rerender}=render(<WorkspacePage {...props} selectedName="repair" repairContext/>);
  await screen.findByRole('button',{name:'Edit target configuration'});
  expect(detail).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole('button',{name:'Edit target configuration'}));
  await waitFor(()=>expect(detail).toHaveBeenCalledWith('repair','macos',expect.any(AbortSignal)));
  expect(await screen.findByDisplayValue('/Missing.app')).toBeInTheDocument();
  rerender(<WorkspacePage {...props} selectedName={null} repairContext/>);
  expect(screen.queryByDisplayValue('/Missing.app')).not.toBeInTheDocument();
  expect(screen.queryByDisplayValue('sensitive-local-value')).not.toBeInTheDocument();
});

it('keeps repair configuration isolated across registry loading and reload',async()=>{
  const response:WorkspaceDetail={...summary('repair'),status:'unavailable',platforms:[{platform:'macos',configPath:'mac.yaml',status:'unavailable',message:'Missing app',action:'Repair',diagnosticAvailable:true,repairAvailable:true}]};
  vi.spyOn(controlPlaneClient,'workspace').mockResolvedValue(response);
  const onConfigurationOpenChange=vi.fn();
  const {rerender}=render(<WorkspacePage {...props} selectedName="repair" repairContext onConfigurationOpenChange={onConfigurationOpenChange}/>);
  await screen.findByText('macOS configuration unavailable');
  rerender(<WorkspacePage {...props} selectedName={null} repairContext onConfigurationOpenChange={onConfigurationOpenChange}/>);
  expect(onConfigurationOpenChange).not.toHaveBeenCalledWith(false);
  rerender(<WorkspacePage {...props} selectedName="repair" repairContext configurationOpen={false} onConfigurationOpenChange={onConfigurationOpenChange}/>);
  expect(await screen.findByRole('button',{name:'Back to diagnostics'})).toBeVisible();
  expect(screen.queryByRole('button',{name:'Add platform'})).not.toBeInTheDocument();
  expect(screen.queryByRole('region',{name:/Workspace files/})).not.toBeInTheDocument();
  expect(screen.getByRole('button',{name:'Edit target configuration'})).toBeVisible();
});

it('groups the workspace name and full path separately from platform metadata', () => {
  const onConfigure = vi.fn();
  render(<WorkspaceTitlebar workspace={{
    name: 'edge',
    rootPath: 'D:\\fsq\\edge',
    status: 'available',
    message: 'Available.',
    platforms: [
      { platform: 'android', configPath: 'android.yaml', status: 'available', message: 'Available.' },
      { platform: 'web', configPath: 'web.yaml', status: 'unavailable', message: 'Unavailable.', action: 'Repair web config.' },
    ],
  }} onConfigure={onConfigure} />);

  const heading = screen.getByRole('heading', { name: 'edge' });
  const path = screen.getByText('D:\\fsq\\edge');
  const platforms = screen.getByLabelText('Workspace platforms');
  expect(heading.parentElement).toContainElement(path);
  expect(heading.parentElement).not.toContainElement(platforms);
  expect(heading.parentElement?.parentElement).toContainElement(platforms);
  expect(screen.getByLabelText('Android available').querySelector('[title="Available"] svg')).toBeVisible();
  expect(screen.getByLabelText('Web unavailable')).toHaveTextContent('Unavailable');
  expect(screen.getByRole('button', { name: 'Configure workspace' })).toHaveAttribute('title', 'Configure workspace');
});

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
it('reports full-bleed presentation only while the loaded browser is visible', async () => {
  const detail = deferred<WorkspaceDetail>();
  vi.spyOn(controlPlaneClient, 'workspace').mockReturnValue(detail.promise);
  const onPresentationChange = vi.fn();
  const { rerender } = render(<WorkspacePage {...props} configurationOpen={false} selectedName="alpha" onPresentationChange={onPresentationChange} />);

  expect(onPresentationChange).toHaveBeenLastCalledWith('default');
  await act(async () => detail.resolve(summary('alpha')));
  await waitFor(() => expect(onPresentationChange).toHaveBeenLastCalledWith('full-bleed'));

  rerender(<WorkspacePage {...props} configurationOpen selectedName="alpha" onPresentationChange={onPresentationChange} />);
  await waitFor(() => expect(onPresentationChange).toHaveBeenLastCalledWith('default'));
});
