import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api/worker': { target: 'http://localhost:8001', changeOrigin: true, rewrite: (p) => p.replace('/api/worker', '') },
      '/api/policy': { target: 'http://localhost:8002', changeOrigin: true, rewrite: (p) => p.replace('/api/policy', '') },
      '/api/trigger': { target: 'http://localhost:8003', changeOrigin: true, rewrite: (p) => p.replace('/api/trigger', '') },
      '/api/claims': { target: 'http://localhost:8004', changeOrigin: true, rewrite: (p) => p.replace('/api/claims', '') },
      '/api/payment': { target: 'http://localhost:8005', changeOrigin: true, rewrite: (p) => p.replace('/api/payment', '') },
      '/api/ml': { target: 'http://localhost:8006', changeOrigin: true, rewrite: (p) => p.replace('/api/ml', '') },
    },
  },
})
