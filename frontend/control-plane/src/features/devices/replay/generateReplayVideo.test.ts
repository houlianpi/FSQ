import { hasSeekableRange, validateReplayBlob } from './generateReplayVideo';

it('requires an actual seekable range rather than finite duration', () => {
  expect(hasSeekableRange({ seekable: { length: 0 } as TimeRanges })).toBe(false);
  expect(hasSeekableRange({ seekable: { length: 1 } as TimeRanges })).toBe(true);
});

it('releases object URL and media resources immediately when validation aborts', async () => {
  const revoke = vi.fn();
  vi.stubGlobal('URL', { ...URL, createObjectURL: vi.fn(() => 'blob:replay'), revokeObjectURL: revoke });
  const pause = vi.spyOn(HTMLMediaElement.prototype, 'pause').mockImplementation(() => undefined);
  const load = vi.spyOn(HTMLMediaElement.prototype, 'load').mockImplementation(() => undefined);
  const controller = new AbortController();
  const validation = validateReplayBlob(new Blob(['video']), true, controller.signal);
  controller.abort();
  await expect(validation).resolves.toBe(false);
  expect(revoke).toHaveBeenCalledWith('blob:replay');
  expect(pause).toHaveBeenCalled();
  expect(load).toHaveBeenCalled();
  vi.unstubAllGlobals();
});