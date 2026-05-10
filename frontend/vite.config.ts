import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      '/dashboard': 'http://127.0.0.1:8000',
      '/ingest': 'http://127.0.0.1:8000',
      '/memory': 'http://127.0.0.1:8000',
    },
  },
})
