import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// The dev proxy is a convenience: the app calls the Flask API directly on
// http://localhost:5000 (CORS is enabled in the backend), so the production
// build works from any static host as well.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      },
    },
  },
});
