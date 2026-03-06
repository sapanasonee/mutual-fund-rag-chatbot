import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/chat': process.env.BACKEND_URL,
      '/funds': process.env.BACKEND_URL,
      '/search-funds': process.env.BACKEND_URL,
      '/health': process.env.BACKEND_URL,
    },
  },
})
