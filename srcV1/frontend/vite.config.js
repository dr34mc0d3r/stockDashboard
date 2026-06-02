import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    // Proxy API calls to the FastAPI backend during development so the
    // browser can use same-origin "/api/..." paths (avoids CORS in dev).
    proxy: {
      // The trade-updates stream is a websocket; it needs ws: true.
      '/api/stream': {
        target: 'http://localhost:8000',
        ws: true,
      },
      '/api': 'http://localhost:8000',
    },
  },
})
