import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { readFileSync, existsSync } from 'node:fs';
import { resolve } from 'node:path';

const root = resolve(process.env.JARVIS_ROOT || '..');
const tokenPath = resolve(root, 'data', '.api_token');

export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
    cors: { origin: 'http://127.0.0.1:5173' },
    allowedHosts: ['127.0.0.1'],
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8787',
        changeOrigin: false,
        configure(proxy) {
          proxy.on('proxyReq', (proxyReq) => {
            if (existsSync(tokenPath)) {
              const token = readFileSync(tokenPath, 'utf8').trim();
              proxyReq.setHeader('X-Jarvis-Token', token);
            }
          });
        },
      },
    },
  },
  build: { outDir: '../dist/frontend', emptyOutDir: true },
});
