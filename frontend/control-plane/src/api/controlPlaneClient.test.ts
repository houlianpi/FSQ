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

it('requires step artifacts to contain readable content or an item error', async () => {
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({
    available: true, stepId: 'step-1', message: null,
    artifacts: [{ kind: 'screenshot', phase: 'before', timestamp: null, mimeType: 'image/png' }],
  }), { status: 200, headers: { 'Content-Type': 'application/json' } }));
  await expect(controlPlaneClient.stepArtifacts('request-1', 'step-1')).rejects.toMatchObject({ body: expect.objectContaining({ code: 'invalid_response' }) });
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
