import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          'react-vendor': ['react', 'react-dom', 'react-router-dom'],
          'charts': ['recharts'],
          'map': ['leaflet', 'react-leaflet'],
          'utils': ['date-fns'],
        },
      },
    },
  },
  server: {
    port: 3000,
    proxy: {
      '/api/workers':  { target: 'http://localhost:8001', changeOrigin: true, rewrite: p => p.replace('/api/workers', '/api/v1') },
      '/api/policies': { target: 'http://localhost:8002', changeOrigin: true, rewrite: p => p.replace('/api/policies', '/api/v1') },
      '/api/triggers': { target: 'http://localhost:8003', changeOrigin: true, rewrite: p => p.replace('/api/triggers', '/api/v1') },
      '/api/claims':   { target: 'http://localhost:8004', changeOrigin: true, rewrite: p => p.replace('/api/claims', '/api/v1') },
      '/api/payments': { target: 'http://localhost:8005', changeOrigin: true, rewrite: p => p.replace('/api/payments', '/api/v1') },
      '/api/ml':       { target: 'http://localhost:8006', changeOrigin: true, rewrite: p => p.replace('/api/ml', '/api/v1') },
    },
  },
})
