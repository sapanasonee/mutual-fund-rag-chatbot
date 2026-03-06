import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// Pass a function to defineConfig to access the 'mode'
export default defineConfig(({ mode }) => {
  // Load environment variables from the current directory
  // The third argument '' loads all variables, regardless of prefix
  const env = loadEnv(mode, process.cwd(), '');

  const backendTarget = env.VITE_BACKEND_URL || 'http://localhost:8000'

  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: {
        // Use the loaded 'env' object instead of import.meta.env
        '/chat': {
          target: backendTarget,
          changeOrigin: true,
        },
        '/funds': {
          target: backendTarget,
          changeOrigin: true,
        },
        '/search-funds': {
          target: backendTarget,
          changeOrigin: true,
        },
        '/health': {
          target: backendTarget,
          changeOrigin: true,
        },
      },
    },
  }
})