import { resolve } from 'node:path';
import { defineConfig, loadEnv } from 'vite';

const apiPrefixes = [
  '/cancel',
  '/execute',
  '/preview',
  '/replay',
  '/replay-video',
  '/replay-video-file',
  '/reports',
  '/runs',
  '/runtime-info',
  '/screenshot',
  '/session',
  '/status',
  '/step-artifacts',
  '/task-progress',
  '/task-stream',
  '/yaml',
];

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const apiOrigin = env.FSQ_PLAYGROUND_API_ORIGIN || 'http://127.0.0.1:8878';
  const proxy = Object.fromEntries(apiPrefixes.map((prefix) => [prefix, { target: apiOrigin }]));

  return {
    appType: 'mpa',
    root: resolve(import.meta.dirname, 'frontend'),
    server: {
      host: '127.0.0.1',
      proxy,
    },
    build: {
      outDir: resolve(import.meta.dirname, 'fsq_agent/playground/static'),
      emptyOutDir: true,
      rollupOptions: {
        input: {
          playground: resolve(import.meta.dirname, 'frontend/playground/index.html'),
        },
      },
    },
  };
});
