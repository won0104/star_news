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
          /*
           * 브라우저가 붙인 Origin 을 떼고 보낸다.
           *
           * Same-origin GETs carry no `Origin`, but a same-origin POST does — so once the
           * proxy forwarded it, the API saw `http://localhost:5174`, found it outside its
           * allow-list and answered `Invalid CORS request` with 403. Every write failed
           * while every read worked, which is what made it look like a signup bug.
           *
           * By the time the request leaves here it is server-to-server and the header is
           * a leftover from the browser leg, so dropping it is honest rather than a
           * bypass: nothing is claiming an origin it does not have. In production the app
           * and the API share an origin and none of this applies.
           */
          configure: (proxy) => {
            proxy.on('proxyReq', (proxyReq) => {
              proxyReq.removeHeader('origin')
            })
          },
        },
      },
    },
  }
})
