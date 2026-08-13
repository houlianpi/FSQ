import { render, screen } from '@testing-library/react';
import { controlPlaneClient } from '../../../api/controlPlaneClient';

const replayMocks = vi.hoisted(() => ({ generateReplayVideo: vi.fn(), blobToBase64: vi.fn() }));
vi.mock('../replay/generateReplayVideo', () => replayMocks);

import { ReplayVideoView } from './ReplayVideoView';

afterEach(() => vi.restoreAllMocks());

it('generates, uploads, and displays a stored replay when no video exists', async () => {
  vi.spyOn(controlPlaneClient, 'replayVideo').mockResolvedValue({ available: false, videoUrl: null });
  vi.spyOn(controlPlaneClient, 'replayFrames').mockResolvedValue({
    available: true, message: null, frames: [{ index: 1, timestamp: 1, mimeType: 'image/png', contentBase64: 'ZnJhbWU=' }],
  });
  const generatedBlob = new Blob(['webm'], { type: 'video/webm' });
  replayMocks.generateReplayVideo.mockResolvedValue(generatedBlob);
  replayMocks.blobToBase64.mockResolvedValue('d2VibQ==');
  const upload = vi.spyOn(controlPlaneClient, 'uploadReplayVideo').mockResolvedValue({ available: true, videoUrl: '/stored.webm' });

  render(<ReplayVideoView requestId="request-1" />);

  expect(await screen.findByLabelText('Run replay video')).toHaveAttribute('src', '/stored.webm?generation=0');
  expect(replayMocks.generateReplayVideo).toHaveBeenCalledOnce();
  const generationSignal = replayMocks.generateReplayVideo.mock.calls[0][1] as AbortSignal;
  expect(replayMocks.generateReplayVideo).toHaveBeenCalledWith(
    [{ index: 1, timestamp: 1, mimeType: 'image/png', contentBase64: 'ZnJhbWU=' }],
    generationSignal,
  );
  expect(replayMocks.blobToBase64.mock.calls[0][0]).toBe(generatedBlob);
  expect(upload.mock.calls[0][3]).toBe(generationSignal);
  expect(upload.mock.calls[0].slice(0, 3)).toEqual(['request-1', 'video/webm', 'd2VibQ==']);
});