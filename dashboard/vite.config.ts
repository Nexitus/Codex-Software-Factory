import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

const dashboardRoot = fileURLToPath(new URL('.', import.meta.url));
const dashboardOrigin = 'http://127.0.0.1:5173';
const apiOrigin = 'http://127.0.0.1:8765';

const devApiOriginGuard = {
  name: 'factory-dev-api-origin-guard',
  configureServer(server: import('vite').ViteDevServer) {
    server.middlewares.use((request, response, next) => {
      if (!request.url?.startsWith('/api/')) return next();
      const origin = request.headers.origin;
      if (origin && origin !== dashboardOrigin) {
        response.statusCode = 403;
        response.end('Cross-origin requests are not allowed');
        return;
      }
      next();
    });
  },
};

export default defineConfig({
  root: dashboardRoot,
  plugins: [devApiOriginGuard, tailwindcss(), react()],
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': {
        target: apiOrigin,
        changeOrigin: true,
        configure(proxy) {
          proxy.on('proxyReq', (proxyRequest, request) => {
            // Only translate the exact origin of this loopback dev UI. Missing
            // Origin remains missing, and foreign origins are rejected above.
            if (request.headers.origin === dashboardOrigin) {
              proxyRequest.setHeader('Origin', apiOrigin);
            }
          });
        },
      },
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
});
