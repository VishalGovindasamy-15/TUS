import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    // Allow the sandboxed browser-preview host (dev only).
    allowedHosts: ['localhost', '127.0.0.1', '.e2b.app'],
    proxy: {
      '/api': {
        target: process.env.VITE_DEV_PROXY ?? 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
});
