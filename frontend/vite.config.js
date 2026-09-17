import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

/**
 * The API is called through a dev-server proxy rather than directly.
 *
 * Two reasons, both about the browser rather than the network: the backend's CORS
 * allow-list is http://localhost:3000 and :5173, and this dev server runs on 5174, so a
 * direct call is refused before it leaves the page; and the refresh token arrives as an
 * HttpOnly cookie, which a cross-site response cannot set under current cookie defaults.
 * Proxied, every request is same-origin and neither problem exists.
 *
 * `changeOrigin` rewrites the Host header so the upstream nginx routes by its own name.
 * Set VITE_API_PROXY_TARGET to point at a local backend (http://localhost:8081) instead.
 *
 * https://vite.dev/config/
 */
const DEFAULT_API_TARGET = 'https://j15e206.p.ssafy.io'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')

  return {
    plugins: [react()],
    server: {
      proxy: {
        '/api': {
          target: env.VITE_API_PROXY_TARGET || DEFAULT_API_TARGET,
          changeOrigin: true,
        },
      },
    },
  }
})
