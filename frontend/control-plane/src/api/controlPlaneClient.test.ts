import { controlPlaneClient, ControlPlaneApiError, validateRunSnapshot } from './controlPlaneClient';

afterEach(() => vi.restoreAllMocks());

it.each([
  ['bootstrap', () => controlPlaneClient.bootstrap()],
  ['readiness', () => controlPlaneClient.readiness('web')],
  ['targets', () => controlPlaneClient.targets('web')],
  ['cases', () => controlPlaneClient.cases('web')],
  ['start', () => controlPlaneClient.startRun({ mode: 'explore', platform: 'web', targetId: 'chrome', goal: 'Verify' })],
  ['cancel', () => controlPlaneClient.cancelRun('request-1')],
  ['snapshot', () => controlPlaneClient.runSnapshot('request-1')],
  ['ui snapshot', () => controlPlaneClient.uiSnapshot('request-1')],
  ['step artifacts', () => controlPlaneClient.stepArtifacts('request-1', 'step-1')],
  ['replay frames', () => controlPlaneClient.replayFrames('request-1')],
  ['replay video', () => controlPlaneClient.replayVideo('request-1')],
  ['replay upload', () => controlPlaneClient.uploadReplayVideo('request-1', 'video/webm', 'encoded')],
  ['config', () => controlPlaneClient.config()],
  ['Azure config save', () => controlPlaneClient.saveAzureConfig({ baseUrl: 'https://example.test', modelName: 'model', apiKey: 'key' })],
  ['GitHub device-flow start', () => controlPlaneClient.startGithubDeviceFlow('model')],
  ['GitHub device-flow status', () => controlPlaneClient.githubDeviceFlow('auth-1')],
  ['GitHub device-flow cancellation', () => controlPlaneClient.cancelGithubDeviceFlow('auth-1')],
  ['connection test', () => controlPlaneClient.testConnection()],
  ['workspace registry', () => controlPlaneClient.workspaces()],
  ['workspace detail', () => controlPlaneClient.workspace('mobile')],
  ['workspace create', () => controlPlaneClient.createWorkspace({ name: 'mobile', parentPath: 'C:\\projects', platform: 'android', target: { appId: 'com.example' }, env: {} })],
  ['workspace update', () => controlPlaneClient.updateWorkspace('mobile', { target: { appId: 'com.example' }, env: {}, expectedRevision: 'sha256:old' })],
  ['workspace entries', () => controlPlaneClient.workspaceEntries('mobile', 'cases')],
  ['workspace file', () => controlPlaneClient.workspaceFile('mobile', 'knowledge/project.md')],
])('rejects a malformed successful %s response', async (_name, request) => {
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({}), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  }));

  await expect(request()).rejects.toMatchObject({
    status: 200,
    body: expect.objectContaining({ code: 'invalid_response' }),
  });
});

it('rejects environment values in the workspace registry projection', async () => {
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({
    workspaces: [{
      name: 'mobile', configPath: 'C:\\projects\\mobile\\.fsq\\config.yaml', rootPath: 'C:\\projects\\mobile',
      status: 'available', message: 'Available.', platform: 'android', env: { SECRET: 'must-not-enter-navigation-state' },
    }],
  }), { status: 200, headers: { 'Content-Type': 'application/json' } }));

  await expect(controlPlaneClient.workspaces()).rejects.toMatchObject({
    body: expect.objectContaining({ code: 'invalid_response' }),
  });
});

it('encodes workspace names and file paths in client requests', async () => {
  const workspaceFile = {
    path: 'knowledge/project notes.md', name: 'project notes.md', mediaType: 'text/markdown', presentation: 'markdown',
    size: 4, lineCount: 1, modifiedTime: '2030-01-01T00:00:00Z', content: 'test',
  };
  const fetch = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify(workspaceFile), {
    status: 200, headers: { 'Content-Type': 'application/json' },
  }));

  await controlPlaneClient.workspaceFile('mobile main', 'knowledge/project notes.md');

  expect(fetch).toHaveBeenCalledWith(
    '/api/control-plane/workspaces/mobile%20main/file?path=knowledge%2Fproject%20notes.md',
    expect.objectContaining({ headers: expect.objectContaining({ 'Content-Type': 'application/json' }) }),
  );
});

it('requires step artifacts to contain readable content or an item error', async () => {
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({
    available: true, stepId: 'step-1', message: null,
    artifacts: [{ kind: 'screenshot', phase: 'before', timestamp: null, mimeType: 'image/png' }],
  }), { status: 200, headers: { 'Content-Type': 'application/json' } }));
  await expect(controlPlaneClient.stepArtifacts('request-1', 'step-1')).rejects.toMatchObject({ body: expect.objectContaining({ code: 'invalid_response' }) });
});

it('accepts Config responses without admitting GitHub token fields into the contract', async () => {
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({
    configured: true,
    provider: { type: 'github_copilot', modelName: 'gpt-5.5', authenticated: true },
  }), { status: 200, headers: { 'Content-Type': 'application/json' } }));

  await expect(controlPlaneClient.config()).resolves.toEqual({
    configured: true,
    provider: { type: 'github_copilot', modelName: 'gpt-5.5', authenticated: true },
  });
});

it('rejects a GitHub Config projection containing an unexpected token field', async () => {
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({
    configured: true,
    provider: { type: 'github_copilot', modelName: 'gpt-5.5', authenticated: true, accessToken: 'must-not-enter-state' },
  }), { status: 200, headers: { 'Content-Type': 'application/json' } }));

  await expect(controlPlaneClient.config()).rejects.toMatchObject({
    body: expect.objectContaining({ code: 'invalid_response' }),
  });
});

it('rejects malformed stream snapshots and non-image screen responses', async () => {
  expect(() => validateRunSnapshot({ requestId: 'request-1' }, 'run stream')).toThrowError(ControlPlaneApiError);
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('not an image', {
    status: 200,
    headers: { 'Content-Type': 'text/plain' },
  }));

  await expect(controlPlaneClient.screen('request-1', 1)).rejects.toMatchObject({
    body: expect.objectContaining({ code: 'invalid_response' }),
  });
});
