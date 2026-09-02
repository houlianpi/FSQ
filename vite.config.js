import { resolve } from 'node:path';
import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const controlPlaneOrigin = env.FSQ_CONTROL_PLANE_API_ORIGIN || 'http://127.0.0.1:8879';

  return {
    appType: 'mpa',
    root: resolve(import.meta.dirname, 'frontend'),
    plugins: [react()],
    server: {
      host: '127.0.0.1',
      proxy: {
        '/api/control-plane': { target: controlPlaneOrigin, changeOrigin: false },
      },
    },
    build: {
      outDir: resolve(import.meta.dirname, '.frontend-dist'),
      emptyOutDir: true,
      manifest: true,
      rollupOptions: {
        input: {
          controlPlane: resolve(import.meta.dirname, 'frontend/control-plane/index.html'),
        },
      },
    },
  };
});
