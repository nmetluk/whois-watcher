import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  // Статика отдаётся nginx из `location /app/ { alias .../webapp/dist/; }`
  // (same-origin с /api/webapp/* и CSP 'self'). См. docs/deployment.md.
  base: '/app/',
  server: { port: 5173, proxy: { '/api': { target: 'http://127.0.0.1:8080', changeOrigin: true } } },
})
