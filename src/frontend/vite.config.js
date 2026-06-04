import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// The FastAPI backend runs on :8000; proxy /api so the browser can call it
// same-origin during dev.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
  // Vitest: only pure-logic suites (lib/*.test.js) — no DOM needed.
  test: {
    environment: 'node',
    include: ['src/**/*.test.js'],
  },
})
