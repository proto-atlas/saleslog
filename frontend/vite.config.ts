import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// /api は FastAPI へ転送して同一オリジン化する。
// ポートは既定 8000 固定。E2E の空DBサーバ等で差し替える場合のみ環境変数で上書きする
const apiPort = process.env.FIELDOPS_API_PORT ?? '8000'
const apiProxy = {
  '/api': {
    target: `http://localhost:${apiPort}`,
  },
}

export default defineConfig({
  plugins: [react(), tailwindcss()],
  optimizeDeps: {
    include: [
      'react-router',
      '@hookform/resolvers/zod',
      'react-hook-form',
      '@clerk/react',
    ],
  },
  server: {
    port: 5173,
    proxy: apiProxy,
  },
  preview: {
    proxy: apiProxy,
  },
})
