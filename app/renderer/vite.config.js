import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { fileURLToPath } from 'node:url'

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
  ],
  build: {
    rollupOptions: {
      input: {
        main: fileURLToPath(new URL('./index.html', import.meta.url)),
        specimen: fileURLToPath(new URL('./specimen.html', import.meta.url)),
      },
    },
  },
  server: {
    port: 5173,
    strictPort: true,
    host: '0.0.0.0', // Bind to all interfaces — fixes IPv6 vs IPv4 mismatch in Electron
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, '')
      }
    }
  }
})

