import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/_discover': 'http://localhost:8000',
      '/cmd': 'http://localhost:8000',
      '/status': 'http://localhost:8000',
      '/last_frame': 'http://localhost:8000',
    },
  },
});
