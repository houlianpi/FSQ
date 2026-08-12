import { resolve } from 'node:path';
import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

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
  const playgroundOrigin = env.FSQ_PLAYGROUND_API_ORIGIN || 'http://127.0.0.1:8878';
  const controlPlaneOrigin = env.FSQ_CONTROL_PLANE_API_ORIGIN || 'http://127.0.0.1:8879';
  const proxy = Object.fromEntries(apiPrefixes.map((prefix) => [prefix, { target: playgroundOrigin }]));
  proxy['/api/control-plane'] = { target: controlPlaneOrigin, changeOrigin: false };

  return {
    appType: 'mpa',
    root: resolve(import.meta.dirname, 'frontend'),
    plugins: [react()],
    server: {
      host: '127.0.0.1',
      proxy,
    },
    build: {
      outDir: resolve(import.meta.dirname, '.frontend-dist'),
      emptyOutDir: true,
      manifest: true,
      rollupOptions: {
        input: {
          playground: resolve(import.meta.dirname, 'frontend/playground/index.html'),
          controlPlane: resolve(import.meta.dirname, 'frontend/control-plane/index.html'),
        },
      },
    },
  };
});
