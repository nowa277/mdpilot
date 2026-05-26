/// <reference types="vitest" />
import { fileURLToPath, URL } from 'node:url';

import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
      '@shared': fileURLToPath(new URL('./src/shared', import.meta.url)),
      '@features': fileURLToPath(new URL('./src/features', import.meta.url)),
      '@mocks': fileURLToPath(new URL('./src/mocks', import.meta.url)),
    },
  },
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      '/llm-proxy': {
        target: 'https://df.dawnloadai.com:9888',
        changeOrigin: true,
        secure: false,
        rewrite: (p) => p.replace(/^\/llm-proxy/, ''),
      },
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./tests/setup.ts'],
    css: false,
    env: { VITE_API_MODE: 'mock', VITE_API_BASE: '', VITE_WS_BASE: '' },
    coverage: { provider: 'v8', reporter: ['text', 'html'] },
  },
});
