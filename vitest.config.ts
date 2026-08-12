import react from '@vitejs/plugin-react';
import { defineConfig } from 'vitest/config';

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./frontend/control-plane/src/test/setup.ts'],
    include: ['frontend/control-plane/src/**/*.test.{ts,tsx}'],
    clearMocks: true,
  },
});
